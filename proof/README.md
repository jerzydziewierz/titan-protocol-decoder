# Formal proof: `put_hex` and `put_int`

Local only, no external service. Two methods check the same two functions:

* **Lean 4** (core only, toolchain in `lean-toolchain`, no Mathlib) proves properties of a model, for all inputs, with no bound.
* **Bounded model checking** (CBMC and ESBMC, in `bmc/`) proves properties of the real C++ code in `src/format.cpp`, for all inputs up to a bound.

`put_int` and `put_hex` in `src/titan.cpp` only send the result of `format_int` and `format_hex` (`src/format.cpp`) to the sink. `format.cpp` uses no standard library, so that both checkers can read it.

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
| I3 | `putInt_large` | v ≥ 10^8 prints as `" (large)"` |
| I4 | `putInt_large_neg` | v ≤ −10^7 prints as `"-(large)"` |
| I5 | `putInt_no_silent_loss` | two values print the same only if they are equal, or both are out of range on the same side |

## Mutation check (the proofs are not vacuous)

| Change | Result |
|---|---|
| `Model.lean`: `hexPair` uses `b.toNat / 16` for the low digit | H3 fails |
| `Model.lean`: `hexBufferSize` is `32 * 3 - 2` | H2 fails |
| `titan.cpp`: lowercase hex table | bridge: 55 734 mismatches |
| `titan.cpp`: `substr(0, 33)` | UBSan: index 95 out of bounds |
| `Model.lean`: negative limit `-10^8` | I1 and I2 fail |
| `titan.cpp`: `message > 100'000'000` | bridge: 1 mismatch at 10^8 (17 characters) |

Undo each change after the check.

## Bounded model checking (`bmc/`)

```
bmc/run.sh           # about 8 minutes
bmc/run.sh --quick   # about 45 seconds, without CBMC format_int
```

Each line must say `VERIFICATION SUCCESSFUL`. The tools check the real `src/format.cpp`. Array bounds, pointer use, signed overflow and loop unwinding are checked automatically; the harnesses add the properties.

| Harness | Inputs | Checks | ESBMC | CBMC |
|---|---|---|---|---|
| `put_int.cpp` | every `int64_t` (no bound) | I1–I4 | 26 s | 7 min |
| `put_hex.cpp` | every message of 0–34 bytes | H2–H5 | 14 s | 2 s |

Tool versions: CBMC 5.95.1 (Ubuntu `apt`), ESBMC 8.6.0 (GitHub release, SHA-256 checked, in `~/opt/esbmc-v8.6/`; set `ESBMC` to use another path).

Mutation check with ESBMC: each change below makes the run fail.

| Change in `src/format.cpp` / `format.hpp` | Result |
|---|---|
| `v >= 100000000` becomes `v > 100000000` | array bounds violated (9 digits in 8 characters) |
| the `-` sign is not written | read-back assertion fails |
| low nibble uses `data[i] >> 4` | read-back assertion fails |
| `hex_capacity = 98` | array bounds violated |

Tool limits that shaped `src/format.cpp`:

* CBMC 5.95 accepts C++11 at most and cannot parse the GCC 13 standard headers. ESBMC replaces `std::string_view` with its own model, which has no `find_first_of(char)`. Thus `format.cpp` includes only `<cstddef>` and `<cstdint>`.
* `std::to_chars` on 64 bits did not finish in ESBMC within 15 minutes. `format_int` checks the range first, and then divides a 32-bit value at most 8 times.
* CBMC 5.95 initialises namespace constants in alphabetical order. `hex_capacity` is therefore the literal 99; a `static_assert` in `titan.cpp` checks it against `hex_max_bytes`.
* CBMC did not find a function body when the definition had `const` parameters and the declaration did not. It then treats the result as "any value". `run.sh` fails when it sees "no body for function titan".

## What is not covered

* Lean: the theorems are about `Model.lean`, not about the compiled C++ code. The bridge compares the two on 69 957 inputs; this is a test, not a proof.
* Bounded model checking: `format_hex` is checked up to 34 bytes. Longer messages run the same code (at most 32 pairs, then `" ..."`), but no tool proves this step. The checkers assume that the compiler translates the code as the C++ standard says.
* The wrappers `put_int` and `put_hex` (two lines each) and the sink are not checked by a tool.
