// Adapted test intentions from solution1 integer tests and solution2/3 fault/boundary tests.
#include "titan.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace {
// Descriptor-indexed callbacks model this API without changing production code.
std::string input, output;
std::size_t position, reads, writes, fail_read, fail_write;
bool lie;
titan::ReadResult read(int, std::span<char> dst) noexcept {
    ++reads;
    if (position == fail_read) return {0, true};
    if (lie) { lie=false; return {dst.size()+1, false}; }
    if (position == input.size()) return {0, false};
    dst[0]=input[position++];
    return {1, false};
}
bool write(int fd, std::span<const char> bytes) noexcept {
    if (fd==2) return true;
    if (writes++ == fail_write) {
        return false;
    }
    output.append(bytes.data(),bytes.size());
    return true;
}
void reset(std::string data={}) {
    input=std::move(data); output.clear(); position=reads=writes=0;
    fail_read=fail_write=std::size_t(-1); lie=false;
}
titan::Output sink{1,write}, errors{2,write};
titan::DepacketError run(titan::Workspace& w) {
    return titan::depacket_and_output({0,read},sink,errors,w);
}
int failures=0, total=0;
void check(const char* name, bool ok) {
    ++total; failures+=!ok;
    std::printf("%s\t%s\n",ok?"PASS":"FAIL",name);
}
}
int main() {
    titan::Workspace w{};
    // Integer conversion must consume the whole view and cover signed limits.
    for (auto text : {"0", "-356789", "9223372036854775807", "-9223372036854775808"}) {
        const auto r=titan::to_int_may_fail(text);
        check((std::string("integer valid ")+text).c_str(),r.valid && r.value==std::stoll(text));
    }
    // Reject syntax noise, embedded NUL, and both overflow directions.
    for (auto text : {std::string(""),std::string("+1"),std::string(" 1"),std::string("1x"),
                     std::string("1\0",2),std::string("9223372036854775808"),std::string("-9223372036854775809")}) {
        check(("integer invalid hex-length "+std::to_string(text.size())+" "+text).c_str(),!titan::to_int_may_fail(text).valid);
    }
    // Fixed-width diagnostic formatting intentionally keeps the rightmost eight characters.
    for (auto value : {INT64_MIN,INT64_MAX,int64_t(-123),int64_t(0),int64_t(123456789)}) {
        reset(); titan::put_int(sink,value); auto expected=std::to_string(value);
        if(expected.size()>8) expected=expected.substr(expected.size()-8);
        else expected=std::string(8-expected.size(),' ')+expected;
        check(("put_int "+std::to_string(value)).c_str(),output==expected);
    }
    // Every byte must be escaped as uppercase hex, including control and high-bit bytes.
    for(int byte=0;byte<256;++byte) {
        reset(); char c=static_cast<char>(byte), expected[3]; std::snprintf(expected,3,"%02X",byte);
        titan::put_hex(sink,{&c,1}); check(("hex byte "+std::to_string(byte)).c_str(),output==expected);
    }
    // The hex preview has exact boundaries and an explicit truncation marker.
    for(std::size_t n : {0,1,31,32,33}) {
        reset(); titan::put_hex(sink,std::string(n,'A')); std::string expected;
        for(std::size_t i=0;i<std::min(n,std::size_t(32));++i) expected+=(i?" 41":"41");
        if(n>32) expected+=" ...";
        check(("hex length "+std::to_string(n)).c_str(),output==expected);
    }
    // put_msg must preserve length, including embedded NUL, rather than scan for termination.
    reset(); titan::put_msg(sink,{"a\0b",3}); check("binary put_msg",output==std::string("a\0b",3));
    // Successful empty input must not emit a phantom packet.
    reset(); check("empty input",run(w)==titan::DepacketError::none && output.empty());
    // Reusing caller-owned storage must not leak fields from the previous conversion.
    reset("$1;2;3;;|"); run(w); const auto first=output;
    reset("$1;2;3;;|"); run(w); check("workspace reuse",output==first && !output.empty());
    // Every read failure location must propagate through the public decoder API.
    for(std::size_t i=0;i<=input.size();++i) {
        reset("$1;2;3;;|"); fail_read=i;
        check(("read failure "+std::to_string(i)).c_str(),run(w)==titan::DepacketError::input);
    }
    // A reader may not claim more bytes than the supplied one-byte destination.
    reset(); lie=true; check("read overreport",run(w)==titan::DepacketError::invalid_read_size);
    // Each failed write must stop conversion and propagate an output error.
    reset("$1;2;3;;|"); run(w); const auto count=writes;
    for(std::size_t i=0;i<count;++i) {
        reset("$1;2;3;;|");
        fail_write=i;
        titan::DepacketError result = run(w);
        check(
            ("write failure "+std::to_string(i)).c_str(),
            result==titan::DepacketError::output);
        // note: original idea was to abort execution on first write error.
        // However, this is not practical.
        // Now, it will abort if any write fails, even if it's abort on non-first write.
        // This does mean that the output may be incomplete and garbled on failure. but at least the failure will be reported.
    }
    // Detect an intra-object overflow that ASan may miss: output_buffer is an adjacent canary.
    for(std::size_t n : {16383,16384,16385,16386}) {
        reset("$"+std::string(n,'A')+"|");
        w.output_buffer.fill('Z');
        const auto r=run(w);
        check(("packet boundary canary "+std::to_string(n)).c_str(),
              std::all_of(w.output_buffer.begin(),w.output_buffer.end(),[](char c){return c=='Z';}));
        check(("packet boundary error "+std::to_string(n)).c_str(),
              (r==titan::DepacketError::packet_oversize)==(n>=16384));
    }
    // Housekeeping parsing must reject missing, malformed and surplus fields.
    reset(); check("housekeeping good",titan::decode_housekeeping_and_output(sink,errors,w,"0;12000;-9000;68;-29950;")==titan::PacketHousekeepingError::none);
    reset(); check("housekeeping short",titan::decode_housekeeping_and_output(sink,errors,w,"0;1;")==titan::PacketHousekeepingError::insufficient_fields);
    reset(); check("housekeeping bad integer",titan::decode_housekeeping_and_output(sink,errors,w,"0;x;2;3;4;")==titan::PacketHousekeepingError::field_unconvertable);
    reset(); check("housekeeping surplus",titan::decode_housekeeping_and_output(sink,errors,w,"0;1;2;3;4;5;")==titan::PacketHousekeepingError::surplus_fields);
    // Header failures must report errors before emitting incomplete records.
    for(auto packet : {"1", "1;2", "1;2;", "x;2;3;", "1;;3;"}) {
        reset(); check((std::string("header invalid ")+packet).c_str(),titan::decode_header_and_output(sink,errors,w,packet)!=titan::PacketHeaderError::none && output.empty());
    }
    // Invalid housekeeping must remain visible to callers of the header layer.
    reset(); check("payload error propagation",titan::decode_header_and_output(sink,errors,w,"10;2;3;0;bad;")!=titan::PacketHeaderError::none);
    std::printf("TOTAL %d FAILED %d\n",total,failures);
    return failures?1:0;
}
