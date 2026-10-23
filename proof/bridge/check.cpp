// Compare the C++ put_hex and put_int with the Lean model.
// Input (stdin): the lines that `lake exe golden` prints. Output: one line for each mismatch,
// then a summary. Exit status 0 only if all lines agree.
#include "src/titan.hpp"

#include <charconv>
#include <cstdint>
#include <iostream>
#include <string>

namespace {

std::string captured;

bool capture(int, std::span<const char> bytes) noexcept {
    captured.append(bytes.data(), bytes.size());
    return true;
}

constexpr titan::Output sink{0, capture};

int nibble(char c) { return c <= '9' ? c - '0' : c - 'A' + 10; }

std::string from_compact_hex(std::string_view hex) {
    std::string bytes;
    for (std::size_t i = 0; i + 1 < hex.size(); i += 2)
        bytes.push_back(static_cast<char>(nibble(hex[i]) * 16 + nibble(hex[i + 1])));
    return bytes;
}

} // namespace

int main() {
    std::string line;
    long checked = 0, failed = 0;
    while (std::getline(std::cin, line)) {
        const auto t1 = line.find('\t');
        const auto t2 = line.find('\t', t1 + 1);
        const std::string_view kind{line.data(), t1};
        const std::string_view input{line.data() + t1 + 1, t2 - t1 - 1};
        const std::string_view expected{line.data() + t2 + 1};
        captured.clear();
        if (kind == "H") {
            titan::put_hex(sink, from_compact_hex(input));
        } else {
            std::int64_t v = 0;
            std::from_chars(input.data(), input.data() + input.size(), v);
            titan::put_int(sink, v);
        }
        ++checked;
        if (captured != expected) {
            ++failed;
            std::cout << "MISMATCH " << kind << " " << input << "\n  model: [" << expected
                      << "]\n  c++:   [" << captured << "]\n";
        }
    }
    std::cout << checked << " cases, " << failed << " mismatches\n";
    return (checked > 0 && failed == 0) ? 0 : 1;
}
