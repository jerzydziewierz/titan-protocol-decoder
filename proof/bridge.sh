#!/usr/bin/env bash
# Prove the model, then compare the model with the C++ code.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.elan/bin:$PATH"
lake build
lake exe golden > bridge/golden.tsv.tmp && mv bridge/golden.tsv.tmp bridge/golden.tsv
g++ -std=c++20 -O1 -Wall -Wextra -fsanitize=address,undefined -I.. bridge/check.cpp ../src/titan.cpp -o bridge/check
./bridge/check < bridge/golden.tsv
