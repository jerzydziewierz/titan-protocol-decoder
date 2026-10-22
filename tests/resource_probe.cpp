// Count decoder I/O requests without OS noise or dynamic storage in the callbacks.
#include "titan.hpp"
#include <cstdio>
#include <string_view>
namespace {
constexpr std::string_view packet="$1;2;3;;|";
std::size_t position=0, reads=0, writes=0, bytes=0;
titan::ReadResult read(int, std::span<char> out) noexcept {
    ++reads;
    if(position==packet.size()*100000) return {0,false};
    out[0]=packet[position++ % packet.size()]; return {1,false};
}
bool write(int, std::span<const char> out) noexcept {++writes; bytes+=out.size(); return true;}
}
int main() {
    titan::Workspace workspace{};
    auto result=titan::depacket_and_output({0,read},{1,write},{2,write},workspace);
    std::printf("{\"packets\":100000,\"read_calls\":%zu,\"write_calls\":%zu,\"output_bytes\":%zu,\"workspace_bytes\":%zu}\n",reads,writes,bytes,sizeof(workspace));
    return result==titan::DepacketError::none?0:1;
}
