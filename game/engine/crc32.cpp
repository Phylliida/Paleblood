// SPDX-License-Identifier: GPL-2.0-or-later
// Engine: the two CRC-32 update kernels.
//
// engine_crc32_update_byte (0x02e613c0) folds one byte into a running CRC-32 and
// engine_crc32_update (0x02e613e0) runs the same fold over a byte range. Both are byte-at-a-time
// table lookups against the standard reflected CRC-32 table at 0x04cdcf50, whose first entries are
// 0x00000000, 0x77073096, 0xee0e612c, 0x990951ba: that is CRC-32/ISO-HDLC (the zlib/gzip
// polynomial 0xedb88320, reflected), the variant whose final value is conventionally XORed with
// 0xffffffff. Neither kernel does that final XOR and neither touches the initial value, because
// each one continues a CRC the caller has already started: the state lives in the caller's word
// and every entry point here both reads and writes it in place.
//
// The range form is written as a do/while, so a zero length performs no work at all rather than
// one iteration; a null pointer with a nonzero length is not a case the original guards against.
#include <cstddef>
#include <cstdint>

#include "runtime/guest.h"

namespace {

// The reflected CRC-32 lookup table (CRC-32/ISO-HDLC): standard low byte first, four bytes of the
// little-endian word per index.
constexpr uint32_t crc_table_address = 0x04cdcf50;

// One byte is eight bits, and the table index is the low byte of the state.
constexpr unsigned crc_byte_bits = 8;
constexpr uint32_t crc_byte_mask = 0xff;

}  // namespace

extern "C" void bb_engine_crc32_update_byte(uint32_t *crc, uint32_t byte)
{
    // Byte-at-a-time reflected step: index by (low byte of the CRC) XOR (the new byte), shift the
    // CRC down, then XOR in the table entry.
    const uint32_t index = (*crc ^ byte) & crc_byte_mask;
    *crc = (*crc >> crc_byte_bits) ^ rt::ptr<const uint32_t>(crc_table_address)[index];
}

extern "C" void bb_engine_crc32_update(uint32_t *crc, const uint8_t *data, uint64_t length)
{
    const uint32_t *table = rt::ptr<const uint32_t>(crc_table_address);
    uint32_t state = *crc;
    while (length != 0) {
        state = (state >> crc_byte_bits) ^ table[(state ^ *data) & crc_byte_mask];
        ++data;
        --length;
    }
    *crc = state;
}
