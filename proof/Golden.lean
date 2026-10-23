import TitanFormat.Model
/-!
Print the model output for a fixed set of inputs, one line each, separated by TAB:
`H <input bytes as hex> <putHex output>` or `I <decimal value> <putInt output>`.
`bridge/check.cpp` reads these lines and compares them with the C++ code.
-/
open TitanFormat

def compactHex (bs : List UInt8) : String :=
  String.join (bs.map fun b => String.ofList (hexPair b))

def hexCases : List (List UInt8) :=
  let all1 := (List.range 256).map fun a => [a.toUInt8]
  let all2 := (List.range 65536).map fun n => [(n / 256).toUInt8, (n % 256).toUInt8]
  let lens := ((List.range 41) ++ [64, 100]).map fun len =>
    (List.range len).map fun i => (37 * i + 11 * len).toUInt8
  [[]] ++ all1 ++ all2 ++ lens

def intCases : List Int :=
  let pows := (List.range 19).flatMap fun k =>
    let p : Int := 10 ^ k
    [p - 1, p, p + 1, -(p - 1), -p, -(p + 1)]
  let sweep := (List.range 4001).map fun (n : Nat) => (n : Int) - 2000
  [-(2^63), -(2^63) + 1, 2^63 - 1, 2^63 - 2, 123456789, -123456789] ++ pows ++ sweep

def main : IO Unit := do
  let out ← IO.getStdout
  for bs in hexCases do
    out.putStrLn s!"H\t{compactHex bs}\t{String.ofList (putHex bs)}"
  for v in intCases do
    out.putStrLn s!"I\t{v}\t{String.ofList (putInt v)}"
