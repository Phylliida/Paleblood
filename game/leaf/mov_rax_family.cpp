#include <cstdint>
#include <cstring>

constexpr std::size_t k_word_bytes = sizeof(std::uint64_t);  // one 8-byte word

// Generated: mov rax, [rdi + K]; ret. Each body reads the 8 bytes at the pointer
// the caller passed, at that member's own displacement. The read is asserted through
// the returned rax: the harness does not instrument guest load/store instructions,
// and the marker sits in a non-writable segment so the post-call snapshot misses it.
// memcpy, not a dereference through a cast: K=0x1 leaves the pointer unaligned.

constexpr std::uint64_t k_leaf_mov_rax_00410100 = 0x10u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00410100(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00410100), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00418d80 = 0x1c0u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_00418d80(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00418d80), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004261a0 = 0x48u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004261a0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004261a0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_0042d830 = 0x40u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_0042d830(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_0042d830), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004381d0 = 0x58u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004381d0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004381d0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00439e20 = 0x1u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00439e20(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00439e20), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004401b0 = 0x8u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004401b0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004401b0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00446880 = 0x108u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_00446880(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00446880), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00450ba0 = 0x30u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00450ba0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00450ba0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00454c70 = 0x28u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00454c70(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00454c70), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00455130 = 0x20u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00455130(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00455130), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00455410 = 0x20u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00455410(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00455410), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00457230 = 0x40u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00457230(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00457230), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00457700 = 0x40u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00457700(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00457700), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004bb210 = 0x8u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004bb210(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004bb210), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004c5810 = 0x8u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004c5810(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004c5810), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004ea8a0 = 0x40u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004ea8a0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004ea8a0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_004ef270 = 0x18u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_004ef270(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_004ef270), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00503de0 = 0x78u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00503de0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00503de0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00504b50 = 0x70u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_00504b50(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00504b50), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_00508090 = 0xb0u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_00508090(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_00508090), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_005ffd70 = 0x88u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_005ffd70(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_005ffd70), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_005ffdf0 = 0xa0u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_005ffdf0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_005ffdf0), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_0060ad90 = 0x88u;  // size 8
extern "C" std::uint64_t bb_leaf_mov_rax_0060ad90(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_0060ad90), k_word_bytes);
    return value;
}
constexpr std::uint64_t k_leaf_mov_rax_006966b0 = 0x50u;  // size 5
extern "C" std::uint64_t bb_leaf_mov_rax_006966b0(std::uint64_t rdi) {
    std::uint64_t value;
    std::memcpy(&value, reinterpret_cast<const void*>(rdi + k_leaf_mov_rax_006966b0), k_word_bytes);
    return value;
}
