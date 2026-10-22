cmake_minimum_required(VERSION 3.16)
project(titan_learned LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(titan STATIC src/titan.cpp)
target_include_directories(titan PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")

add_executable(recode src/main.cpp)
target_link_libraries(recode PRIVATE titan)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(titan PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(recode PRIVATE -Wall -Wextra -Wpedantic)
endif()
