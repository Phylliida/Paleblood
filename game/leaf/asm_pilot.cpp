// Pilot for decision 1/2: a single-instruction asm body plus terminator, and the C body that
// cannot match it for a 3-byte shape. Proves tools/check_asm_bytes.py in both directions.
#include <cstdint>

extern "C" __attribute__((naked)) void bb_asm_pilot_004034f0(void) {
  __asm__ volatile("movb $1, %al\n\tret");
}

// The shape the assertion exists to catch: same length, different first byte.
namespace {
constexpr std::uint64_t k_low_byte = 0xffu;
constexpr std::uint64_t k_mov_al_imm_01 = 0x1u;
}  // namespace

extern "C" std::uint64_t bb_c_pilot_004034f0(std::uint64_t a0) {
  return (a0 & ~k_low_byte) | k_mov_al_imm_01;
}

// For the 1-byte family byte equality is NECESSARY AND NOT SUFFICIENT: at -O2 an empty C body
// emits exactly one `c3`, identical to naked `asm("ret")`. The tool must say so rather than
// pretend its green distinguishes them.
extern "C" void bb_c_pilot_ret(void) {}
