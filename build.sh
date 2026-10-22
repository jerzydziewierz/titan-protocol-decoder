cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
./build/recode < data/titan-protocol-capture.txt > results/output.yaml


