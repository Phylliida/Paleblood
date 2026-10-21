#include <cstdint>

// 0x006b0560: xor eax,eax; ret. One of 4,721 members of a single 3-byte body.
extern "C" std::uint64_t bb_leaf_ret_zero_006b0560() { return 0; }
