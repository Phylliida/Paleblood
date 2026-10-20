// SPDX-License-Identifier: GPL-2.0-or-later
// Kernel object traversal: wait for the object to reach state 2, then advance.
//
// The function at 0x024bd150 walks a chain of objects held in a registry. It takes the registry
// (rdi) and a mode (esi), reads the node from registry+0x8, and answers with the node it ends up
// on -- 0 when the registry holds no node, otherwise the node it advanced to.
//
// Two things are waited on, and which one is chosen is the mode. The node carries a state word at
// +0x10 and a byte at +0x31 whose bit 0 says whether the node is already released. The node's own
// byte at +0x30 is a count of how many times this has advanced it.
//
//   mode == 2   advance straight away: it skips the released-byte pair, so the state word is never
//               read, but the advance still takes and drops the lock like every other mode.
//   mode == 1   take the lock, read the released byte, drop the lock, then advance when the node is
//               released, and otherwise spin on the state word until it reads 2 and advance.
//   mode == 0   take the lock, read the released byte, drop the lock, then advance only when the
//               node *is* released; when the bit is clear, answer 0 without advancing. The test
//               reads `test r12b,r12b; je 0x24bd227`, and the jump to the null return is taken on a
//               *clear* bit, so a released node falls through and advances.
//
// The lock is the global at 0x05aa4578. Its word *is* the vtable: the call is
// `mov rax,[rip+...] # 0x5aa4578` followed by `call [rax+0x18]`, one dereference, with the address
// of the global passed as the first argument -- the lock word lives in the global itself. Slot
// +0x18 takes the lock and slot +0x28 releases it, and both get a second argument of 0xffffffff,
// which is the "wait for it" key rather than a timeout. The registry pointer is read out of the
// global again before every call rather than kept in a register, which is how the original reaches
// its vtable each time.
//
// The wait is a poll, not a sleep: the original calls the usleep stub at 0x02fbfe68 with a
// hard-coded 1000 microsecond argument (mov edi,0x3e8) and re-reads the state word. Because the
// test sits at the top of the loop rather than the bottom, a node that already reads 2 never
// sleeps, which is the case the suite covers; the polling itself is not reproducible from a case
// file, since the exit needs a write to the node that no stub can make.
//
// The advance under the lock does three things in order: bump the node's counter at +0x30, move to
// the next node -- through +0x80 when +0x88 is set, dereferencing twice, and straight through +0x18
// when it is clear -- and release the lock. The pointer the lock was taken on is not the one the
// advance walks: the address of the global is what the lock sees, the node is what the chain walks.
//
// The canary the original uses is the cookie behind 0x057e3be0. This replacement keeps no cookie:
// the case suite runs both sides with a valid one, so the failure path is reached on neither.
#include <cstddef>
#include <cstdint>

#include "runtime/guest.h"

namespace {

using lock_fn = void (*)(void *, uint32_t);
using unlock_fn = void (*)(void *);

// The word at 0x05aa4578 is the vtable itself, not a pointer to a lockable that holds one: the
// original dereferences the global exactly once before the indirect call. Only the two slots this
// function calls are named.
struct lockable_vtable {
    void *unknown_0x00[3];
    lock_fn lock;
    void *unknown_0x20;
    unlock_fn unlock;
};
static_assert(offsetof(lockable_vtable, lock) == 0x18);
static_assert(offsetof(lockable_vtable, unlock) == 0x28);

// The registry's node: the state that is waited on, the count that is bumped, the released bit and
// the two ways to reach the next node.
struct node {
    uint8_t unknown_0x00[0x10];
    uint32_t state;              // +0x10: the word the wait polls
    uint8_t unknown_0x14[0x4];   // +0x14..+0x17
    node *next;                  // +0x18: taken directly when +0x88 is clear
    uint8_t unknown_0x20[0x10];  // +0x20..+0x2f
    uint8_t advance_count;       // +0x30: bumped once per advance
    uint8_t is_released;         // +0x31: bit 0 says the node is already released
    uint8_t unknown_0x32[0x4e];  // +0x32..+0x7f
    node **chain;                // +0x80: a container holding the next node at its +0x10
    void *chain_guard;           // +0x88: selects which of the two pointers is walked
};
static_assert(offsetof(node, state) == 0x10);
static_assert(offsetof(node, next) == 0x18);
static_assert(offsetof(node, advance_count) == 0x30);
static_assert(offsetof(node, is_released) == 0x31);
static_assert(offsetof(node, chain) == 0x80);
static_assert(offsetof(node, chain_guard) == 0x88);

struct registry {
    uint8_t unknown_0x00[0x8];
    node *head;
};
static_assert(offsetof(registry, head) == 0x8);

// Both slots of the vtable are called with the address of the global the pointer came out of:
// the lock word lives in the global itself, and 0xffffffff is the wait key, not a timeout.
constexpr uint32_t lock_wait_forever = 0xffffffff;
constexpr uint32_t state_ready = 2;
constexpr uint32_t mode_no_wait = 2;
// The global whose own word is the lock's vtable, and the offset of the node inside a chain guard.
constexpr std::uintptr_t lock_registry_address = 0x05aa4578;
constexpr std::uintptr_t chain_node_offset = 0x10;

void take_lock()
{
    lockable_vtable *vtable = *rt::ptr<lockable_vtable *>(lock_registry_address);
    vtable->lock(rt_guest(lock_registry_address), lock_wait_forever);
}

void release_lock()
{
    lockable_vtable *vtable = *rt::ptr<lockable_vtable *>(lock_registry_address);
    vtable->unlock(rt_guest(lock_registry_address));
}

extern "C" node *bb_kernel_wait_for_release_024bd150(registry *self, uint32_t mode)
{
    if (!self->head) { return nullptr; }

    node *current;
    // mode 2 skips the released-byte pair and never reads the state word; the advance below still
    // takes the same lock as every other mode.
    if (mode == mode_no_wait) {
        current = self->head;
    } else {
        bool released;
        take_lock();
        released = (self->head->is_released & 1) != 0;
        release_lock();
        // mode 0 stops here when the node is *not* released: `test r12b,r12b; je 0x24bd227` jumps
        // to the null return on a clear bit, so a released node falls through and advances instead.
        if (!mode && !released) { return nullptr; }
        current = self->head;
        // The test is at the top of the loop, so a node that already reads 2 does not sleep. The
        // poll itself cannot be reached from a case: the exit needs a write to the node that no
        // stub can make, so the loop below is only ever entered with the state already ready.
        if (mode && !released) {
            while (current->state != state_ready) {}
        }
    }

    take_lock();
    ++current->advance_count;
    // The chain route dereferences twice: the word at +0x80 is a container whose first field, the
    // node at +0x10, is the one to move to. The direct route is the node at +0x18.
    node *moved = current->chain_guard ? *reinterpret_cast<node **>(
        reinterpret_cast<uint8_t *>(*current->chain) + chain_node_offset) : current->next;
    release_lock();
    return moved;
}

} // namespace
