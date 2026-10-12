// SPDX-License-Identifier: GPL-2.0-or-later
// Frame timing: the current thread's identity, the mutex lock pair and the semaphore triple.
//
// frame_timing_thread_self (0x0111a8a0) writes the calling thread's own identifier to *out and
// returns 0. The value is opaque: the original stores the whole 64-bit return of the import, so
// nothing here may narrow it.
//
// frame_timing_mutex_lock (0x0111acd0) and frame_timing_mutex_unlock (0x0111acf0) are the lock
// pair for the same middleware. Both treat a null mutex as a no-op that returns 0 without calling
// the kernel. Neither passes the kernel's result through: the instruction pair after the call is
// MOV ECX,EAX / TEST ECX,ECX / MOV EAX,0x21 / CMOVE EAX,ECX, so a successful call (eax == 0) keeps
// the zero and any other result is replaced by 0x21. The specific error code is discarded -- the
// reported word is a fixed 0x21, not the kernel's errno. The comparison is on the low 32 bits, so
// an error whose low word is zero would read as success; no case exercises that.
//
// frame_timing_semaphore_delete (0x0111ad80), _wait (0x0111ada0) and _signal (0x0111adc0) wrap the
// libkernel semaphore triple. They report the same way as the mutex pair, by the same three
// instructions with the registers the other way round -- MOV ECX,0x21 / TEST EAX,EAX / CMOVE
// ECX,EAX / MOV EAX,ECX -- so zero stays zero and every nonzero result becomes the fixed 0x21. None
// of the three checks its handle, and none rewrites EAX before the test, so ESI/EDX keep the values
// only _wait and _signal set: wait asks for one unit and passes a null timeout, which waits without
// a deadline rather than returning EAGAIN.
#include <pthread.h>

#include "runtime/original.h"

namespace {

// The executable's call stubs.
RT_ORIGINAL(0x02fbfe78, c_pthread_self, uint64_t());
RT_ORIGINAL(0x2fbfef8, c_pthread_mutex_lock, int(void *mutex));
RT_ORIGINAL(0x2fbff08, c_pthread_mutex_unlock, int(void *mutex));
RT_ORIGINAL(0x2fbec68, kernel_delete_sema, int(uint32_t sem));
RT_ORIGINAL(0x2fbec78, kernel_wait_sema, int(uint32_t sem, int need_count, void *timeout));
RT_ORIGINAL(0x2fbec88, kernel_signal_sema, int(uint32_t sem, int count));

// The reported failure code, as in the clock helpers.
constexpr uint32_t mutex_error = 0x21;

}  // namespace

extern "C" uint64_t bb_frame_timing_thread_self(uint64_t *out)
{
    *out = c_pthread_self();
    return 0;
}

extern "C" uint32_t bb_frame_timing_mutex_lock(void *mutex)
{
    if (mutex == nullptr) return 0;
    const uint32_t result = static_cast<uint32_t>(c_pthread_mutex_lock(mutex));
    return result == 0 ? 0u : mutex_error;
}

extern "C" uint32_t bb_frame_timing_mutex_unlock(void *mutex)
{
    if (mutex == nullptr) return 0;
    const uint32_t result = static_cast<uint32_t>(c_pthread_mutex_unlock(mutex));
    return result == 0 ? 0u : mutex_error;
}

extern "C" uint32_t bb_frame_timing_semaphore_delete(uint32_t sem)
{
    const uint32_t result = static_cast<uint32_t>(kernel_delete_sema(sem));
    return result == 0 ? 0u : mutex_error;
}

extern "C" uint32_t bb_frame_timing_semaphore_wait(uint32_t sem)
{
    const uint32_t result = static_cast<uint32_t>(kernel_wait_sema(sem, 1, nullptr));
    return result == 0 ? 0u : mutex_error;
}

extern "C" uint32_t bb_frame_timing_semaphore_signal(uint32_t sem)
{
    const uint32_t result = static_cast<uint32_t>(kernel_signal_sema(sem, 1));
    return result == 0 ? 0u : mutex_error;
}
