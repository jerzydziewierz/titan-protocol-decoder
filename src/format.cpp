#include "format.hpp"

namespace titan {
namespace format {

std::size_t format_int(std::int64_t v, char* out) noexcept {
    const char* marker = nullptr;
    if (v >= 100000000) {marker = " (large)";}
    else if (v <= -10000000) {marker = "-(large)";}
    if (marker != nullptr) {
        for (std::size_t i = 0; i < int_width; ++i) {out[i] = marker[i];}
        return int_width;
    }
    // Here -10^7 < v < 10^8: at most 7 digits and a sign, or 8 digits. The magnitude fits in 32 bits.
    const bool negative = v < 0;
    std::uint32_t magnitude = static_cast<std::uint32_t>(negative ? -v : v);
    std::size_t pos = int_width;
    do {
        out[--pos] = static_cast<char>('0' + magnitude % 10);
        magnitude /= 10;
    } while (magnitude != 0);
    if (negative) {out[--pos] = '-';}
    while (pos > 0) {out[--pos] = ' ';}
    return int_width;
}

std::size_t format_hex(const unsigned char* data, std::size_t size, char* out) noexcept {
    static const char hex[] = "0123456789ABCDEF";
    const std::size_t shown = size < hex_max_bytes ? size : hex_max_bytes;
    std::size_t used = 0;
    for (std::size_t i = 0; i < shown; ++i) {
        if (i != 0) {out[used++] = ' ';}
        out[used++] = hex[data[i] >> 4];
        out[used++] = hex[data[i] & 15];
    }
    if (size > hex_max_bytes) {
        static const char ellipsis[] = " ...";
        for (std::size_t i = 0; i < 4; ++i) {out[used++] = ellipsis[i];}
    }
    return used;
}

}
}
