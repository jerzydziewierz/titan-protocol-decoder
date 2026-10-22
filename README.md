# This is the `autotests` branch

Do NOT merge into `handmade` branch!

see the `README.md` in `handmade` branch for why.


# What is this

This test suite tests for the following:

* General correctness of the output
* Adversarial testing to find any memory problems
* Adversarial testing with damaged input data
* Performance testing

# Known problems

* For an overall invalid packet where the header is good, but the payload data (e.g. housekeeping data) is damaged, the program will output partial output.
    * Workaround: None
    * To Do: there are at least 3 solutions to this; preferably, upgrade the writer object to support transactional mode, where output contents are buffered and then in the end can be commited or discarded at any time.

# What is being tested

## How to run

Requirements in addition to the `handmade` ones: `pixi` (the environment uses the Anaconda `main` channel only), and `/usr/bin/time`, `strace` and `perf` for the benchmark and profile stages.

* `./test.sh` : runs ALL tests in extensive mode and continues after a failed stage. It prints a PASS/FAIL summary and returns nonzero if a stage failed. It takes about 2–3 minutes. Set `HYPOTHESIS_MAX_EXAMPLES` to change the property-test depth (default 2000).
* `pixi run check` : the normal (non-extensive) correctness run. `ctest --test-dir build-autotests --output-on-failure` runs the C++ suites only.
* `pixi run status` / `pixi run stop` : show or stop a running campaign, from a second terminal.

### GitHub Actions

`.github/workflows/tests.yml` runs `./test.sh` on each push to `autotests`, on each pull request, and on manual start ("Run workflow" on the Actions tab). Each run shows a report on its summary page: stage results, C++ and heap-guard results, failing Python subcases, mutations, benchmark and profile timings. `tests/ci_summary.py` writes this report. After each push run, the full `reports/` folder and `test-sh.log` are force-pushed as one commit to the `ci-reports` branch; the branch keeps only the latest run. The flame graph is `reports/profile/index.html` on that branch. Download it and open it in a browser. Failing stages and failing tests are shown as warnings on the run page, but they do not fail the job: `DEFECTS.md` lists them as known problems. The job fails only if `test.sh` does not finish.

The workflow imports no actions (no `uses:` lines). It uses shell steps only: plain `git` for checkout and for publishing the reports, a pixi binary checked by SHA-256, Anaconda `main` packages through `pixi.lock`, and Ubuntu apt for `time`, `strace` and `perf`. The runner image itself (`ubuntu-24.04`) is provided by GitHub.

`./test.sh` runs these stages:

| Stage                | What it does                                                                                                                                           | Output in `reports/`                    |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|
| check                | Builds a Release tree and an ASan/UBSan tree. In each tree, runs the C++ assertions, the no-heap guard and the Python suite (100 Hypothesis examples). | `checks.json`, `build-autotests*-*.log` |
| extensive Hypothesis | Runs the Python suite again in both trees with 2000 examples for each property.                                                                        | `extensive-build-autotests*-python.log` |
| mutation             | Compiles changed copies of `src/titan.cpp` against the C++ assertions. A mutation is killed when it causes new named failures.                         | `mutations.json`, `mutation-*.log`      |
| benchmark            | 100,000 packets for each workload (ping, housekeeping, malformed), three trials, output to `/dev/null`. It also counts read/write calls.               | `performance.json`                      |
| profile              | Timings, user/kernel CPU split, syscall counts, and a flame graph if `perf` access is permitted.                                                       | `profile/index.html`                    |

### Enable `perf` temporarily (for the flame graph)

Ubuntu sets `kernel.perf_event_paranoid` to 4 by default. At this level, `perf` cannot sample, so the profile report has no flame graph (`reports/profile/perf-access.log` records the reason). Level 2 lets a user profile their own processes in user space. Kernel profiling stays blocked at this level. The change needs sudo and lasts until the next reboot:

```sh
cat /proc/sys/kernel/perf_event_paranoid               # record the current value, e.g. 4
sudo sysctl -w kernel.perf_event_paranoid=2
pixi run profile                                       # or ./test.sh
sudo sysctl -w kernel.perf_event_paranoid=4            # restore the recorded value
```

Do not write the setting to `/etc/sysctl.d/`; that makes it permanent.

`DEFECTS.md` lists the defects that the tests find now. `tests/README.md` has the full test contract and the limits of the evidence.

## Test files

| File | Kind | Runs in |
| --- | --- | --- |
| `tests/tests.cpp` | C++ unit and fault-injection assertions against the library API | `titan-tests` (ctest `learned-decoder`), mutation |
| `tests/no_heap.cpp` | Heap guard: wraps `malloc`/`calloc`/`realloc`/`free` and `new` | `titan-no-heap` (ctest `learned-no-heap`) |
| `tests/test_yaml.py` | Black-box tests of the `recode` CLI: YAML output, Hypothesis properties, input mutation | check, extensive Hypothesis |
| `tests/resource_probe.cpp` | Counts read/write callback calls and output bytes | benchmark |
| `tests/campaign.py`, `tests/profile_run.py` | Campaign driver: builds, runs, mutates, measures, writes reports | all `pixi run` tasks |

## Short descriptor for each test intent

### `tests/tests.cpp` (C++ assertions)

* Integer conversion: consume the whole field and cover the signed 64-bit limits.
* Integer rejection: reject syntax noise, embedded NUL, and overflow in both directions.
* Fixed-width formatting: keep the rightmost eight characters of a diagnostic number.
* Hex escaping: show every byte value 0–255 as uppercase hex, including control and high-bit bytes.
* Hex preview: exact length limits and an explicit truncation marker.
* `put_msg`: keep the length, including embedded NUL; do not stop at a terminator.
* Empty input: successful empty input emits no packet.
* Workspace reuse: a second conversion does not show fields from the previous one.
* Read failure: a failure at each read position propagates through the public decoder API.
* Read contract: a reader that reports more bytes than the one-byte destination holds is rejected.
* Write failure: a failure at each write position stops conversion and returns an output error.
* Packet boundary: a canary next to the input buffer detects an overflow that ASan cannot see (fields in the same object). Packets of 16383 to 16386 bytes; 16384 and larger are rejected as oversize.
* Housekeeping parsing: reject missing, malformed and surplus fields.
* Header errors: report the error before an incomplete record is emitted.
* Payload errors: an invalid housekeeping payload stays visible to the caller of the header layer.

### `tests/no_heap.cpp`

* Self-check: the guard detects a forbidden `malloc` and `new`.
* No heap: ping, housekeeping, empty, NUL-containing and empty-input conversions make no heap call, in the success, read-failure and write-failure paths.

### `tests/test_yaml.py` (CLI and YAML output)

* `test_loader`: the test YAML loader rejects duplicate keys.
* `test_ping`: a ping record matches known values in the flat schema.
* `test_ping_payload`: an opaque ping payload is shown as a bounded hex preview.
* `test_housekeeping`: signed housekeeping values and both housekeeping IDs (10, 12) are kept.
* `test_generated_ping` (Hypothesis): headers round-trip over the full display range.
* `test_generated_housekeeping` (Hypothesis): generated signed fields go to the correct keys.
* `test_newline_noise`: CR/LF outside packets does not change the records.
* `test_malformed_dropped`: malformed and incomplete packets are dropped, and the next valid packet is decoded.
* `test_each_binary_byte`: each non-decimal byte in a numeric field is rejected.
* `test_arbitrary_binary` (Hypothesis): arbitrary bytes terminate and give parseable, control-safe YAML.
* `test_binary_recovery` (Hypothesis): a valid packet after arbitrary bytes is recovered.
* `test_truncation_yaml`: eight-character truncation keeps the space after the YAML colon.
* `test_capture`: the supplied capture gives one record for each complete packet.
* `test_input_mutations`: deleted, inserted, replaced and flipped bytes do not stop a trailing valid packet.
* `test_oversized_recovery`: an oversized packet is dropped and the next valid packet is decoded.
* `test_locale`: the process locale does not change the number format.
* `test_cli_arguments`: extra CLI arguments are rejected, not read as input paths.
* `test_closed_stdin`: a failed read gives a nonzero exit status.
* `test_full_output_device`: a write to a full device (ENOSPC) gives a nonzero exit status.

### Mutation campaign (`tests/campaign.py mutation`)

Each mutation must be killed by the C++ assertions: 
* accept a numeric suffix, 
* drop the integer sign, 
* preview 31 bytes instead of 32, 
* wrong hex nibble, 
* hide a read failure, 
* reject valid housekeeping, 
* wrong start marker, 
* wrong end marker, 
* skip the first payload byte, 
* off-by-one at the packet-size limit.
