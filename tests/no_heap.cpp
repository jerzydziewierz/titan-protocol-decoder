#include "titan.hpp"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <string_view>

namespace {
bool allocation_forbidden = false;
std::size_t heap_attempts = 0;
bool reject_heap() noexcept {
    if (!allocation_forbidden) return false;
    ++heap_attempts;
    return true;
}
}

// GNU linker wrapping catches direct linked calls, not allocator calls internal to
// separately loaded shared libraries. Global new covers C++ allocation entrypoints.
extern "C" {
void* __real_malloc(std::size_t);
void* __real_calloc(std::size_t, std::size_t);
void* __real_realloc(void*, std::size_t);
void __real_free(void*);
void* __wrap_malloc(std::size_t size) { return reject_heap() ? nullptr : __real_malloc(size); }
void* __wrap_calloc(std::size_t n, std::size_t size) { return reject_heap() ? nullptr : __real_calloc(n, size); }
void* __wrap_realloc(void* p, std::size_t size) { return reject_heap() ? nullptr : __real_realloc(p, size); }
void __wrap_free(void* p) { if (!reject_heap()) __real_free(p); }
}

namespace {
void* allocate(std::size_t size, std::size_t alignment = 0) {
    if (reject_heap()) throw std::bad_alloc{};
    void* pointer = nullptr;
    if (alignment) {
        if (posix_memalign(&pointer, alignment, size ? size : 1) != 0) pointer = nullptr;
    } else pointer = __real_malloc(size ? size : 1);
    if (!pointer) throw std::bad_alloc{};
    return pointer;
}
void release(void* p) noexcept { if (!reject_heap()) __real_free(p); }
}
void* operator new(std::size_t n) { return allocate(n); }
void* operator new[](std::size_t n) { return allocate(n); }
void* operator new(std::size_t n, std::align_val_t a) { return allocate(n, static_cast<std::size_t>(a)); }
void* operator new[](std::size_t n, std::align_val_t a) { return allocate(n, static_cast<std::size_t>(a)); }
void* operator new(std::size_t n, const std::nothrow_t&) noexcept { try { return allocate(n); } catch (...) { return nullptr; } }
void* operator new[](std::size_t n, const std::nothrow_t&) noexcept { try { return allocate(n); } catch (...) { return nullptr; } }
void* operator new(std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept {
    try { return allocate(n, static_cast<std::size_t>(a)); } catch (...) { return nullptr; }
}
void* operator new[](std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept {
    try { return allocate(n, static_cast<std::size_t>(a)); } catch (...) { return nullptr; }
}
void operator delete(void* p) noexcept { release(p); }
void operator delete[](void* p) noexcept { release(p); }
void operator delete(void* p, std::size_t) noexcept { release(p); }
void operator delete[](void* p, std::size_t) noexcept { release(p); }
void operator delete(void* p, std::align_val_t) noexcept { release(p); }
void operator delete[](void* p, std::align_val_t) noexcept { release(p); }
void operator delete(void* p, std::size_t, std::align_val_t) noexcept { release(p); }
void operator delete[](void* p, std::size_t, std::align_val_t) noexcept { release(p); }
void operator delete(void* p, const std::nothrow_t&) noexcept { release(p); }
void operator delete[](void* p, const std::nothrow_t&) noexcept { release(p); }
void operator delete(void* p, std::align_val_t, const std::nothrow_t&) noexcept { release(p); }
void operator delete[](void* p, std::align_val_t, const std::nothrow_t&) noexcept { release(p); }

// Fixed-storage adapters keep test-framework allocation outside the guarded region.
namespace {
std::string_view data;
std::size_t position;
bool fail_input=false, fail_output=false;
titan::ReadResult read(int, std::span<char> out) noexcept {
    if(fail_input) return {0,true};
    if(position==data.size()) return {0,false};
    out[0]=data[position++]; return {1,false};
}
bool write(int, std::span<const char>) noexcept {return !fail_output;}
}
int main() {
    allocation_forbidden=true;
    auto* a=__wrap_malloc(8); auto* b=::operator new(8,std::nothrow);
    allocation_forbidden=false;
    if(a || b || heap_attempts!=2) return 2;
    titan::Workspace w{};
    for(auto input : {std::string_view{"$1;2;3;;|"},std::string_view{"$10;2;3;0;-4;5;6;-7;|"},
                     std::string_view{"$|"},std::string_view{"$1;\0;3;;|",10},std::string_view{""}}) {
        for(int failure=0;failure<3;++failure) {
            data=input; position=0; fail_input=failure==1; fail_output=failure==2;
            heap_attempts=0; allocation_forbidden=true;
            titan::depacket_and_output({0,read},{1,write},{2,write},w);
            allocation_forbidden=false;
            if(heap_attempts) return 1;
        }
    }
    std::puts("PASS: no heap activity in tested success and failure paths");
}
