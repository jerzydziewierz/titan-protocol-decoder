import TitanFormat.Model
/-!
# Proofs about `put_hex` and `put_int`

Each theorem holds for **all** inputs of the model. Tests cannot cover these domains: `put_hex`
takes any byte string, and `put_int` takes 2^64 values.
-/
namespace TitanFormat

/-! ## Helper facts -/

theorem hexVal_hexDigit : ∀ n, n < 16 → hexVal (hexDigit n) = n := by decide

theorem hexDigit_ne_space : ∀ n, n < 16 → hexDigit n ≠ ' ' := by decide

theorem hexDigit_ne_minus : ∀ n, n < 16 → hexDigit n ≠ '-' := by decide

theorem byte_split (b : UInt8) :
    (16 * hexVal (hexDigit (b.toNat / 16)) + hexVal (hexDigit (b.toNat % 16))).toUInt8 = b := by
  have hb := b.toNat_lt
  rw [hexVal_hexDigit _ (by omega), hexVal_hexDigit _ (by omega)]
  rw [Nat.div_add_mod]
  exact UInt8.ofNat_toNat

/-! ## put_hex -/

/-- H1: each byte gives two digits, and a space separates bytes. -/
theorem hexBody_length (xs : List UInt8) : (hexBody xs).length = 3 * xs.length - 1 := by
  induction xs with
  | nil => rfl
  | cons b rest ih =>
    cases rest with
    | nil => rfl
    | cons c rest' =>
      simp only [hexBody, hexPair, List.length_append, List.length_cons, List.length_nil] at ih ⊢
      omega

/-- H2: `out_chars` in the C++ code is large enough, for every message. -/
theorem putHex_fits_buffer (msg : List UInt8) : (hexBody (msg.take 32)).length ≤ hexBufferSize := by
  rw [hexBody_length, List.length_take]
  unfold hexBufferSize
  omega

/-- H3: the hex text gives back exactly the bytes. -/
theorem readHex_hexBody (xs : List UInt8) : readHex (hexBody xs) = xs := by
  induction xs with
  | nil => rfl
  | cons b rest ih =>
    cases rest with
    | nil => simp only [hexBody, hexPair, readHex, byte_split]
    | cons c rest' =>
      simp only [hexBody, hexPair, List.cons_append, List.nil_append] at ih ⊢
      simp only [readHex, byte_split, ih]

/-- H4: the output of `put_hex` gives back the first 32 bytes of the message. -/
theorem putHex_roundtrip (msg : List UInt8) :
    readHex (putHex msg |>.take (3 * min msg.length 32 - 1)) = msg.take 32 := by
  have h : (hexBody (msg.take 32)).length = 3 * min msg.length 32 - 1 := by
    rw [hexBody_length, List.length_take]; omega
  unfold putHex
  rw [← h, List.take_left, readHex_hexBody]

/-- H5: `" ..."` is there exactly when the message is longer than 32 bytes. -/
theorem putHex_length (msg : List UInt8) :
    (putHex msg).length = 3 * min msg.length 32 - 1 + (if msg.length > 32 then 4 else 0) := by
  unfold putHex
  rw [List.length_append, hexBody_length, List.length_take]
  split <;> simp <;> omega

/-- H6: two different messages of at most 32 bytes never give the same text. -/
theorem putHex_injective (a b : List UInt8) (ha : a.length ≤ 32) (hb : b.length ≤ 32)
    (h : putHex a = putHex b) : a = b := by
  have hta : a.take 32 = a := List.take_of_length_le ha
  have htb : b.take 32 = b := List.take_of_length_le hb
  unfold putHex at h
  have ha' : ¬ a.length > 32 := by omega
  have hb' : ¬ b.length > 32 := by omega
  simp only [ha', hb', ite_false, List.append_nil, hta, htb] at h
  rw [← readHex_hexBody a, ← readHex_hexBody b, h]

/-! ## put_int -/

theorem decDigits_ne_nil (n : Nat) : decDigits n ≠ [] := by
  unfold decDigits; split <;> simp

theorem decDigits_digits (n : Nat) : ∀ c ∈ decDigits n, ∃ k, k < 10 ∧ c = hexDigit k := by
  induction n using Nat.strongRecOn with
  | _ n ih =>
    unfold decDigits
    split
    · intro c hc; simp at hc; exact ⟨n, by omega, hc⟩
    · intro c hc
      rcases List.mem_append.mp hc with h | h
      · exact ih (n / 10) (by omega) c h
      · simp at h; exact ⟨n % 10, by omega, h⟩

theorem decDigits_length (n k : Nat) (h : n < 10 ^ (k + 1)) : (decDigits n).length ≤ k + 1 := by
  induction k generalizing n with
  | zero => unfold decDigits; split <;> simp_all
  | succ k ih =>
    unfold decDigits
    split
    · simp
    · have := ih (n / 10) (by rw [Nat.pow_succ] at h; omega)
      simp; omega

theorem readDec_append (cs : List Char) (c : Char) :
    readDec (cs ++ [c]) = 10 * readDec cs + hexVal c := by
  simp [readDec, List.foldl_append]

theorem readDec_decDigits (n : Nat) : readDec (decDigits n) = n := by
  induction n using Nat.strongRecOn with
  | _ n ih =>
    unfold decDigits
    split
    · simp [readDec, hexVal_hexDigit n (by omega)]
    · rw [readDec_append, ih (n / 10) (by omega), hexVal_hexDigit _ (by omega)]
      omega

theorem dropWhile_space_digits (n : Nat) : (decDigits n).dropWhile (· == ' ') = decDigits n := by
  cases h : decDigits n with
  | nil => exact absurd h (decDigits_ne_nil n)
  | cons c rest =>
    obtain ⟨k, hk, rfl⟩ := decDigits_digits n c (by rw [h]; simp)
    have hb : (hexDigit k == ' ') = false := beq_eq_false_iff_ne.mpr (hexDigit_ne_space k (by omega))
    simp [List.dropWhile, hb]

theorem dropWhile_replicate (k : Nat) (l : List Char) :
    (List.replicate k ' ' ++ l).dropWhile (· == ' ') = l.dropWhile (· == ' ') := by
  induction k with
  | zero => rfl
  | succ k ih => simp [List.replicate_succ, ih]

/-- I1: the output of `put_int` always has eight characters. -/
theorem putInt_length (v : Int) : (putInt v).length = 8 := by
  simp only [putInt, List.length_append, List.length_replicate, List.length_drop]
  omega

/-- I2: in the range that fits in eight characters, the output gives back the value. -/
theorem putInt_roundtrip (v : Int) (lo : -10^7 < v) (hi : v < 10^8) :
    readInt (putInt v) = v := by
  unfold putInt intChars
  split
  · -- negative: `-` and at most seven digits
    have hl := decDigits_length v.natAbs 6 (by omega)
    have hd : ('-' :: decDigits v.natAbs).length - 8 = 0 := by simp; omega
    dsimp only
    rw [hd, List.drop_zero, readInt, dropWhile_replicate]
    simp [List.dropWhile, readDec_decDigits]
    omega
  · -- zero or positive: at most eight digits
    have hl := decDigits_length v.natAbs 7 (by omega)
    have hd : (decDigits v.natAbs).length - 8 = 0 := by omega
    dsimp only
    rw [hd, List.drop_zero, readInt, dropWhile_replicate, dropWhile_space_digits]
    have hne : ∀ ds, decDigits v.natAbs ≠ '-' :: ds := by
      intro ds h
      obtain ⟨k, hk, hc⟩ := decDigits_digits v.natAbs '-' (by rw [h]; simp)
      exact hexDigit_ne_minus k (by omega) hc.symm
    split
    · rename_i ds h; exact absurd h (hne ds)
    · rw [readDec_decDigits]; omega

/-- I3 (finding): a negative value with more than seven digits loses its sign. -/
theorem putInt_loses_sign : putInt (-123456789) = "23456789".toList := by
  simp [putInt, intChars, decDigits, hexDigit]

/-- I4 (finding): two different `int64_t` values give the same text, so the YAML loses data. -/
theorem putInt_not_injective :
    ∃ a b, isInt64 a ∧ isInt64 b ∧ a ≠ b ∧ putInt a = putInt b :=
  ⟨123456789, -123456789, by unfold isInt64; omega, by unfold isInt64; omega, by decide,
    by simp [putInt, intChars, decDigits, hexDigit]⟩

end TitanFormat

-- What each proof trusts. Expected: only `propext`, `Classical.choice`, `Quot.sound`; never `sorryAx`.
#print axioms TitanFormat.putHex_fits_buffer
#print axioms TitanFormat.putHex_roundtrip
#print axioms TitanFormat.putHex_injective
#print axioms TitanFormat.putInt_roundtrip
#print axioms TitanFormat.putInt_not_injective
