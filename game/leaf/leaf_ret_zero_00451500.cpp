#include <cstdint>

// 0x00451500: xor eax,eax; ret. One of 4,721 members of a single 3-byte body.
extern "C" std::uint64_t bb_leaf_ret_zero_00451500() { return 0; }
