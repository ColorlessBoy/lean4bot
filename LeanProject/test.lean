namespace PlayGround
theorem Or.elim : ∀ {a b c : Prop}, a ∨ b → (a → c) → (b → c) → c := by
  intro a b c h h1 h2
  exact Or.rec h1 h2 h
