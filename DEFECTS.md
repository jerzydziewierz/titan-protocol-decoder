# Decoder defects and test evidence

Scope: the decoder in `src/` on this branch, as measured by `./test.sh`. The contract is that malformed packets are dropped. The test oracle uses the flat output schema and the intentional eight-character display width. The campaign JSON files in `reports/` record the source hashes.

## Open defects

| ID | Severity | Reproducer and observed behavior | Evidence |
| --- | --- | --- | --- |
| D03 | High: invalid YAML | `$10;2;3;0;1;2;12345678;-1234567;\|` emits `housekeeping_intensity:12345678` and `housekeeping_temperature:-1234567` without a space after the colon, so PyYAML rejects the document. This happens to any value that fills all eight display characters: 8 or more digits, or a negative value with 7 or more digits. | Four `test_truncation_yaml` cases. In extensive mode, `test_generated_housekeeping` also finds it, because its generator reaches negative 7-digit values. |
| D05 | High: malformed packet emitted | When the header is valid but the housekeeping payload is not, the decoder emits a partial record (the header fields and `payload_hex`, but no housekeeping fields) and exits 0. Reproducers: `$10;2;3;0;bad;\|` (field cannot be converted) and `$10;2;3;0;1;2;3;4;5;\|` (surplus sixth field, formerly D06). | `test_malformed_dropped`, 2 subcases. See "Known problems" in `README.md`. |
| D07 | Medium: signed header accepted | `$1;-1;2;;\|` emits a record with `sequence_number: -1` instead of dropping the packet. | `test_malformed_dropped`, 1 subcase. |

## Policy-dependent finding

D10: `$99;2;3;\|` is emitted with `interpreted_command: Unknown`. The suite assumes that only commands 1, 10 and 12 are supported, so this fails `test_malformed_dropped`. If unknown commands are valid opaque packets, change this assertion. This is not a memory-safety defect.

## Closed defects

✅ D01: in support of memory safety, when a packet body reaches the input-buffer limit, `depacket_and_output` drops it before it writes past the buffer and returns oversize. The canary and boundary assertions pass.

✅ D02: in support of no silent data loss, when a write callback fails, the decoder reports an output error and the CLI exits nonzero (`test_full_output_device`, 18 write-failure injection points).

✅ D04: in support of the read-callback contract, when a successful read reports more bytes than the destination span holds, the decoder returns `invalid_read_size`.

✅ D06: in support of strict housekeeping parsing, when a sixth payload field is present, the housekeeping layer rejects it. The record is still emitted partially; see D05.

✅ D08: ping payloads may be nonempty; the decoder shows a bounded hex preview. This is accepted behavior.

✅ D09: only CR/LF outside complete packets must be ignored; line breaks inside numeric fields are not required to work. 

## Passing evidence and measurements

C++ assertions: 327 of 327 pass in both the Release and the ASan/UBSan builds. The heap guard passes in both builds. Python suite: 19 test methods. In each build, 4 `test_malformed_dropped` subcases fail (D05 ×2, D07, D10) and 4 `test_truncation_yaml` subcases fail with YAML errors (D03). Extensive mode (2000 Hypothesis examples per property) adds the `test_generated_housekeeping` error (D03). It finds no other defects.

Mutation campaign: all nine behavioral mutations are killed by new named failures. ⚠️ The tenth mutation, `fix_overflow_boundary_control`, was a positive control that repaired D01 in a copy of the source. Now that D01 is fixed in `src/titan.cpp` (`> size()-2`), the same text replacement creates an off-by-one error instead. The tests kill it (`packet boundary error 16383`), so it is no longer a control.

Benchmark, 100,000 packets, median of three Release trials: about 99,600 ping packets/s (0.86 MiB/s), 44,900 housekeeping packets/s (0.90 MiB/s) and 207,000 malformed packets/s discarded (1.58 MiB/s). Peak process RSS is about 3.4–3.5 MiB. The resource probe counts 900,001 read calls, 1,800,000 write calls and 11,700,000 output bytes for 100,000 ping packets: nine reads and eighteen writes per packet. The workspace is 81,920 bytes. Most of the run time is kernel time; see the profile below.

Profile (`reports/profile/index.html`, with `kernel.perf_event_paranoid=2`): 300,000 packets per trial, three Release trials. Ping takes 2.94 s wall time (0.52 s user, 2.42 s system). Housekeeping takes 6.56 s (1.17 s user, 5.38 s system). So about 82 % of CPU time is in the kernel. The strace for 1,000 ping packets counts 18,000 `write` and 9,005 `read` calls: 18 writes and 9 reads per packet, the same as the resource probe. The user-space flame graph (999 Hz, 555 ping samples and 1,216 housekeeping samples) has the same shape for both workloads. About 47 % of the samples are in the libc `write` wrapper and about 25 % in the libc `read` wrapper. `outer::write_bytes` and `outer::read_bytes` take 13–16 % more. The decoder itself (`depacket_and_output`, `decode_header_and_output`, `put_msg`, `put_int`) takes less than 12 % self time. 💡 The decoder's own computation is not the bottleneck. The cost is one syscall for each input byte and one for each output fragment. A buffered reader and writer, which flush at packet boundaries, would remove most of it. This also matches the transactional writer proposed for D05 in `README.md`. No optimization has been made.

## Deferred coverage

See `tests/README.md` for the commands and the limits of the evidence. The tests do not claim to be exhaustive.
