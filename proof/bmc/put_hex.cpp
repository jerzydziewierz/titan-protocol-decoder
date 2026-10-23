// format_hex, for every message of at most MAX_LEN bytes (the bound). MAX_LEN > 32 covers " ...".
#include "harness.hpp"

#ifndef MAX_LEN
#define MAX_LEN 34
#endif

static int nibble(char c) {
    assert((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'));
    return c <= '9' ? c - '0' : c - 'A' + 10;
}

int main() {
    unsigned char msg[MAX_LEN];
    const std::size_t len = nondet_ulong();
    __VERIFIER_assume(len <= MAX_LEN);
    for (std::size_t i = 0; i < MAX_LEN; ++i) msg[i] = nondet_uchar();

    char out[titan::format::hex_capacity];
    const std::size_t used = titan::format::format_hex(msg, len, out);

    // H2, H5: fits the buffer; length; " ..." exactly when the message is longer than 32 bytes.
    const std::size_t shown = len < 32 ? len : 32;
    const std::size_t body = shown == 0 ? 0 : 3 * shown - 1;
    assert(used <= titan::format::hex_capacity);
    assert(used == body + (len > 32 ? 4 : 0));
    if (len > 32) assert(out[body] == ' ' && out[body + 1] == '.' && out[body + 2] == '.' && out[body + 3] == '.');

    // H3, H4: each pair reads back to its byte, and one space separates pairs.
    for (std::size_t k = 0; k < shown; ++k) {
        if (k != 0) assert(out[3 * k - 1] == ' ');
        assert(nibble(out[3 * k]) * 16 + nibble(out[3 * k + 1]) == msg[k]);
    }
    return 0;
}
