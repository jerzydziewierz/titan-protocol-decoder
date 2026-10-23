#include "titan.hpp"
#include "format.hpp"
#include <string_view>
#include <cstdint>
#include <charconv>
#include <chrono>
#include <optional>

namespace titan {

    static constexpr char field_separator=';';

    /// send string_view to sink. no checks are done.
    bool put_msg(const Output sink, const std::string_view message) noexcept {
        return sink.write(sink.descriptor, std::span<const char>{message.data(), message.size()});
    }

    /// format with format_int (src/format.cpp) and output with put_msg.
    // Post-submission fix (George Rey): a value that does not fit in eight characters lost its
    // leading digits and its sign, e.g. -123456789 printed as 23456789. Now it prints as
    // " (large)" or "-(large)"; the output stays eight characters.
    bool put_int(const Output sink, const std::int64_t message) noexcept {
        char out_chars[format::int_width];
        const std::size_t used = format::format_int(message, out_chars);
        return put_msg(sink, std::string_view{out_chars, used});
    }

    /// Display at most 32 bytes as uppercase hex pairs, with spaces between bytes (format_hex).
    bool put_hex(const Output sink, const std::string_view message) noexcept {
        static_assert(format::hex_capacity == format::hex_max_bytes * 3 - 1 + 4, "32 pairs, 31 spaces, \" ...\"");
        char out_chars[format::hex_capacity];
        const std::size_t used = format::format_hex(
            reinterpret_cast<const unsigned char*>(message.data()), message.size(), out_chars);
        return put_msg(sink, std::string_view{out_chars, used});
    }


    IntConvertResult to_int_may_fail(std::string_view message) noexcept {
        IntConvertResult result2{};
        const std::from_chars_result result = std::from_chars(message.begin(), message.end(), result2.value);
        result2.valid = (result.ec == std::errc{})&&(result.ptr==(message.data()+message.size()));
        return result2;
    }


    ///decodes content of payload for housekeeping: expects 5 fields.
    ///
    /// | Name        | Description                                                      |
    /// | ----------- | ---------------------------------------------------------------- |
    /// | Status      | `0` indicates operational state, other values indicate failures  |
    /// | Theta       | Theta angle of the sun position in increments of 1 / 1000 degree |
    /// | Phi         | Phi angle of the sun position in increments of 1 / 1000 degrees  |
    /// | Intensity   | Unitless quantity, Intensity of the sun on the sensor            |
    /// | Temperature | Temperature of the sensor, increments of 1 / 1000 degree         |

    PacketHousekeepingError decode_housekeeping_and_output(
        __attribute_maybe_unused__ const Output output,
        __attribute_maybe_unused__ const Output error_sink,
        __attribute_maybe_unused__ Workspace& workspace,
        __attribute_maybe_unused__ const std::string_view payload
        ) noexcept {
        // ok, here we have 6 fields, so it may be nice to do take them iteratively.
        struct HouseKeepingResult {
            int64_t status=0;
            int64_t theta=0;
            int64_t phi=0;
            int64_t intensity=0;
            int64_t temperature=0;

        };
        HouseKeepingResult housekeeping_result{};
        int64_t* pointers[] = {
            &housekeeping_result.status,
            &housekeeping_result.theta,
            &housekeeping_result.phi,
            &housekeeping_result.intensity,
            &housekeeping_result.temperature
        };
        size_t last_separator = 0;
        for (int64_t* destination:pointers) {
            const size_t next_separator = payload.find_first_of(field_separator,last_separator);
            if (next_separator==std::string_view::npos) return PacketHousekeepingError::insufficient_fields; // return early
            const std::string_view field_str = payload.substr(last_separator,next_separator-last_separator);
            auto [valid, value] = to_int_may_fail(field_str);
            if (!valid) {return PacketHousekeepingError::field_unconvertable;}; // return early
            *destination = value;
            last_separator=next_separator+1;
        }
        // everything ok for the first field set; but if there is more fields, we need to detect that:
        const size_t extra_separator = payload.find_first_of(field_separator,last_separator);
        if (extra_separator!=std::string_view::npos) return PacketHousekeepingError::surplus_fields;
        put_msg(output,"  housekeeping_status: "); put_int(output,housekeeping_result.status); put_msg(output,"\n");
        put_msg(output,"  housekeeping_theta: "); put_int(output,housekeeping_result.theta); put_msg(output,"\n");
        put_msg(output,"  housekeeping_phi: "); put_int(output, housekeeping_result.phi); put_msg(output,"\n");
        put_msg(output,"  housekeeping_intensity:"); put_int(output, housekeeping_result.intensity); put_msg(output,"\n");
        put_msg(output,"  housekeeping_temperature:"); put_int(output, housekeeping_result.temperature); put_msg(output,"\n");



        return PacketHousekeepingError::none;
    }

    /// decodes content of generic packet:
    /// expects
    /// * Command ID,
    /// * sequence number,
    /// * timestamp;
    /// then, everything else is a payload.
    ///
    /// The field separator is ';' except for the payload where the entire payload is passed on to the packet-specific decoder.
    PacketHeaderError decode_header_and_output(
        const Output output,
        __attribute_maybe_unused__  const Output error_sink,
        __attribute_maybe_unused__  Workspace& workspace,
        const std::string_view message
        ) noexcept {
        // we expect at least 3 separators, and after 3rd one, it's payload.
        // we need to get command ID, sequence number, timestamp; all of these are large integers
        bool write_success = true;
        std::uint64_t commandID=0;
        std::uint64_t sequence_number=0;
        std::uint64_t timestamp=0;

        enum class KnownMessageTypes { ping, housekeeping, unknown};

        KnownMessageTypes interpreted_message_type = KnownMessageTypes::unknown;
        const size_t separator_position_after_commandID = message.find_first_of(field_separator,0);
        if (separator_position_after_commandID==std::string_view::npos) return PacketHeaderError::invalid_packet_content_field_separator;

        const size_t separator_position_after_sequence_number = message.find_first_of(field_separator,separator_position_after_commandID+1);

        if (separator_position_after_sequence_number==std::string_view::npos) return PacketHeaderError::invalid_packet_content_field_separator;
        const size_t separator_position_after_timestamp = message.find_first_of(field_separator,separator_position_after_sequence_number+1);

        if (separator_position_after_timestamp==std::string_view::npos) return PacketHeaderError::invalid_packet_content_field_separator;

        // so far, so good.
        const std::string_view str_commandID = message.substr(0,separator_position_after_commandID);
        const std::string_view str_sequence_number = message.substr(separator_position_after_commandID+1, separator_position_after_sequence_number-separator_position_after_commandID-1);
        const std::string_view str_timestamp = message.substr(separator_position_after_sequence_number+1, separator_position_after_timestamp-separator_position_after_sequence_number-1);
        __attribute_maybe_unused__  const std::string_view payload = message.substr(separator_position_after_timestamp+1);


        auto [valid1, value1] = to_int_may_fail(str_commandID);
        if (!valid1) {return PacketHeaderError::header_unconvertable_field_content;};
        commandID = value1;

        auto [valid2, value2] = to_int_may_fail(str_sequence_number);
        if (!valid2) {return PacketHeaderError::header_unconvertable_field_content;};
        sequence_number = value2;

        auto r_timestamp = to_int_may_fail(str_timestamp);
        if (!r_timestamp.valid) {return PacketHeaderError::header_unconvertable_field_content;};
        timestamp = r_timestamp.value;


        // now, depending on the commandID, we might need to process payload.
        // for now, emit what we have
        write_success&=put_msg(output,"- commandID:"); write_success&=put_int(output,commandID); write_success&=put_msg(output,"\n");
        std::string_view commandID_interpretation="Unknown";
        if (commandID==1) {commandID_interpretation="Ping"; interpreted_message_type=KnownMessageTypes::ping;}
        else if ((commandID==10)||(commandID==12)) {commandID_interpretation="House_keeping"; interpreted_message_type=KnownMessageTypes::housekeeping;}
        write_success&=put_msg(output,"  interpreted_command: "); write_success&=put_msg(output,commandID_interpretation); write_success&=put_msg(output,"\n");

        write_success&=put_msg(output,"  sequence_number: "); write_success&=put_int(output,sequence_number); write_success&=put_msg(output,"\n");

        write_success&=put_msg(output, "  timestamp: "); write_success&=put_int(output, timestamp); write_success&=put_msg(output,"\n");
        write_success&=put_msg(output, "  payload_hex: "); write_success&=put_hex(output,payload); write_success&=put_msg(output,"\n");

        // ok; there is only one kind of payload to interpret, so let's not play with loadable interpreter registries yet.
        // for now, simple is sufficient: if the commandID is 10 or 12, then interpret it further.
        if (interpreted_message_type==KnownMessageTypes::housekeeping) {
            PacketHousekeepingError housekeeping_packet_error = decode_housekeeping_and_output(output,error_sink,workspace,payload);
            if (housekeeping_packet_error!=PacketHousekeepingError::none) {return PacketHeaderError::payload_known_type_but_interpretation_error;}
        }
        if (write_success) {return PacketHeaderError::none;} else {return PacketHeaderError::write_failure;};

    };


    DepacketError depacket_and_output(const Input input, const Output output, const Output error_sink, Workspace& workspace) noexcept
    {
        DepacketError error = DepacketError::none;
        bool write_success = true;
        const std::span<char> buffer{workspace.input_buffer};


        // ok, time for our state machine.

        //****
        // algorithm: state machine:
        // ---
        // e1: start_char : start character found
        // e2: other_char : other character found
        // e3: end_char : end character found
        // e4: eof : end of file
        // ---
        // s0: startup
        //     on entry:reset buffer, open files, ->s1
        // s1: between messages
        //      on entry: read character, if error or eof -> s3
        //          e1:reset buffer,->s2;
        //          e2:->s1;
        //          e3:emit error, ->s1;
        //          e4:->s3
        // s2: inside message
        //     on entry: read character if error or eof -> s3
        //          e1:emit error, reset buffer, ->s2;
        //          s2:add to buffer; ->s2;
        //          e3:commit the message to message processor, THEN reset buffer, ->s1
        //          e4:emit error, reset buffer, ->s3
        // s3: finalise
        //     on entry: close files.
        enum class Smstates {between, inside, finalise};
        auto smstate = Smstates::between;
        std::array<char, 1> candidate_char{}; // sensible packet size. Error if packet turns out to be any larger.
        size_t candidate_packet_size = 0;
        while (true) {

            // common on enter state
            const ReadResult result = input.read(input.descriptor, candidate_char);
            if (result.failed) {
                error= DepacketError::input; smstate = Smstates::finalise ;
            }
            // A successful read cannot exceed the destination supplied to the callback.
            else if (result.size > candidate_char.size()) { error = DepacketError::invalid_read_size; smstate = Smstates::finalise; }
            else if (result.size == 0) { smstate = Smstates::finalise; }


            if (smstate==Smstates::between) {
                if (candidate_char[0]=='$') // good packet start found
                {
                    candidate_packet_size = 0;
                    smstate = Smstates::inside; continue;
                }
                // any other character: ignore.

            } // end of smstate==Smstates::between;

            if (smstate==Smstates::inside) {

                if (candidate_char[0]=='$') { // start of new packet on the inside of existing packet. discard the previous packet and restart packet buffering.
                    candidate_packet_size = 0;
                    smstate = Smstates::inside; continue;

                }
                if (candidate_char[0]=='|') {
                    // good end of packet. submit to processing. Note that we need to pass the shortened buffer.data(), not the full buffer.data();
                    __attribute_maybe_unused__ PacketHeaderError per_packet_error = decode_header_and_output( output, error_sink, workspace, std::string_view{buffer.data(),candidate_packet_size});
                    write_success &=(per_packet_error!=PacketHeaderError::write_failure);
                    if (!write_success) {
                        return DepacketError::output;
                    }
                    // if other error, ignore, and continue. this is safe.
                    smstate = Smstates::between; continue;
                }
                // any other character: first, check for overflow
                if (candidate_packet_size>workspace.input_buffer.size()-2) {
                    error = DepacketError::packet_oversize; // discard entire packet.
                    candidate_packet_size = 0;
                    smstate = Smstates::between; continue;
                }
                // any other character: add to the input buffer.
                buffer[candidate_packet_size] = candidate_char[0]; candidate_packet_size++;
                continue;
            } // end of smstate==Smstates::inside


            if (smstate == Smstates::finalise) {
                break;
            }
        }
        return error;
    } // end of decode()

}
