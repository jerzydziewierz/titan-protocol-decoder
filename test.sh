#!/usr/bin/env bash
# Run every test suite in extensive mode. Continue after a failed stage; report all stages at the end.
# Usage: ./test.sh            (HYPOTHESIS_MAX_EXAMPLES=N ./test.sh to change the property-test depth)
set -u
cd "$(dirname "$0")"
examples="${HYPOTHESIS_MAX_EXAMPLES:-2000}"
declare -a summary=()
failed=0

trap 'echo "test.sh: stopped by signal"; exit 130' INT TERM

stage() {  # stage <name> <command...>
    local name="$1"; shift
    echo "=== $name"
    if "$@"; then summary+=("PASS  $name"); else summary+=("FAIL  $name"); failed=1; fi
}

stage "pixi environment" pixi install
stage "check: C++ assertions, no-heap guard, Python suite (Release + ASan/UBSan)" pixi run check
for tree in build-autotests build-autotests-sanitize; do
    stage "Hypothesis x$examples against $tree" bash -c 'set -o pipefail
        HYPOTHESIS_MAX_EXAMPLES="$1" TITAN_EXE="$2/recode" pixi run python tests/test_yaml.py 2>&1 \
            | tee "reports/extensive-$2-python.log"' _ "$examples" "$tree"
done
stage "mutation campaign" pixi run mutation
stage "benchmark" pixi run benchmark
stage "profile" pixi run profile

echo; echo "=== Summary (logs and JSON in reports/)"
printf '%s\n' "${summary[@]}"
exit "$failed"
