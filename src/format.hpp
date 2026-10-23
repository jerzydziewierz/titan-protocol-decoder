#pragma once
// Pure formatters for put_int and put_hex. They use no standard library, so that the bounded model
// checkers (CBMC, ESBMC) can verify this code as it is. See proof/README.md.
#include <cstddef>
#include <cstdint>

namespace titan {
namespace format {

// format_int writes exactly int_width characters.
constexpr std::size_t int_width = 8;

// format_hex shows at most hex_max_bytes bytes; hex_capacity is the largest output (with " ...").
constexpr std::size_t hex_max_bytes = 32;
// A literal, not an expression: CBMC 5.95 initialises namespace constants in alphabetical order, so
// "hex_max_bytes * 3 - 1 + 4" would read hex_max_bytes as 0 there. A static_assert in titan.cpp checks it.
constexpr std::size_t hex_capacity = 99;

/// Write v right-aligned in 8 characters. A value that does not fit prints as " (large)" (v >= 10^8)
/// or "-(large)" (v <= -10^7). out must hold int_width characters. Returns int_width.
std::size_t format_int(std::int64_t v, char* out) noexcept;

/// Write at most 32 bytes as uppercase hex pairs with one space between pairs, then " ..." if size > 32.
/// out must hold hex_capacity characters. Returns the count of characters written.
std::size_t format_hex(const unsigned char* data, std::size_t size, char* out) noexcept;

}
}
