#include <cstdint>

// 0x0050af70: xor eax,eax; ret. One of 4,721 members of a single 3-byte body.
extern "C" std::uint64_t bb_leaf_ret_zero_0050af70() { return 0; }
