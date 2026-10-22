#include "titan.hpp"

#include <cerrno>
#include <unistd.h>

namespace outer {

// read into the provided buffer. return read result.
titan::ReadResult read_bytes(int file_descriptor, std::span<char> buffer) noexcept
{
    ssize_t count;
    do {
        // use read provided by posix unistd.h
        count = ::read(file_descriptor, buffer.data(), buffer.size());
    } while (count < 0 && errno == EINTR);

    if (count < 0) return {0, true};
    return {static_cast<std::size_t>(count), false};
}

// POSIX may write only a prefix. Keep writing until the whole view is consumed.
bool write_bytes(int descriptor, std::span<const char> bytes) noexcept
{
    while (!bytes.empty()) {
        ssize_t count;
        do {
            count = ::write(descriptor, bytes.data(), bytes.size());
        } while (count < 0 && errno == EINTR);

        if (count <= 0) return false;
        bytes = bytes.subspan(static_cast<std::size_t>(count));
    }
    return true;
}

} // end of namespace lancher

int main(int argc, char**)
{
    if (argc != 1) {
        return 1; // error 1: wrong count of arguments.
    }
    // These objects live through the call. No stream object owns heap storage.
    static constexpr int source = STDIN_FILENO;
    static constexpr int destination = STDOUT_FILENO;
    static constexpr int stderr = STDERR_FILENO;
    titan::Workspace workspace{};
    constexpr titan::Input input{source, outer::read_bytes};
    constexpr titan::Output output{destination, outer::write_bytes};
    constexpr titan::Output error_sink{stderr, outer::write_bytes};
    const titan::DepacketError decode_error = titan::depacket_and_output(input, output, error_sink, workspace);
    if (decode_error==titan::DepacketError::none) {return 0;} else {return 1;}

}
