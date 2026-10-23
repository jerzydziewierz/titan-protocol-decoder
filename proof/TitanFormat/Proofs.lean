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

theorem hexDigit_ne_paren : ∀ n, n < 16 → hexDigit n ≠ ')' := by decide

/-- In range, `intChars` fits in eight characters. -/
theorem intChars_length (v : Int) (lo : -10^7 < v) (hi : v < 10^8) : (intChars v).length ≤ 8 := by
  unfold intChars
  split
  · have := decDigits_length v.natAbs 6 (by omega); simp; omega
  · have := decDigits_length v.natAbs 7 (by omega); omega

/-- I1: the output of `put_int` always has eight characters. -/
theorem putInt_length (v : Int) : (putInt v).length = 8 := by
  unfold putInt
  split
  · rfl
  · split
    · rfl
    · have := intChars_length v (by omega) (by omega)
      simp only [List.length_append, List.length_replicate]
      omega

/-- I2: in the range that fits in eight characters, the output gives back the value. -/
theorem putInt_roundtrip (v : Int) (lo : -10^7 < v) (hi : v < 10^8) :
    readInt (putInt v) = v := by
  have h1 : ¬ v ≥ 10^8 := by omega
  have h2 : ¬ v ≤ -10^7 := by omega
  simp only [putInt, h1, h2, ite_false]
  unfold intChars
  split
  · rw [readInt, dropWhile_replicate]
    simp [List.dropWhile, readDec_decDigits]
    omega
  · rw [readInt, dropWhile_replicate, dropWhile_space_digits]
    have hne : ∀ ds, decDigits v.natAbs ≠ '-' :: ds := by
      intro ds h
      obtain ⟨k, hk, hc⟩ := decDigits_digits v.natAbs '-' (by rw [h]; simp)
      exact hexDigit_ne_minus k (by omega) hc.symm
    split
    · rename_i ds h; exact absurd h (hne ds)
    · rw [readDec_decDigits]; omega

/-- I3: a value of 10^8 or more prints as `" (large)"`. -/
theorem putInt_large (v : Int) (h : v ≥ 10^8) : putInt v = " (large)".toList := by
  unfold putInt; rw [if_pos h]

/-- I4: a value of −10^7 or less prints as `"-(large)"`. -/
theorem putInt_large_neg (v : Int) (h : v ≤ -10^7) : putInt v = "-(large)".toList := by
  have : ¬ v ≥ 10^8 := by omega
  unfold putInt; rw [if_neg this, if_pos h]

/-- In range, the output has no `)`, so it never looks like a marker. -/
theorem putInt_no_paren (v : Int) (lo : -10^7 < v) (hi : v < 10^8) : ')' ∉ putInt v := by
  have h1 : ¬ v ≥ 10^8 := by omega
  have h2 : ¬ v ≤ -10^7 := by omega
  simp only [putInt, h1, h2, ite_false, List.mem_append, List.mem_replicate]
  intro h
  rcases h with ⟨_, h⟩ | h
  · exact absurd h (by decide)
  · unfold intChars at h
    have hd : ')' ∉ decDigits v.natAbs := fun hm => by
      obtain ⟨k, hk, hc⟩ := decDigits_digits v.natAbs ')' hm
      exact hexDigit_ne_paren k (by omega) hc.symm
    split at h
    · simp at h; exact hd h
    · exact hd h

/-- I5: `put_int` loses no data silently. Two values give the same text only if they are equal
or both are out of range on the same side. This holds for every `int64_t` and beyond. -/
theorem putInt_no_silent_loss (a b : Int) (h : putInt a = putInt b) :
    a = b ∨ (a ≥ 10^8 ∧ b ≥ 10^8) ∨ (a ≤ -10^7 ∧ b ≤ -10^7) := by
  have pos : ')' ∈ " (large)".toList := by decide
  have neg : ')' ∈ "-(large)".toList := by decide
  have dif : " (large)".toList ≠ "-(large)".toList := by decide
  by_cases ha : -10^7 < a ∧ a < 10^8
  · by_cases hb : -10^7 < b ∧ b < 10^8
    · left
      rw [← putInt_roundtrip a ha.1 ha.2, ← putInt_roundtrip b hb.1 hb.2, h]
    · exfalso
      apply putInt_no_paren a ha.1 ha.2
      rw [h]
      by_cases hb' : b ≥ 10^8
      · rw [putInt_large b hb']; exact pos
      · rw [putInt_large_neg b (by omega)]; exact neg
  · by_cases hb : -10^7 < b ∧ b < 10^8
    · exfalso
      apply putInt_no_paren b hb.1 hb.2
      rw [← h]
      by_cases ha' : a ≥ 10^8
      · rw [putInt_large a ha']; exact pos
      · rw [putInt_large_neg a (by omega)]; exact neg
    · right
      by_cases ha' : a ≥ 10^8 <;> by_cases hb' : b ≥ 10^8
      · left; exact ⟨ha', hb'⟩
      · rw [putInt_large a ha', putInt_large_neg b (by omega)] at h; exact absurd h dif
      · rw [putInt_large_neg a (by omega), putInt_large b hb'] at h; exact absurd h (Ne.symm dif)
      · right; omega

end TitanFormat

-- What each proof trusts. Expected: only `propext`, `Classical.choice`, `Quot.sound`; never `sorryAx`.
#print axioms TitanFormat.putHex_fits_buffer
#print axioms TitanFormat.putHex_roundtrip
#print axioms TitanFormat.putHex_injective
#print axioms TitanFormat.putInt_length
#print axioms TitanFormat.putInt_roundtrip
#print axioms TitanFormat.putInt_no_silent_loss
