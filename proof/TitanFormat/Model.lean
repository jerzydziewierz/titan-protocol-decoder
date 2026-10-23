/-!
# Model of `put_hex` and `put_int` (src/titan.cpp)

This file is a hand copy of the two C++ formatters, as pure functions that return the characters
that the C++ code sends to the sink. The proofs are about this copy. `bridge/check.cpp` compares
the copy with the real C++ code (see `README.md`).
-/
namespace TitanFormat

/-! ## put_hex -/

/-- `hex[n]` in the C++ code: `"0123456789ABCDEF"`. -/
def hexDigit (n : Nat) : Char :=
  if n < 10 then Char.ofNat (48 + n) else Char.ofNat (55 + n)

/-- `hex[byte >> 4]`, `hex[byte & 15]`. -/
def hexPair (b : UInt8) : List Char :=
  [hexDigit (b.toNat / 16), hexDigit (b.toNat % 16)]

/-- The loop: a space before each byte except the first. -/
def hexBody : List UInt8 → List Char
  | [] => []
  | [b] => hexPair b
  | b :: rest => hexPair b ++ ' ' :: hexBody rest

/-- C++ size of `out_chars`. -/
def hexBufferSize : Nat := 32 * 3 - 1

/-- `put_hex`: at most 32 bytes, then `" ..."` if the message is longer. -/
def putHex (msg : List UInt8) : List Char :=
  hexBody (msg.take 32) ++ (if msg.length > 32 then " ...".toList else [])

/-! ## put_int -/

/-- Decimal digits of a natural number, most significant first (`std::to_chars`). -/
def decDigits (n : Nat) : List Char :=
  if n < 10 then [hexDigit n] else decDigits (n / 10) ++ [hexDigit (n % 10)]

/-- `std::to_chars` for a signed integer. -/
def intChars (v : Int) : List Char :=
  if v < 0 then '-' :: decDigits v.natAbs else decDigits v.natAbs

/-- `put_int`: a fixed marker if the value does not fit in eight characters, else pad on the left
with spaces to eight. -/
def putInt (v : Int) : List Char :=
  if v ≥ 10^8 then " (large)".toList
  else if v ≤ -10^7 then "-(large)".toList
  else
    let d := intChars v
    List.replicate (8 - d.length) ' ' ++ d

/-- The range of `std::int64_t`. -/
def isInt64 (v : Int) : Prop := -2^63 ≤ v ∧ v < 2^63

/-! ## Readers used only to state round trips -/

def hexVal (c : Char) : Nat :=
  if c.toNat < 58 then c.toNat - 48 else c.toNat - 55

/-- Read back the output of `hexBody`: pairs of hex digits with one space between pairs. -/
def readHex : List Char → List UInt8
  | hi :: lo :: ' ' :: rest => (16 * hexVal hi + hexVal lo).toUInt8 :: readHex rest
  | [hi, lo] => [(16 * hexVal hi + hexVal lo).toUInt8]
  | _ => []

/-- Read decimal digits (most significant first). -/
def readDec (cs : List Char) : Nat :=
  cs.foldl (fun acc c => 10 * acc + hexVal c) 0

/-- Read the output of `putInt`: skip the left spaces, an optional `-`, then digits. -/
def readInt (cs : List Char) : Int :=
  match cs.dropWhile (· == ' ') with
  | '-' :: ds => -(readDec ds : Int)
  | ds => readDec ds

end TitanFormat
