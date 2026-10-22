#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>

namespace titan {

// std::array stores its bytes inside this object; it does not allocate a buffer.
struct Workspace {
    std::array<char, 16*1024> input_buffer; // sensible packet size. Error if packet turns out to be any larger.
    std::array<char, 64*1024> output_buffer; //accumulates yaml output
    };

// A successful read of zero bytes means EOF. An error makes size irrelevant.
struct ReadResult {
    std::size_t size;
    bool failed;
    };

// File descriptors are copied integers; these structs do not close them.
// Callbacks must be valid, and descriptors must stay open during depacket().
struct Input {
    int descriptor;
    // pointer to reader function
    ReadResult (*read)(int, std::span<char>) noexcept;
    };

// A successful write accepts the whole span. The sink must not retain the span.
// There is no flush operation yet: this interface expects an unbuffered sink.
struct Output {
    int descriptor;
    // pointer to writer function
    bool (*write)(int, std::span<const char>) noexcept;
    };

enum class OuterError {
    none,
    input,
    output
    };

enum class PacketHeaderError {
    none,
    invalid_packet_content_field_separator,
    header_unconvertable_field_content,
    payload_known_type_but_interpretation_error,
    write_failure,
    };

enum class PacketHousekeepingError {
    none,
    insufficient_fields,
    field_unconvertable,
    surplus_fields,
};

enum class DepacketError {none, input, invalid_read_size, packet_oversize, output};

struct IntConvertResult {
    bool valid=false;
    std::int64_t value=0;
};

/// noexcept forbids escaping exceptions; callbacks must separately avoid allocation.
DepacketError depacket_and_output(Input input, Output output, Output error_sink, Workspace& workspace) noexcept;

bool put_msg(Output sink, std::string_view message) noexcept;

bool put_int(Output sink, std::int64_t message) noexcept;

bool put_hex(Output sink, std::string_view message) noexcept;

IntConvertResult to_int_may_fail(std::string_view message) noexcept;

PacketHousekeepingError decode_housekeeping_and_output(
        Output output,
        Output error_sink,
        Workspace& workspace,
        std::string_view payload
        ) noexcept;


PacketHeaderError decode_header_and_output(
    Output output,
    Output error_sink,
    Workspace& workspace,
    std::string_view message
    ) noexcept;

}
