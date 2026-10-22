# Test contract and commands

Malformed packets are dropped without output records; the next valid packet must still be decoded. Packet boundaries are `$` and `|`. CR/LF outside complete packets are ignored. The suite does not require line breaks inside fields to preserve their values. This suite assumes supported commands are 1, 10 and 12, header numbers are nonnegative, ping payloads may contain opaque data displayed as hex, and housekeeping contains exactly five signed decimal fields with a nonnegative status. Unknown-command policy and integer widths beyond the signed conversion API remain design choices: the supported-command assumption is explicit, not a claim that the conflicting challenge sources define it uniquely.

The output oracle uses this implementation's flat field names and eight-character display convention. It does not require sibling YAML field names, error records, source offsets, raw prefixes, flushing callbacks or allocation-failure recovery. Incomplete/restarted packets are dropped. Oversize input is checked against the actual 16 KiB packet-content buffer. A stream-level oversize return is permitted; recovery output is still checked.

```sh
pixi install
./test.sh            # all stages, extensive mode
pixi run check
pixi run mutation
pixi run benchmark
pixi run status
pixi run stop
```

Campaigns run in the foreground with owned child process groups, per-command timeouts, and a status file that identifies the process, birth tick, operation and held resources. Run status or stop from a second terminal. Stop requests are observed between operations and while polling children; they terminate the active child group. Only run one campaign at a time. No remote compute is needed for these finite workloads.

`check` builds separate Release and ASan/UBSan trees, then runs the C++ assertions, heap guard and Python suite in both. The full command returns nonzero if any suite fails. To run a single Python test, use `pixi run python tests/test_yaml.py OutputTests.test_ping`. Set `TITAN_EXE` to select a different executable. `ctest --test-dir build-autotests --output-on-failure` runs just the registered C++ suites.

Each C++ group has an intent comment; each Python test has an intent docstring. The C++ runner evaluates every named assertion even when earlier assertions fail. Python subtests keep byte and boundary cases independent. Four Hypothesis properties use up to 100 examples each (set `HYPOTHESIS_MAX_EXAMPLES` to change this; `test.sh` uses 2000), deterministic generation, and no timing deadline; CLI calls have a three-second timeout. Hypothesis may shrink failures, so 100 is a configured limit rather than a promise of exactly 100 process launches.

# Port map

| Source | Adaptation |
| --- | --- |
| solution1/cpp/tests/tests.cpp | Signed negative conversion example, extended to full signed boundaries and rejection cases. |
| solution2_with_ai/tests/tests.cpp | Framing, byte safety, limit canaries, integer formatting, read/write fault injection and workspace reuse through descriptor callbacks. |
| solution2_with_ai/tests/test_yaml.py and oracle.py | Independent known answers and flat-schema assertions, generated headers/payloads, binary bytes, line breaks outside complete packets, capture count and malformed recovery. No wholesale oracle import: its malformed-record policy does not apply here. |
| solution2_with_ai/tests/campaign.py | Isolated source mutations, baseline accounting, finite campaigns and persisted provenance. |
| solution3_no_heap/tests/no_heap.cpp | C/C++ allocation guard, self-check and fixed-storage adapters for the integer-descriptor API. |
| solution3_no_heap/tests/benchmark.py | File-based workloads, repeated CLI timing, user/system CPU, maximum RSS, throughput and source/workload hashes. |

`mutation` compiles disposable copies of `src/titan.cpp` against the C++ test runner. Nine behavioral mutations must cause new named failures relative to the already failing baseline to count as killed. Compiler failures and incomplete runs do not count. A tenth mutation, `fix_overflow_boundary_control`, was written as a positive control that repaired the packet-size boundary. The boundary is now fixed in `src/titan.cpp`, so this mutation creates an off-by-one error and the tests kill it; see `DEFECTS.md`. Input mutation tests separately delete, insert and flip bytes in packets. Neither kind changes production files.

`benchmark` processes 100,000 packets per workload, three trials each, with stdout directed to `/dev/null`. It reports medians, individual trials, CPU time and process peak RSS. Timings include startup and I/O and have about 20 ms polling resolution. A fixed-storage resource probe counts read/write requests and output bytes. These are current-version measurements, not a speed contest against siblings with different output obligations. Peak RSS includes runtime overhead, not just the workspace.

# Limits of the evidence

This is a finite port, not exhaustive verification. It does not include a coverage-guided libFuzzer campaign, instruction/branch coverage, a multi-compiler matrix, injected OS-level EINTR/partial-write scheduling, SIGPIPE disposition tests, or long-duration RSS-growth measurements. The one-byte input request makes reader chunk-size variations uninformative here; overreporting and read failures are tested instead. The allocation guard catches linked C allocation calls and C++ new/delete during tested conversions, not allocator calls internal to separately loaded shared libraries or runtime startup. Locale tests use installed process locales; they do not claim arbitrary global C++ locale coverage. The current API has no flush operation to inject.

Remaining numeric interpretation cases include the desired upper bound for header integers, leading-zero YAML semantics, and whether a final housekeeping separator is optional. Current tests require the delimiter form present in the capture. These are candidates for future tests once their desired behavior is agreed.

Evidence is stored in `reports/checks.json`, `reports/mutations.json`, `reports/performance.json` and the adjacent logs. `DEFECTS.md` groups repeated failing assertions into root causes; failure counts are not defect counts.

# Profiling and visual report

Run `pixi run profile`, then open `reports/profile/index.html` in a browser. This offline report needs no external scripts or server. Select ping or housekeeping to view three normal Release timings, the userspace/kernel CPU split, and a separate syscall-frequency report. When perf access is available, it also shows a userspace flame graph: click a frame to zoom, reset to return, or search for a function name. Width represents samples, not exact elapsed time. Stack depth is displayed downward from callers to callees.

The campaign uses installed `/usr/bin/time`, `strace` and `perf`; it installs no profiling dependencies. Normal timings process 300,000 packets per trial; strace uses 1,000 packets to limit overhead. Trace timings are not normal-run syscall cost estimates. Loader reads are included in syscall counts. Perf uses 999 Hz userspace CPU-clock sampling with DWARF unwinding and a separate Release build with debug information. Inlining, unavailable library symbols and incomplete stacks limit attribution. Kernel CPU is measured by time but excluded from this flame graph.

If perf is restricted, the CPU and syscall panels still work and `perf-access.log` records the reason. On this host, changing `kernel.perf_event_paranoid` from 4 to 2 permits own-process userspace profiling while retaining kernel restrictions; other security controls may still apply. Grey must execute any local sudo command. Rerun the profile after access changes. Raw timing, trace, perf and JSON files remain beside the HTML. `pixi run status` and `pixi run stop` also apply to profiling.

# Debug Python tests in CLion

The shared run configuration `Python newline noise (Debug decoder)` uses `.pixi/envs/default/bin/python`, runs `test_yaml.OutputTests.test_newline_noise`, and sets `TITAN_EXE=cmake-build-debug/recode`. Build the `recode` Debug target before running it; this Python configuration does not build C++ automatically. Select the configuration, set a Python breakpoint in the test, and choose Debug. The existing gutter-created configurations also work with their `tests/` working directory: executable and capture paths are resolved relative to the repository root. Relative `TITAN_EXE` overrides are also repository-relative; absolute paths remain absolute.

Python debugging steps through test generation, subprocess invocation and assertions. It does not step into the native C++ subprocess. For decoder breakpoints, use a native CMake Debug configuration with a reproducible input, or the C++ test target. The subprocess timeout still applies if the native child is paused in a separate debugger.
