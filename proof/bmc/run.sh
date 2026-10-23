#!/usr/bin/env bash
# Verify src/format.cpp with CBMC and ESBMC. Exit status 0 only if each run says VERIFICATION SUCCESSFUL.
# Times on ws: ESBMC 15 s + 30 s; CBMC 2 s + 7 min (format_int). Use --quick to skip CBMC format_int.
set -uo pipefail
cd "$(dirname "$0")"
ESBMC="${ESBMC:-$HOME/opt/esbmc-v8.6/unpacked/release/bin/esbmc}"
SRC=../../src/format.cpp
status=0

check() { # name, command...
    local name="$1"; shift
    local log; log=$("$@" 2>&1)
    # A missing body makes the tool treat the function as "any result": the run would prove nothing.
    if grep -q 'no body for function titan' <<<"$log"; then echo "$name: NO BODY FOR FUNCTION UNDER TEST"; status=1; return; fi
    if grep -q 'VERIFICATION SUCCESSFUL' <<<"$log"; then echo "$name: VERIFICATION SUCCESSFUL"
    else echo "$name: FAILED"; grep -E 'Violated|FAILURE|ERROR|error:' -A2 <<<"$log" | head -20; status=1; fi
}

CBMC_FLAGS=(--cpp11 -I../.. --bounds-check --pointer-check --signed-overflow-check --unwinding-assertions)
ESBMC_FLAGS=(--std c++20 -I../.. --overflow-check)

check "ESBMC format_hex" "$ESBMC" "${ESBMC_FLAGS[@]}" $SRC put_hex.cpp --unwind 36
check "ESBMC format_int" "$ESBMC" "${ESBMC_FLAGS[@]}" $SRC put_int.cpp --unwind 10
check "CBMC  format_hex" cbmc "${CBMC_FLAGS[@]}" $SRC put_hex.cpp --unwind 36
[[ "${1:-}" == --quick ]] || check "CBMC  format_int" cbmc "${CBMC_FLAGS[@]}" $SRC put_int.cpp --unwind 10
exit $status
