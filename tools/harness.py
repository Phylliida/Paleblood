#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run one function on one captured case, natively, and print a verify.py result case.

usage:
  harness.py --elf EBOOT.elf (--case CASE.json | --cases DIR) --address 0xXXXXXXXX
             [--replacement SYMBOL --lib LIB.so] [--timeout SECONDS]

CONTRACT: stdout is a JSON map keyed by case id, and NOTHING ELSE may appear there. A batch is a
map from id to entry; a single case is one entry. differential.run_original requires
set(stdout) == set(case stems) and refuses anything else as a malformed inventory -- which is how
this rule last caught a per-run field I had stamped at the top level, turning `image_base_set` into
a case name. Per-run facts go on the entries (or stderr); the top level belongs to case ids alone.
Three fields have now been lost to that channel, so it is written here rather than remembered.

The executable (your own dump's eboot.elf) is read by Paleblood's loader (runtime/loader.c,
through build/runtime/libpbloader.so), mapped at the runtime's host address, relocated, and every imported
library function becomes a stub that the case scripts. Game functions listed in the case's
`stubs` are replaced by scripted stubs too (a jump at their entry), on both sides. Without --replacement the original
function at ADDRESS (a PS4 virtual address) runs; with it, SYMBOL from LIB runs after LIB's
bbgame_init (given a loader that installs no hooks). Both see the same memory and the same
scripted library calls. Design and file formats: docs/VERIFY.md.

Prints one JSON object: return value, callee-saved registers, every changed byte of writable
memory, every library call. With --cases, the image is mapped once and every case runs in a
fork of it (a crash or a hang loses only that case); prints {file stem: result}. Runs at low
priority (BB_NICE, default 10). Exits 0, or 3 on bad input.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import struct
import sys

# The four address frames and their conversions are in docs/addressing.md. In short: guest (PS4)
# addresses are 0x400000-based, IMAGE + guest - EBOOT_BASE is the host address the guest image is
# mapped at, boot['loads'] reports offsets into that image (not PS4 addresses), and a file offset in
# eboot.elf is guest - 0x3fc000. Both conversions below are correct as written; changing either to
# "look more symmetric" has already cost two debugging sessions, because a wrong translation here
# manifests as a scripted access reported outside every segment, not as a bad address.
IMAGE = 0x800000000         # host address of guest offset 0, as in the scaffold
EBOOT_BASE = 0x400000       # PS4 virtual address of guest offset 0
SANDBOX = 0x900000000       # case buffers
SANDBOX_SIZE = 16 << 20
DATA = 0x910000000          # data imports, one page each
CODE = 0x920000000          # trampoline and import stubs
PAGE = 4096
STACK_WINDOW = 1 << 20
RUNAWAY = 1000              # unscripted calls before a case is abandoned

PROT_RWX = 7
PROT_NONE = 0
MAP_PRIVATE, MAP_ANONYMOUS, MAP_FIXED_NOREPLACE = 0x02, 0x20, 0x100000

# call_capture(block): see docs/VERIFY.md. Block layout: 0 target, 8..48 rdi..r9, 56 rax,
# 64 rdx, 72 xmm0, 88 xmm1, 104 rbx, 112 rbp, 120 r12, 128 r13, 136 r14, 144 r15,
# 152 rsp before the call, 160 rsp after it. Callee-saved registers hold sentinels. xmm0 and
# xmm1 are loaded from their slots before the call (float arguments) and stored back after it.
# rax is loaded from its slot before the call too, so a case can enter with a value in it: an
# original that clears eax then differs observably from a replacement that does not. A case that
# does not name rax enters with 0, which is what the trampoline used to force unconditionally.
TRAMPOLINE = bytes.fromhex(
    '53554154415541564157574989fb48bb111111111111111148bd222222222222222249bc3333333333333333'
    '49bd444444444444444449be555555555555555549bf66666666666666664989a398000000498b7b08498b73'
    '10498b5318498b4b204d8b43284d8b4b304d8b13f3410f6f4348f3410f6f4b58498b433841ffd24c8b1c24498943'
    '3849895340f3410f7f4348f3410f7f4b5849895b6849896b704d8963784d89ab800000004d89b3880000004d'
    '89bb900000004989a3a00000005f415f415e415d415c5d5bc3')
SENTINELS = {'rbx': 0x1111111111111111, 'rbp': 0x2222222222222222, 'r12': 0x3333333333333333,
             'r13': 0x4444444444444444, 'r14': 0x5555555555555555, 'r15': 0x6666666666666666}
ARG_REGS = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
# Stack arguments (the case's "stack": values for [rsp+8], [rsp+16], ... at the call): the
# trampoline pushes STACK_COUNT qwords from STACK_POINTER (an even count, so the call stays
# aligned) and adds STACK_BYTES to rsp after it. The slots sit in the trampoline's page:
# count, pointer, bytes, entry rax.
STACK_SLOTS = 0x800                         # offset in CODE: count, pointer, bytes, entry rax


def _stack_trampoline(base: bytes) -> bytes:
    call = bytes.fromhex('498b433841ffd2')  # mov rax, [r11+0x38]; call r10 (the base form)
    at = base.index(call)

    def rel(insn_end: int, slot: int) -> bytes:
        return struct.pack('<i', STACK_SLOTS + slot - insn_end)
    code = bytearray(base[:at])
    code += bytes.fromhex('488b05') + rel(len(code) + 7, 0)        # mov rax, [count]
    code += bytes.fromhex('4c8b1d') + rel(len(code) + 7, 8)        # mov r11, [pointer]
    code += bytes.fromhex('4885c0' '7409' '48ffc8' '41ff34c3' 'ebf2')   # push [r11+8*rax], rax..1
    # The push loop spends rax as its counter and r11 as the stack-argument pointer, so the entry
    # rax comes from the state block here rather than from the block the base form reads.
    code += bytes.fromhex('488b05') + rel(len(code) + 7, 24)      # mov rax, [entry rax]
    code += bytes.fromhex('41ffd2')                               # call r10
    code += bytes.fromhex('480325') + rel(len(code) + 7, 16)       # add rsp, [bytes]
    suffix = base[at + len(call):]
    restore_block = bytes.fromhex('4c8b1c24')
    restore_at = suffix.index(restore_block) + len(restore_block)
    # The saved entry rdi is the block pointer restored into r11 here. Caller-saved registers are
    # observations only; comparisons opt in explicitly and otherwise ignore unspecified values.
    observed = bytes.fromhex('4989bba80000004989b3b000000049898bb80000004d8983c00000004d898bc80000004d8993d00000004d899bd8000000')
    suffix = suffix[:restore_at] + observed + suffix[restore_at:]
    return bytes(code) + suffix
# Native stub for series entries (a wait that polls the clock calls it hundreds of thousands of
# times): copies the next 16-byte value to *arg, counts the call, returns the scripted value;
# when the series is used up it jumps to the Python dispatcher. State block: 0 remaining,
# 8 next value, 16 native calls, 24 Python fallback, 32 return value. Variants by argument
# register; the state address replaces 0x1122334455667788.
SERIES_STUB = {
    0: bytes.fromhex('49bb887766554433221149833b00742349ff0b498b43084c8b104c89174c8b50084c895708'
                     '498343081049ff4310498b4320c3498b4318ffe0'),
    1: bytes.fromhex('49bb887766554433221149833b00742349ff0b498b43084c8b104c89164c8b50084c895608'
                     '498343081049ff4310498b4320c3498b4318ffe0'),
}
SERIES = 0x930000000        # per-case native series stubs and their state
# Internal-function stubs enter through a native prologue that saves xmm0 and xmm1 (float
# arguments, compared with "argf32") at +64, then jumps to the Python dispatcher.
XSTUB = 0x940000000
# Library imports enter through a native wrapper (IMPSTUB_SIZE bytes each): it saves xmm0 and
# xmm1 at +64 (float arguments, compared with "argf32"), calls the Python dispatcher and copies
# its result into xmm0 too, so a float return is scripted as its bit pattern ("ret": "0x3f800000").
IMPSTUB = 0x950000000
IMPSTUB_SIZE = 96
XSTUB_SIZE = 96
XMM_SAVE_SLOTS = 2          # both prologues save xmm0 at +64 and xmm1 at +80, and nothing else
_REPORT_FD = None           # the child's result pipe, while a case runs in a forked child


def report_failure(message: str) -> bool:
    """Hand a refusal to the parent as a payload. True if it landed.

    A refusal raised inside a ctypes callback cannot travel as an exception: ctypes
    ignores it and the caller sees zero. `Run.guarded` therefore exits the child itself,
    and it has to report the same way main() does -- as data -- so that exit status 3 has
    exactly one shape on the wire. Printing instead would put the message on stderr twice,
    because the parent raises it back as a BadInput and main() prints that.
    """
    if _REPORT_FD is None:
        return False
    try:
        os.write(_REPORT_FD, json.dumps({'bad_input': message}, sort_keys=True).encode())
    except OSError:
        return False
    return True
ARCH_SET_GS, SYS_ARCH_PRCTL = 0x1001, 158
NID_SALT = bytes.fromhex('518d64a635ded8c1e6b039b1c3e55230')


class BadInput(Exception):
    pass


def nid(name: str) -> str:
    digest = hashlib.sha1(name.encode('ascii') + NID_SALT).digest()[:8][::-1]
    return base64.b64encode(digest).decode().rstrip('=').replace('/', '-')


libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.mprotect.restype = ctypes.c_int
libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]


def mmap_fixed(address: int, size: int) -> None:
    size = (size + PAGE - 1) // PAGE * PAGE
    got = libc.mmap(address, size, PROT_RWX, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0)
    if got != address:
        raise BadInput(f'cannot map 0x{address:x} ({size} bytes): errno {ctypes.get_errno()}')


LOADER_BIND = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int)


def loader_library():
    """runtime's executable loader as a shared library: $BB_LOADER, else the build's."""
    path = os.environ.get('BB_LOADER') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                       'build', 'runtime', 'libpbloader.so')
    if not os.path.isfile(path):
        raise BadInput(f'{path}: build the repository first (the loader is runtime/loader.c)')
    lib = ctypes.CDLL(path)
    lib.rt_elf_open.restype = ctypes.c_void_p
    lib.rt_elf_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    for name in ('rt_elf_image_size', 'rt_elf_entry', 'rt_elf_load_count', 'rt_elf_import_count'):
        getattr(lib, name).restype = ctypes.c_uint64
        getattr(lib, name).argtypes = [ctypes.c_void_p]
    lib.rt_elf_loads.restype = ctypes.POINTER(ctypes.c_uint64)
    lib.rt_elf_loads.argtypes = [ctypes.c_void_p]
    lib.rt_elf_import_name.restype = ctypes.c_char_p
    lib.rt_elf_import_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    lib.rt_elf_map.restype = ctypes.c_int
    lib.rt_elf_map.argtypes = [ctypes.c_void_p, ctypes.c_void_p, LOADER_BIND, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.rt_elf_thread_pointer_to_gs.restype = ctypes.c_size_t
    lib.rt_elf_thread_pointer_to_gs.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    return lib


def open_executable(path: str) -> dict:
    """The executable, read by our loader (runtime/loader.c): sizes, loads and import names; it is
    mapped by Machine."""
    lib = loader_library()
    error = ctypes.create_string_buffer(512)
    handle = lib.rt_elf_open(path.encode(), error, len(error))
    if not handle:
        raise BadInput(error.value.decode(errors='replace'))
    raw = lib.rt_elf_loads(handle)
    loads = []
    for i in range(lib.rt_elf_load_count(handle)):
        # rt_elf_load: vaddr, memsz (u64), flags (u32, padded to 8)
        loads.append((raw[3 * i], raw[3 * i + 1], raw[3 * i + 2] & 0xffffffff))
    names = [lib.rt_elf_import_name(handle, i).decode() for i in range(lib.rt_elf_import_count(handle))]
    return {'size': lib.rt_elf_image_size(handle), 'entry': lib.rt_elf_entry(handle), 'loads': loads, 'names': names,
            'handle': handle, 'loader': lib}


def hexint(v) -> int:
    return v if isinstance(v, int) else int(str(v), 0)


STUB_SLOTS = 64             # internal-function stubs per case


def byte_diffs(old: bytes, new: bytes, chunk: int = 1 << 12) -> list[tuple[int, bytes]]:
    """(offset, new bytes) for each run of differing bytes, in ascending order.

    Comparing every byte in Python was the entire per-case cost: the writable segment alone is
    `memsz 0x5f70f4` = 6.25 MB, and that loop measured 1818 ms against 2.6 ms for one C-level
    comparison of the same two regions. It is not the guest executing -- a 41-byte body costs
    microseconds -- so compare a chunk at a time in C and drop into the byte loop only where a
    chunk differs. Runs stay maximal: the inner scan walks past the chunk boundary, so a run
    spanning chunks is still reported once.
    """
    if old == new:
        return []
    n, runs, i = len(old), [], 0
    while i < n:
        stop = min(i + chunk, n)
        if old[i:stop] == new[i:stop]:
            i = stop
            continue
        while i < stop:
            if old[i] == new[i]:
                i += 1
                continue
            end = i
            while end < n and old[end] != new[end]:
                end += 1
            runs.append((i, new[i:end]))
            i = end
    return runs


class Machine:
    """The image mapped and relocated once, import stubs in place. Library calls dispatch to
    the current Run, so cases can share one mapping (each runs in its own fork)."""

    def __init__(self, boot: dict):
        self.boot = boot
        self.current: 'Run | None' = None
        self.callbacks = []
        b = boot
        mmap_fixed(IMAGE, b['size'])
        mmap_fixed(SANDBOX, SANDBOX_SIZE)
        mmap_fixed(XSTUB, STUB_SLOTS * XSTUB_SIZE)
        names = b['names']
        mmap_fixed(DATA, max(1, len(names)) * PAGE)
        mmap_fixed(CODE, PAGE + 16 * (max(1, len(names)) + STUB_SLOTS))
        code = _stack_trampoline(TRAMPOLINE)
        assert len(code) < STACK_SLOTS
        ctypes.memmove(CODE, code, len(code))
        self.proto = ctypes.CFUNCTYPE(ctypes.c_uint64, *[ctypes.c_uint64] * 6)
        mmap_fixed(IMPSTUB, max(1, len(names)) * IMPSTUB_SIZE)
        for i in range(len(names)):
            cb = self.proto(lambda a, b_, c, d, e, f, i=i:
                            self.current.guarded(self.current.dispatch, i, (a, b_, c, d, e, f)))
            self.callbacks.append(cb)
            wrapper = IMPSTUB + IMPSTUB_SIZE * i
            save = wrapper + 64
            # movabs r11, save; movdqu [r11], xmm0; movdqu [r11+16], xmm1; sub rsp, 8;
            # movabs rax, cb; call rax; add rsp, 8; movq xmm0, rax; ret
            code = (b'\x49\xbb' + struct.pack('<Q', save) + b'\xf3\x41\x0f\x7f\x03' + b'\xf3\x41\x0f\x7f\x4b\x10' +
                    b'\x48\x83\xec\x08' + b'\x48\xb8' + struct.pack('<Q', ctypes.cast(cb, ctypes.c_void_p).value) +
                    b'\xff\xd0' + b'\x48\x83\xc4\x08' + b'\x66\x48\x0f\x6e\xc0' + b'\xc3')
            ctypes.memmove(wrapper, code, len(code))
            stub = b'\x48\xb8' + struct.pack('<Q', wrapper) + b'\xff\xe0'
            ctypes.memmove(CODE + PAGE + 16 * i, stub, len(stub))
        # Our loader copies the segments in, applies every relocation (imported functions go to
        # their stubs, imported data to its page) and changes the executable's thread-pointer
        # loads to read GS, where a case's "gs" points.
        def bind(_user, index, kind):
            return DATA + PAGE * index if kind == 1 else CODE + PAGE + 16 * index
        self.bind = LOADER_BIND(bind)
        error = ctypes.create_string_buffer(512)
        if b['loader'].rt_elf_map(b['handle'], IMAGE, self.bind, None, error, len(error)):
            raise BadInput(error.value.decode(errors='replace'))
        b['loader'].rt_elf_thread_pointer_to_gs(b['handle'], IMAGE)


class Run:
    def __init__(self, boot: dict, case: dict):
        self.boot, self.case = boot, case
        self.calls: list[dict] = []
        self.errors: list[str] = []
        self.block = (ctypes.c_uint64 * 28)()
        self.scripts: dict[str, list] = {}
        for entry in case.get('imports', []):
            self.scripts.setdefault(nid(entry['name']), []).append(entry)
        self.buffers: dict[str, tuple[int, int]] = {}
        self.redzones: list[tuple[int, bytes, str]] = []
        self.access_trace: list[dict] = []
        self.callbacks = []
        self.native: dict[int, dict] = {}      # import index -> series stub state
        self.keep = []
        self.stub_scripts: dict[int, list] = {}
        for entry in case.get('stubs', []):
            self.stub_scripts.setdefault(hexint(entry['address']), []).append(entry)

    # memory layout ---------------------------------------------------------------------
    def setup(self, machine: 'Machine') -> None:
        """Lay out this case on a mapped machine: buffers, stubs, memory presets."""
        machine.current = self
        names = self.boot['names']
        proto = machine.proto
        series_imports = []
        for i, raw in enumerate(names):
            entries = self.scripts.get(raw.split('#')[0], [])
            args = {int(e['series']['arg']) for e in entries if 'series' in e}
            if args and args <= {0, 1} and len(args) == 1:
                series_imports.append((i, args.pop()))
        if series_imports:
            mmap_fixed(SERIES, PAGE * (1 + len(series_imports) // 32))
            for n, (i, arg) in enumerate(series_imports):
                state = SERIES + 128 * n
                code = state + 48
                ctypes.memmove(state, bytes(48), 48)
                ctypes.memmove(state + 24, struct.pack('<Q', ctypes.cast(machine.callbacks[i], ctypes.c_void_p).value), 8)
                stub = SERIES_STUB[arg].replace(struct.pack('<Q', 0x1122334455667788), struct.pack('<Q', state))
                ctypes.memmove(code, stub, len(stub))
                jump = b'\x48\xb8' + struct.pack('<Q', code) + b'\xff\xe0'
                ctypes.memmove(CODE + PAGE + 16 * i, jump, len(jump))
                self.native[i] = {'state': state, 'record': None}
        if len(self.stub_scripts) > STUB_SLOTS:
            raise BadInput(f'more than {STUB_SLOTS} stubbed functions')
        off = 0
        for name in sorted(self.case.get('buffers', {})):
            spec = self.case['buffers'][name]
            size = int(spec['size'])
            if size < 0 or size > SANDBOX_SIZE:
                raise BadInput(f'buffer {name}: size is outside the sandbox limit')
            data = bytes.fromhex(spec.get('bytes', ''))
            if len(data) > size:
                raise BadInput(f'buffer {name}: more bytes than its size')
            start = SANDBOX + off
            self.buffers[name] = (start, size)
            ctypes.memmove(start, data + bytes(size - len(data)), size)
            payload_pages = max(1, (size + PAGE - 1) // PAGE)
            redzone_start = start + size
            redzone_end = start + payload_pages * PAGE
            if redzone_end > redzone_start:
                redzone = bytes((0xA5 ^ ((i * 29 + len(name)) & 0xff)) for i in range(redzone_end - redzone_start))
                ctypes.memmove(redzone_start, redzone, len(redzone))
                self.redzones.append((redzone_start, redzone, name))
            guard = start + payload_pages * PAGE
            if off + (payload_pages + 1) * PAGE > SANDBOX_SIZE:
                raise BadInput('buffers and guard pages exceed the sandbox')
            if libc.mprotect(guard, PAGE, PROT_NONE):
                raise BadInput(f'cannot install guard page after buffer {name}: errno {ctypes.get_errno()}')
            off += (payload_pages + 1) * PAGE
        for i, address in enumerate(sorted(self.stub_scripts)):
            save = XSTUB + XSTUB_SIZE * i + 64
            cb = proto(lambda a, b_, c, d, e, f, address=address, save=save:
                       self.guarded(self.dispatch_stub, address, (a, b_, c, d, e, f), save))
            self.callbacks.append(cb)
            code = XSTUB + XSTUB_SIZE * i
            # movabs r11, save; movdqu [r11], xmm0; movdqu [r11+16], xmm1; sub rsp, 8;
            # movabs rax, cb; call rax; add rsp, 8; movq xmm0, rax; ret (a float return is
            # scripted as its bit pattern, as for imports)
            stub = (b'\x49\xbb' + struct.pack('<Q', save) + b'\xf3\x41\x0f\x7f\x03' + b'\xf3\x41\x0f\x7f\x4b\x10' +
                    b'\x48\x83\xec\x08' + b'\x48\xb8' + struct.pack('<Q', ctypes.cast(cb, ctypes.c_void_p).value) +
                    b'\xff\xd0' + b'\x48\x83\xc4\x08' + b'\x66\x48\x0f\x6e\xc0' + b'\xc3')
            ctypes.memmove(code, stub, len(stub))
            jump = b'\xff\x25\x00\x00\x00\x00' + struct.pack('<Q', code)
            ctypes.memmove(self.guest(address), jump, len(jump))
        if 'gs' in self.case:
            # The guest thread pointer (gs:[0] must hold it too, as a TCB does).
            if libc.syscall(SYS_ARCH_PRCTL, ARCH_SET_GS, ctypes.c_ulong(self.value(self.case['gs']))):
                raise BadInput(f'arch_prctl(ARCH_SET_GS) failed: errno {ctypes.get_errno()}')
        writes = []
        for m in fixture_seeds(self.case):
            target = m['addr']
            addr = self.value(target) if isinstance(target, str) and target.startswith('buf:') else self.guest(hexint(target))
            if 'pointer' in m:
                data = struct.pack('<Q', self.value(f"buf:{m['pointer']}"))
            elif 'guest' in m:
                data = struct.pack('<Q', self.guest(hexint(m['guest'])))
            else:
                data = bytes.fromhex(m['bytes'])
            self.check_memory(addr, len(data), write=True, source="fixture_setup")
            ctypes.memmove(addr, data, len(data))
            writes.append((addr, data))
        # THE READ-BACK, once per body and before it runs. A write is a claim; what the body reads is the
        # state. If a seed misses -- wrong guest() arithmetic, a slot outside the mapping, a case applied
        # to a stale image -- the body reads zero, stores to 0 + K2, and the differential then compares two
        # zero-filled tails and lands the row green. A static gate on the case FILE cannot see any of that.
        miss = read_back_mismatch(lambda a, n: ctypes.string_at(a, n), writes)
        if miss is not None:
            addr, want, got = miss
            raise BadInput(f'fixture seed did not land at 0x{addr:x}: expected {want.hex()}, read back '
                           f'{got.hex()} -- refusing before the body runs; a seed that misses reads zero')

    def guest(self, ps4: int) -> int:
        '''PS4 address -> host address. The `- EBOOT_BASE` belongs here and nowhere else: it is
        what turns the game's 0x400000-based addresses into offsets into the mapped image.'''
        if not EBOOT_BASE <= ps4 < EBOOT_BASE + self.boot['size']:
            raise BadInput(f'0x{ps4:x} is outside the image')
        return IMAGE + ps4 - EBOOT_BASE

    def value(self, v) -> int:
        if isinstance(v, str) and v.startswith('buf:'):
            name, _, off = v[4:].partition('+')
            if name not in self.buffers:
                raise BadInput(f'unknown buffer {name}')
            offset = int(off, 0) if off else 0
            if offset < 0 or offset > self.buffers[name][1]:
                raise BadInput(f'pointer {v} is outside its declared buffer')
            return self.buffers[name][0] + offset
        if isinstance(v, str) and v.startswith('guest:'):
            return self.guest(int(v[6:], 0))
        return hexint(v) & 0xffffffffffffffff

    def check_memory(self, address: int, size: int, write: bool = False,
                     source: str = "scripted_callback") -> None:
        """Validate an observed harness-mediated access against declared regions.

        This records accesses made by scripted imports/stubs and fixture setup. It does not
        instrument arbitrary guest load/store instructions; those remain an explicit limitation.
        """
        if size < 0:
            raise BadInput('negative memory access size')
        for start, length in self.buffers.values():
            if start <= address and address + size <= start + length:
                if source != "fixture_setup":
                    self.access_trace.append({"access": "write" if write else "read",
                                              "address": self.describe(address), "size": size,
                                              "source": source, "region": self.describe(start)})
                return
        stack_top = self.block[19]
        if stack_top and stack_top - STACK_WINDOW <= address and address + size <= stack_top:
            if source != "fixture_setup":
                self.access_trace.append({"access": "write" if write else "read",
                                          "address": self.describe(address), "size": size,
                                          "source": source, "region": "stack"})
            return
        required_flag = 2 if write else 4
        # A preset is the harness laying out the case, not an access the program makes, so the
        # segment's permission bits (which describe what the guest may do) do not constrain it:
        # a case that scripts the constants at 0x04ccbb20 has to write them into the read+execute
        # segment. The address must still land inside a loaded segment, so `memory` cannot reach
        # anywhere the guest could not name.
        fixture = source == "fixture_setup"
        # boot['loads'] reports vaddrs as offsets from the image base, not PS4 addresses:
        # 0x050dc000 + 0x005f70f4 is exactly boot['size'], and 0x04ccbb20 lives in the first
        # segment's range. So they are used here as offsets into IMAGE, the same space `address`
        # is already in.
        for vaddr, memsz, flags in self.boot['loads']:
            segment = IMAGE + vaddr
            if (fixture or flags & required_flag) and segment <= address and address + size <= segment + memsz:
                if source != "fixture_setup":
                    self.access_trace.append({"access": "write" if write else "read",
                                              "address": self.describe(address), "size": size,
                                              "source": source, "region": "guest_image"})
                return
        direction = 'write' if write else 'read'
        # describe() names the address as a case author wrote it (guest address, buffer offset or
        # stack), so the message points at the case line rather than at an internal host address.
        raise BadInput(f'scripted {direction} {self.describe(address)}+0x{size:x} '
                       f'is outside declared readable/writable regions')

    def normalised(self, v: int) -> int:
        """Map a host address inside the mapped image back to its guest address.

        This is a *value* conversion, not a display one: the original runs in the host mapping
        and a computed pointer lands at IMAGE + (guest - EBOOT_BASE), while a replacement gets
        no such mapping and returns the guest address directly. Comparison must see one space,
        so the conversion happens here and produces an int. describe() then renders it for
        humans -- a comparison must never be built from a display format.
        """
        if IMAGE <= v < IMAGE + self.boot['size']:
            return v - IMAGE + EBOOT_BASE
        return v

    def describe(self, v: int) -> str:
        top = self.block[19]
        if top and top - STACK_WINDOW <= v <= top:
            return 'stack'
        if IMAGE <= v < IMAGE + self.boot['size']:
            return f'0x{v - IMAGE + EBOOT_BASE:08x}'
        for name, (start, size) in self.buffers.items():
            if start <= v < start + size:
                return f'buf:{name}+0x{v - start:x}'
        return f'0x{v:x}'

    # library calls ---------------------------------------------------------------------
    def finish_series(self, index: int) -> None:
        """Fold the calls a native series stub served into the record of its first call."""
        n = self.native.get(index)
        if n and n['record'] is not None:
            served = ctypes.c_uint64.from_address(n['state'] + 16).value
            n['record']['count'] = 1 + served
            ctypes.c_uint64.from_address(n['state'] + 16).value = 0
            ctypes.c_uint64.from_address(n['state']).value = 0
            n['record'] = None

    def guarded(self, call, *args) -> int:
        """Run a scripted call, turning an exception into an exit status.

        ctypes does not propagate an exception out of a callback: it prints "Exception ignored on
        calling ctypes callback function" and hands the caller zero. So a BadInput raised inside
        a scripted write or a series entry -- a write target outside every declared region, a
        register named as a target, a malformed series -- used to leave a clean-looking result
        and exit status 0, and the comparison then covered two runs that never made the write.
        The message is the evidence, so it is handed to the parent as the payload main() would
        write for the same refusal, and the parent prints it once. Status 3 means one thing.
        """
        try:
            return call(*args)
        except BaseException as exception:          # ctypes would swallow this and return zero
            if not report_failure(f'{exception}'):
                # No pipe: a Run built outside a forked child (a unit test, a direct run_case
                # call). Stderr is then the only channel there is.
                print(f'harness: {exception}', file=sys.stderr)
            os._exit(3)

    def saved_xmm(self, save: int, index) -> str:
        '''The 32-bit pattern of an xmm register a prologue saved at `save`.

        Both native prologues save xmm0 and xmm1 and nothing else, so an index past the
        last one would read the following trampoline slot: bytes no case set, equal on both
        sides by construction, which compares clean and reports nothing. Refusing it is the
        only way that mistake is visible.
        '''
        r = int(index)
        if not 0 <= r < XMM_SAVE_SLOTS:
            raise BadInput(f'argf32 index {r} names no saved register: '
                           f'only xmm0 and xmm1 are saved (0 <= index < {XMM_SAVE_SLOTS})')
        return ctypes.string_at(save + 16 * r, 4).hex()

    def dispatch(self, index: int, args: tuple) -> int:
        self.finish_series(index)
        raw = self.boot['names'][index]
        key = raw.split('#')[0]
        queue = self.scripts.get(key)
        if not queue:
            self.errors.append(f'unscripted library call {raw}')
            if len(self.errors) > RUNAWAY:
                # The function keeps calling past its script (a wait that never ends): stop now.
                print(f'harness: {RUNAWAY} unscripted calls; the function does not finish on this case',
                      file=sys.stderr)
                os._exit(4)
            self.calls.append({'import': raw, 'args': []})
            return 0
        entry = queue[0]
        series = entry.get('series')
        if series:
            # One entry for many consecutive calls: each call writes the next value.
            i = entry.setdefault('_next', 0)
            entry['_next'] = i + 1
            if entry['_next'] >= len(series['values']):
                queue.pop(0)
        else:
            queue.pop(0)
        argc = int(entry.get('argc', 0))
        self.calls.append({'import': entry['name'], 'args': [self.describe(a) for a in args[:argc]]})
        if entry.get('argf32'):
            save = IMPSTUB + IMPSTUB_SIZE * index + 64
            self.calls[-1]['argf32'] = [self.saved_xmm(save, r) for r in entry['argf32']]
        if series:
            if series.get('format') != 'timeval_us' or int(series.get('offset', 0)):
                raise BadInput(f"unsupported series {series.get('format')} at offset {series.get('offset', 0)}")
            pack = lambda v: struct.pack('<qq', int(v) // 1_000_000, int(v) % 1_000_000)
            self.check_memory(args[int(series['arg'])], 16, write=True, source="import_series")
            ctypes.memmove(args[int(series['arg'])], pack(series['values'][i]), 16)
            ret = hexint(entry.get('ret', 0)) & 0xffffffffffffffff
            n = self.native.get(index)
            rest = series['values'][i + 1:]
            if n and rest:
                # The native stub serves the rest of this series without coming back here.
                buf = ctypes.create_string_buffer(b''.join(pack(v) for v in rest))
                self.keep.append(buf)
                ctypes.memmove(n['state'], struct.pack('<QQQ', len(rest), ctypes.addressof(buf), 0), 24)
                ctypes.memmove(n['state'] + 32, struct.pack('<Q', ret), 8)
                n['record'] = self.calls[-1]
                if queue and queue[0] is entry:
                    queue.pop(0)
            return ret
        for w in entry.get('writes', []):
            self.scripted_write(w, args, "import_write", entry['name'])
        return hexint(entry.get('ret', 0)) & 0xffffffffffffffff

    def dispatch_stub(self, address: int, args: tuple, save: int = 0) -> int:
        queue = self.stub_scripts.get(address)
        name = f'0x{address:08x}'
        if not queue:
            self.errors.append(f'unscripted call to stubbed function {name}')
            self.calls.append({'call': name, 'args': []})
            return 0
        entry = queue.pop(0)
        picks = entry.get('argi', list(range(int(entry.get('argc', 0)))))
        record = {'call': name, 'args': [self.describe(args[i]) for i in picks]}
        for r in entry.get('argf32', []):
            # Float arguments: xmm0 / xmm1 as their 32-bit pattern.
            record.setdefault('argf32', []).append(self.saved_xmm(save, r))
        for m in entry.get('argmem', []):
            at = args[int(m['arg'])] + int(m.get('offset', 0))
            self.check_memory(at, int(m['size']), source="stub_argument")
            record.setdefault('argmem', []).append(ctypes.string_at(at, int(m['size'])).hex())
        self.calls.append(record)
        for w in entry.get('writes', []):
            # What the real function stored through a pointer argument (e.g. a constructor), or,
            # when the case names a target, at an address it is not handed a pointer to.
            self.scripted_write(w, args, "stub_write", name)
        return self.value(entry.get('ret', 0))

    def scripted_write(self, w: dict, args: tuple, source: str, who: str) -> None:
        """One scripted write, addressed either through a pointer argument or by the case.

        `target` names memory the case laid out ('buf:NAME+0x10' or 'guest:0x...'), for a
        function that changes state it receives no pointer to -- a sleep whose only argument is
        a count. Without it the write goes through `args[arg] + offset`, which is how a store
        through a caller's pointer is scripted.

        A register is never a target: which register holds a pointer is the compiler's choice,
        so a case naming one would describe one implementation and not the other. The address a
        write resolved to is recorded per call (`scripted_write_targets`) instead of being
        folded into the observed write diff, because two faithful implementations may reach the
        same address by different arithmetic and that is a thing to report, not a byte-level
        disagreement to hide in. It is named with describe(), so a write through a stack pointer
        reads as 'stack' rather than as an offset: the absolute address differs between the two
        sides by construction, and a wrong stack target is caught where it lands, not here.
        """
        if 'pointer' in w:
            data = struct.pack('<Q', self.value(f"buf:{w['pointer']}"))
        elif 'guest' in w:
            data = struct.pack('<Q', self.guest(hexint(w['guest'])))
        else:
            data = bytes.fromhex(w['bytes'])
        if 'size' in w and len(data) != int(w['size']):
            self.errors.append(f"{who}: write of {len(data)} bytes, the case says {w['size']}")
        if 'target' in w:
            text = str(w['target'])
            if not text.startswith(('buf:', 'guest:')):
                raise BadInput(f"scripted write target {text!r} must be 'buf:NAME+OFF' or "
                               f"'guest:0xADDR': a register is not a target, because which register "
                               f"holds a pointer is the compiler's choice and two faithful "
                               f"implementations may differ")
            address = self.value(text)
        else:
            address = args[int(w['arg'])] + int(w.get('offset', 0))
        self.check_memory(address, len(data), write=True, source=source)
        ctypes.memmove(address, data, len(data))
        self.calls[-1].setdefault('scripted_write_targets', []).append(self.describe(address))

    # execution -------------------------------------------------------------------------
    def snapshot(self) -> dict[int, bytes]:
        regions = {}
        for vaddr, memsz, flags in self.boot['loads']:
            if flags & 2:
                regions[IMAGE + vaddr] = ctypes.string_at(IMAGE + vaddr, memsz)
        for start, size in self.buffers.values():
            regions[start] = ctypes.string_at(start, size)
        return regions

    def run(self, target: int) -> dict:
        args = self.case.get('args', {})
        unknown = set(args) - set(ARG_REGS) - {'xmm0', 'xmm1', 'rax'}
        if unknown:
            raise BadInput(f'unknown argument registers {sorted(unknown)}')
        observed = self.case.get('observe_registers', [])
        allowed = {'rax', 'rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9', 'r10', 'r11'}
        if not isinstance(observed, list) or any(reg not in allowed for reg in observed):
            raise BadInput('observe_registers must list caller-saved GPR names supported by the harness')
        stack = [self.value(v) for v in self.case.get('stack', [])]
        if len(stack) % 2:
            stack.append(0)
        self.stack = (ctypes.c_uint64 * max(1, len(stack)))(*stack)
        ctypes.memmove(CODE + STACK_SLOTS, struct.pack('<QQQQ', len(stack), ctypes.addressof(self.stack),
                                                       8 * len(stack), self.value(args.get('rax', 0))), 32)
        self.block[0] = target
        for i, reg in enumerate(ARG_REGS):
            self.block[1 + i] = self.value(args.get(reg, 0))
        for reg, off in (('xmm0', 72), ('xmm1', 88)):
            raw = bytes.fromhex(args.get(reg, '')).ljust(16, b'\0')[:16]
            ctypes.memmove(ctypes.addressof(self.block) + off, raw, 16)
        # Declared address slots. A function that STORES a pointer writes an address into memory,
        # and the two sides disagree about which space that address is in for one honest reason:
        # the original executes inside the host mapping (IMAGE + guest - EBOOT_BASE) and the
        # replacement does not. `normalised()` corrects exactly that for return values and there
        # was no equivalent on the memory channel, so a correct replacement failed. A slot is
        # declared per case, compared on its own, and translated on the ORIGINAL side only -- a
        # replacement that stores an image-space address must still fail. The slot carries its own
        # full before/after bytes rather than being reconstructed from a write diff: a diff run can
        # be shorter than the slot (a stored byte that equals the seed's), and a partial run cannot
        # be decoded back into a value.
        slots = []
        for spec in self.case.get('guest_address_slots') or []:
            if not isinstance(spec, dict) or 'addr' not in spec:
                raise BadInput('guest_address_slots entries are {"addr": ..., "width": 8}')
            width = int(spec.get('width', 8))
            if width not in (4, 8):
                raise BadInput(f'guest_address_slots width {width}: only 4 and 8 can hold a pointer')
            at = self.value(spec['addr'])
            self.check_memory(at, width, source='guest_address_slot')
            slots.append((str(spec['addr']), at, width))
        slot_before = {spec: ctypes.string_at(at, w).hex() for spec, at, w in slots}
        before = self.snapshot()
        ctypes.CFUNCTYPE(None, ctypes.c_void_p)(CODE)(ctypes.addressof(self.block))
        for index in self.native:
            self.finish_series(index)
        after = self.snapshot()
        redzone_writes = []
        for start, expected, name in self.redzones:
            actual = ctypes.string_at(start, len(expected))
            changed = [i for i, (old, new) in enumerate(zip(expected, actual)) if old != new]
            if changed:
                redzone_writes.append({"buffer": name, "first_offset": self.buffers[name][1] + changed[0],
                                       "changed_bytes": len(changed)})
        out: dict = {'id': self.case.get('id', 'case')}
        returns = self.case.get('returns', 'i64')
        rax, rdx = self.block[7], self.block[8]
        xmm0 = bytes(ctypes.string_at(ctypes.addressof(self.block) + 72, 16))
        xmm1 = bytes(ctypes.string_at(ctypes.addressof(self.block) + 88, 16))
        ret = {'i8': {'rax': rax & 0xff},
               'i32': {'rax': rax & 0xffffffff},
               'i64': {'rax': self.normalised(rax)},
               'i128': {'rax': rax, 'rdx': rdx},
               'f32': {'xmm0': xmm0[:4].hex()},
               'f64': {'xmm0': xmm0[:8].hex()},
               'vec': {'xmm0': xmm0.hex(), 'xmm1': xmm1.hex()},
               'void': {}}.get(returns)
        if ret is None:
            raise BadInput(f'unknown returns type {returns}')
        out['ret'] = ret
        regs = dict(zip(SENTINELS, self.block[13:19]))
        out['preserved'] = {r: 'kept' if regs[r] == SENTINELS[r] else f'0x{regs[r]:x}' for r in SENTINELS}
        out['preserved']['rsp'] = 'kept' if self.block[20] == self.block[19] else 'unbalanced'
        register_values = {
            'rax': f'0x{self.block[7]:x}',
            'rdi': f'0x{self.block[21]:x}', 'rsi': f'0x{self.block[22]:x}',
            'rdx': f'0x{self.block[8]:x}',
            'rcx': f'0x{self.block[23]:x}', 'r8': f'0x{self.block[24]:x}',
            'r9': f'0x{self.block[25]:x}', 'r10': f'0x{self.block[26]:x}',
            'r11': f'0x{self.block[27]:x}',
        }
        out['observed_registers'] = sorted(set(observed))
        out['registers'] = {reg: register_values[reg] for reg in out['observed_registers']}
        writes = []
        for start, old in before.items():
            for offset, data in byte_diffs(old, after[start]):
                at = start + offset
                if any(s_at <= at and at + len(data) <= s_at + w for _, s_at, w in slots):
                    continue    # compared through the slot channel, in guest space, below
                writes.append({'addr': self.describe(at), 'bytes': data.hex()})
        slot_records = {}
        for spec, at, width in slots:
            data = ctypes.string_at(at, width)
            if SIDE == 'original':
                value = self.normalised(int.from_bytes(data, 'little'))
                data = value.to_bytes(width, 'little')
            slot_records[spec] = {'before': slot_before[spec], 'after': data.hex()}
        out['guest_address_slots'] = slot_records
        out['writes'] = writes
        out['access_trace'] = self.access_trace
        out['access_trace_scope'] = "harness-mediated scripted accesses; guest instructions are not instrumented"
        out['redzone_writes'] = redzone_writes
        if redzone_writes:
            out.setdefault('errors', []).append('buffer redzone modified: ' + json.dumps(redzone_writes, sort_keys=True))
        out['calls'] = self.calls
        if self.errors:
            out['errors'] = self.errors
        return out


def _mapping_perms(addr: int) -> str:
    """The permission string of the mapping containing ADDR, or '' when none does.

    A wrong-type or read-only symbol is otherwise indistinguishable from a writable one until the
    write: one fixture segfaulted the interpreter proving it. Reading the mapping is the same
    mechanism the plugin's region_is_executable uses, applied to the other permission.
    """
    with open('/proc/self/maps') as fh:
        for line in fh:
            fields = line.split()
            lo, hi = (int(x, 16) for x in fields[0].split('-'))
            if lo <= addr < hi:
                return fields[1]
    return ''


def load_replacement(lib_path: str, symbol: str, size: int):
    # RETURNS (address, image_base_set). A function attribute would be a per-comparison fact stored
    # per-process: load a based library, then a plain one, and it still reads True from the previous
    # call -- capture_ok.csv's shape in miniature. The fact is bound to the library it describes.
    """dlopen the game library, run its bbgame_init with a loader that installs no hooks, and
    return the address of SYMBOL."""
    lib = ctypes.CDLL(lib_path)
    # The guest load base the generated leaf bodies read (game/leaf/rip_load_family.cpp). Set ONCE
    # here, where the library is loaded -- not per case: 161 chances to forget, and forgetting
    # faults on the dereference instead of mismatching, which reads as a harness bug. Asserted
    # immediately, because a setter that silently failed and a body reading zero are the same
    # fault one frame apart. IMAGE is this harness's own mapping, so these bodies are honest only
    # under it; their default of 0 is the in-game value (Map is identity or refusal).
    # THE SUBJECT IS THE LIBRARY THAT CONTAINS THE BODY, not "every library dlopened here". This
    # function is called with argument-supplied fixture libraries too (test_harness's
    # libnomatch/libplain), which carry no based body and legitimately export no base; refusing
    # them reddened twelve tests over a property they do not have. Absent therefore records
    # image_base_set = False -- the run says which condition it established instead of the reader
    # reconstructing it from a fault -- and a based body compared under a False base faults on the
    # dereference, which is the loud failure we want and is now readable in the record.
    #
    # THREE VALUES, NOT TWO. 'n/a' means this library exports no base at all -- fixture libraries,
    # and every family that reads no guest constant: nothing to set, nothing claimed. True means the
    # symbol exists, took IMAGE, and read back. A symbol that EXISTS and does not take IMAGE is a
    # refusal, never a False: `image_base_set: false` beside a based body is the sentence "this
    # green is about an instrument", which is what this flag exists to make unsayable, and a single
    # False for both meanings records a failure as if it were a fact about the body.
    # Existence is decided by dlsym -- a mechanism independent of the call that can fail -- because
    # in_dll raising ValueError cannot distinguish "no such symbol" from "symbol present, read or
    # slot failed", and those are opposite facts that were sharing one value.
    libdl = ctypes.CDLL('libdl.so.2', use_errno=True)
    libdl.dlsym.restype = ctypes.c_void_p
    libdl.dlsym.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    sym = libdl.dlsym(ctypes.c_void_p(lib._handle), b'pbl_image_base')
    if not sym:
        base_set = 'n/a'
    else:
        # WRITABILITY IS CHECKED BEFORE THE WRITE, because the check I wrote first did not exist:
        # a fixture exporting `void pbl_image_base(void)` made in_dll hand back a c_uint64 bound to
        # the function's CODE, and assigning it killed the process with SIGSEGV rather than raising
        # ValueError. A symbol of the wrong type, or a const in .rodata, is a refusal -- and it has
        # to be decided from the mapping, which is a mechanism independent of the write it guards.
        perms = _mapping_perms(int(sym))
        if 'w' not in perms:
            raise BadInput(f'pbl_image_base at {int(sym):#x} is exported but not writable '
                           f'(mapping {perms or "not mapped"}); refusing to write it')
        pbl = ctypes.c_uint64.in_dll(lib, 'pbl_image_base')
        pbl.value = IMAGE
        if pbl.value != IMAGE:
            raise BadInput(f'pbl_image_base did not take IMAGE: {pbl.value:#x}')
        base_set = True
    # THE GUARD THAT OUTLIVES THE PROBE (the temporary probe is retired here). The flag
    # `base_set` proves a WRITE at the moment of writing; this proves the VALUE at the moment of
    # USE, in the same process that dispatches, after the call that could silently undo it.
    # stderr, never stdout: harness.py's stdout is a JSON map keyed by case id and nothing else
    # may appear there -- a probe on stdout broke every case with `Expecting value: line 1`.
    def _check_base_after_init():
        if base_set is True and pbl.value != IMAGE:
            raise BadInput(
                'pbl_image_base is %#x after bbgame_init, expected IMAGE %#x (pid %d): the base '
                'that was set did not survive the call it was set for' % (pbl.value, IMAGE, os.getpid()))
        sys.stderr.write('boundary: pid=%d base_set=%s pbl_image_base=%#x IMAGE=%#x\n' % (
            os.getpid(), base_set, pbl.value if base_set is True else 0, IMAGE))
    hook = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_void_p)(lambda o, s, t: 0)
    load_replacement.keep = (lib, hook)

    class Host(ctypes.Structure):
        _fields_ = [('version', ctypes.c_uint32), ('image', ctypes.c_void_p),
                    ('image_size', ctypes.c_uint64), ('install_hook', ctypes.c_void_p)]
    host = Host(1, IMAGE, size, ctypes.cast(hook, ctypes.c_void_p).value)
    if lib.bbgame_init(ctypes.byref(host)):
        raise BadInput('bbgame_init failed')
    _check_base_after_init()
    try:
        return ctypes.cast(getattr(lib, symbol), ctypes.c_void_p).value, base_set
    except AttributeError:
        # Without this, a library that does not export SYMBOL surfaces as an opaque `exit 1` from
        # the child process, which reads as a fault rather than as a build that is missing the
        # replacement. Name it: a wrong --lib or a stale build should never look like behaviour.
        raise BadInput(f'{os.path.basename(lib_path)} does not export {symbol}: the replacement is '
                       'not in this library (build the repository, or pass the right --lib)')


def run_case(machine: Machine, case: dict, address: str, target: int | None) -> dict:
    if case.get('address') != address:
        raise BadInput(f'case is for {case.get("address")}, not {address}')
    run = Run(machine.boot, case)
    run.setup(machine)
    return run.run(target if target is not None else run.guest(int(address, 0)))


def _trace_import_targets(boot: dict, case: dict) -> list[dict]:
    """Describe generated import bridges so an out-of-range edge names its external call."""
    scripted_names = {nid(entry["name"]): entry["name"] for entry in case.get("imports", [])}
    targets = []
    for index, raw in enumerate(boot["names"]):
        symbol = raw.split("#", 1)[0]
        targets.append({"name": scripted_names.get(symbol, symbol),
                        "entry": CODE + PAGE + 16 * index,
                        "entry_end": CODE + PAGE + 16 * index + 16,
                        "wrapper": IMPSTUB + IMPSTUB_SIZE * index,
                        "wrapper_end": IMPSTUB + IMPSTUB_SIZE * (index + 1)})
    return targets


SIDE = 'original'   # who is executing: 'original' runs relocated inside the host mapping, and a
                    # pointer IT computes lands in image space. Set before the fork in
                    # _run_isolated; the default is the original, which is the conservative side.


def _run_isolated(machine: Machine, case: dict, address: str, target: int | None,
                  timeout: int, trace: bool, trace_limit: int, replacement_lib: str | None) -> dict:
    global SIDE
    SIDE = 'replacement' if replacement_lib else 'original'
    import signal
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        global _REPORT_FD
        os.close(r)
        _REPORT_FD = w
        signal.alarm(timeout)
        try:
            if trace:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import instruction_trace
                instruction_trace.trace_me()
            result = run_case(machine, case, address, target)
            code = 0
        except BadInput as error:
            result, code = {'bad_input': str(error)}, 3
        except Exception as error:
            result, code = {'bad_input': f'instruction tracing failed: {error}'}, 3
        with os.fdopen(w, 'w') as stream:
            json.dump(result, stream, sort_keys=True)
        os._exit(code)
    os.close(w)
    trace_result = None
    if trace:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import instruction_trace
        target_address = target if target is not None else IMAGE + int(address, 0) - EBOOT_BASE
        try:
            trace_result = instruction_trace.trace_child(pid, target_address, machine.boot, case,
                                                        replacement_lib, trace_limit,
                                                        import_targets=_trace_import_targets(machine.boot, case))
        except (OSError, ValueError, instruction_trace.TraceUnavailable) as error:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
            os.close(r)
            raise BadInput(f'instruction tracing unavailable: {error}') from error
    with os.fdopen(r) as stream:
        data = stream.read()
    if trace_result is not None and '_tracee_wait_status' in trace_result:
        status = trace_result.pop('_tracee_wait_status')
    else:
        _, status = os.waitpid(pid, 0)
    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        stop_reason = (trace_result or {}).get('stop_reason')
        if sig == signal.SIGALRM:
            result = {'fault': f'timeout after {timeout} s'}
        elif trace_result is not None and stop_reason and not str(stop_reason).startswith('instruction_signal_'):
            # The tracer PTRACE_KILLs the tracee when it stops on an instruction it cannot decode or
            # an event limit, so the signal is an artifact of tracing, not behaviour -- we killed it.
            # Reporting a guest fault here would put our own hand in the evidence: an unsupported
            # decode became "signal 9" on both sides, which then compared clean. The stop reason is
            # recorded as a gap and an incomplete trace already fails closed in verify.compare.
            result = {}
        else:
            result = {'fault': f'signal {sig}'}
    elif os.WEXITSTATUS(status) == 3:
        # One shape by construction, but a child killed between fork and write would leave
        # the pipe empty, and a JSONDecodeError here would replace the reason with a parse
        # error that reads like a bug in the case.
        try:
            reason = json.loads(data)['bad_input']
        except (ValueError, KeyError, TypeError):
            raise BadInput('the child exited 3 without reporting why') from None
        raise BadInput(reason)
    elif os.WEXITSTATUS(status) != 0 or not data:
        result = {'fault': f'exit {os.WEXITSTATUS(status)}'}
    else:
        result = json.loads(data)
    if trace_result is not None:
        result['instruction_trace'] = trace_result
    return result


def batch(machine: Machine, cases_dir: str, address: str, target: int | None, timeout: int,
          trace: bool = False, trace_limit: int = 100_000,
          replacement_lib: str | None = None) -> dict:
    """Every *.json in CASES_DIR, each in a fork of the mapped machine: a crash or a hang loses
    only that case. Returns {file stem: result}."""
    import glob
    out = {}
    for path in sorted(glob.glob(os.path.join(cases_dir, '*.json'))):
        if os.path.basename(path) == 'abi.json':
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            case = json.load(f)
        try:
            out[stem] = _run_isolated(machine, case, address, target, timeout, trace,
                                      trace_limit, replacement_lib)
        except BadInput as error:
            raise BadInput(f'{stem}: {error}') from error
        out[stem]['id'] = stem
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--elf', required=True, help='the executable (eboot.elf)')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--case', help='one case file; prints its result')
    g.add_argument('--cases', help='a directory of case files; prints {file stem: result}')
    ap.add_argument('--address', required=True)
    ap.add_argument('--replacement')
    ap.add_argument('--lib')
    ap.add_argument('--timeout', type=int, default=20, help='per case, batch mode')
    ap.add_argument('--trace-instructions', action='store_true',
                    help='trace bounded x86-64 guest/replacement memory operands (Linux + Capstone 5)')
    ap.add_argument('--trace-instruction-limit', type=int, default=100_000,
                    help='maximum single-stepped instructions per case')
    ap.add_argument('--patch', help='a community patch file (XML); with --patch-name, its bytes are written '
                    'into the image first (to check an option against the patch it replaces)')
    ap.add_argument('--patch-name')
    a = ap.parse_args()
    # Verification is background work: keep the machine responsive (BB_NICE=0 to disable).
    try:
        os.nice(int(os.environ.get('BB_NICE', '10')))
    except OSError:
        pass
    try:
        boot = open_executable(a.elf)
        machine = Machine(boot)
        if a.patch:
            if not a.patch_name:
                raise BadInput('--patch needs --patch-name')
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from patch_overlap import patch_bytes
            for addr, data in patch_bytes(a.patch, a.patch_name):
                if not EBOOT_BASE <= addr < EBOOT_BASE + boot['size'] - len(data):
                    raise BadInput(f'patch line at 0x{addr:08x} is outside the image')
                ctypes.memmove(IMAGE + addr - EBOOT_BASE, data, len(data))
        target = None
        if a.replacement:
            if not a.lib:
                raise BadInput('--replacement needs --lib')
            target, a.image_base_set = load_replacement(a.lib, a.replacement, boot['size'])
        if a.trace_instruction_limit < 1 or a.trace_instruction_limit > 10_000_000:
            raise BadInput('--trace-instruction-limit must be 1..10000000')
        if a.case:
            with open(a.case) as f:
                result = _run_isolated(machine, json.load(f), a.address, target, a.timeout,
                                       a.trace_instructions, a.trace_instruction_limit, a.lib)
        else:
            result = batch(machine, a.cases, a.address, target, a.timeout,
                           a.trace_instructions, a.trace_instruction_limit, a.lib)
        # The base is stamped on each CASE ENTRY, not at the top level: the harness's stdout is a map
        # from case id to entry, so a top-level key becomes a pseudo-case and run_original's
        # inventory check refuses the run -- correctly, and it caught this exact mistake by name
        # ("incomplete or malformed fixture inventory"). Per-entry is the only namespace the contract
        # offers, and the record is per comparison, which is the granularity the evidence has.
        base_fact = a.image_base_set if a.replacement else 'n/a'
        #
        # TWO SHAPES, and the first version of this loop assumed one: a batch returns a map from case
        # id to entry, a single case returns AN ENTRY. Iterating `.values()` over the second walks its
        # fields, and the dict-valued ones took the stamp -- `preserved` stopped saying 'kept' in four
        # tests, which is what a stamp landing inside a register map looks like from outside.
        if a.case:
            result['image_base_set'] = base_fact
        else:
            for entry in result.values():
                if isinstance(entry, dict):
                    entry['image_base_set'] = base_fact
    except (OSError, ValueError, KeyError, BadInput, json.JSONDecodeError, AttributeError) as e:
        print(f'harness: {e}', file=sys.stderr)
        return 3
    json.dump(result, sys.stdout, sort_keys=True)
    print()
    return 0


def read_back_mismatch(read, writes):
    """(addr, expected, got) for the first written range that does not read back -- None if all did.

    `read(addr, len) -> bytes` is a parameter so this can be falsified without an image. The harness passes
    `ctypes.string_at`, i.e. reads through the GUEST mapping -- the same move that made the rt_guest_writable
    fixture trustworthy: the byte read back through the mapping, never the write's return code.
    """
    for addr, data in writes:
        got = read(addr, len(data))
        if got != data:
            return addr, data, got
    return None


def fixture_seeds(case):
    """The `memory` entries the runner applies with source="fixture_setup".

    THE reader of the seeding schema. A gate that decides whether a case seeds a slot asks this
    function, never `json.load` the case a second time: two readers of one schema eventually
    disagree, and the gate would then be certifying a run the runner does not perform.
    """
    return list(case.get('memory', []))

# The entry point is the LAST statement in the file. A function defined below it is unbindable when the
# module runs as a script: main() executes at the guard, reaches the call site, and the name does not exist
# yet. I put read_back_mismatch above fixture_seeds and thereby pushed fixture_seeds below this guard --
# 44 tests failed with `name 'fixture_seeds' is not defined` and the anchor had been correct all along.
# An anchor is a claim about where a construct is; it is not a claim about the file's execution order.
if __name__ == '__main__':
    sys.exit(main())
