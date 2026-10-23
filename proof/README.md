# Formal proof: `put_hex` and `put_int`

Local only. Core Lean 4 (toolchain in `lean-toolchain`), no Mathlib, no external service.

## Run

```
./bridge.sh
```

It does three steps: `lake build` checks all proofs, `lake exe golden` prints the model output for 69 957 inputs, and `bridge/check` (C++, with ASan and UBSan) compares these lines with `src/titan.cpp`. The last line must be `69957 cases, 0 mismatches`.

## Files

| File | Contents |
|---|---|
| `TitanFormat/Model.lean` | A hand copy of `put_hex` and `put_int` as pure functions |
| `TitanFormat/Proofs.lean` | The theorems and their proofs; `#print axioms` at the end |
| `Golden.lean` | Prints model outputs for the bridge |
| `bridge/check.cpp` | Runs the real C++ functions on the same inputs and compares |

## What is proven (for all inputs of the model)

| ID | Theorem | Says |
|---|---|---|
| H1 | `hexBody_length` | n bytes give 3n−1 characters |
| H2 | `putHex_fits_buffer` | the output never exceeds `out_chars[32*3-1]` |
| H3 | `readHex_hexBody` | hex text reads back to the same bytes |
| H4 | `putHex_roundtrip` | `put_hex` output reads back to the first 32 bytes |
| H5 | `putHex_length` | `" ..."` appears exactly when the message is longer than 32 bytes |
| H6 | `putHex_injective` | different messages of at most 32 bytes give different text |
| I1 | `putInt_length` | `put_int` always writes 8 characters |
| I2 | `putInt_roundtrip` | for −10^7 < v < 10^8, the text reads back to v |
| I3 | `putInt_loses_sign` | finding: `-123456789` prints as `23456789` |
| I4 | `putInt_not_injective` | finding: two different `int64_t` values print the same |

I3 and I4 are bugs in `put_int`: the YAML loses data for values outside the I2 range. The caller also passes `uint64_t` fields to `put_int(int64_t)`.

## Mutation check (the proofs are not vacuous)

| Change | Result |
|---|---|
| `Model.lean`: `hexPair` uses `b.toNat / 16` for the low digit | H3 fails |
| `Model.lean`: `hexBufferSize` is `32 * 3 - 2` | H2 fails |
| `titan.cpp`: lowercase hex table | bridge: 55 734 mismatches |
| `titan.cpp`: `substr(0, 33)` | UBSan: index 95 out of bounds |

Undo each change after the check.

## What the proof does not cover

The theorems are about `Model.lean`, not about the compiled C++ code. The bridge reduces this gap but does not close it: it is exhaustive for `put_hex` inputs of 0–2 bytes and samples longer inputs, and it samples `put_int` at all powers of ten, the `int64_t` limits and −2000…2000. The model also assumes that `std::to_chars` and `std::from_chars` behave as the standard says.
