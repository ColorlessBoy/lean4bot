namespace PlayGround
theorem Exists.imp : {α : Sort u} → {p q : α → Prop} → (∀ (a : α), p a → q a) → Exists p → Exists q := by
  intro α p q h h1
  apply Exists.rec
  intro a ha
  apply Exists.intro a
  exact h a ha
  exact h1
