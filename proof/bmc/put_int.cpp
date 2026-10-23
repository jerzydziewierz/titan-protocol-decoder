// format_int, for every int64_t value. No bound on the value: it is symbolic.
#include "harness.hpp"

int main() {
    const std::int64_t v = nondet_longlong();
    char out[titan::format::int_width];
    const std::size_t used = titan::format::format_int(v, out);

    // I1: always eight characters (array bounds are checked by the tool).
    assert(used == 8);

    // I3, I4: out of range gives the marker.
    const char* const pos_marker = " (large)";
    const char* const neg_marker = "-(large)";
    if (v >= 100000000) { for (int i = 0; i < 8; ++i) assert(out[i] == pos_marker[i]); return 0; }
    if (v <= -10000000) { for (int i = 0; i < 8; ++i) assert(out[i] == neg_marker[i]); return 0; }

    // I2: in range, the text reads back to v. Left spaces, optional '-', then digits only.
    int i = 0;
    while (i < 8 && out[i] == ' ') ++i;
    const bool negative = (i < 8 && out[i] == '-');
    if (negative) ++i;
    assert(i < 8);
    std::int64_t value = 0;
    for (; i < 8; ++i) {
        assert(out[i] >= '0' && out[i] <= '9');
        value = value * 10 + (out[i] - '0');
    }
    assert((negative ? -value : value) == v);
    return 0;
}
