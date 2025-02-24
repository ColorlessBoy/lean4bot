namespace PlayGround
theorem Exists.imp : ∀ {α : Sort u} {p q : α → Prop}, (∀ (a : α), p a → q a) → Exists p → Exists q := by
  intro α p q h h1
  exact Exists.rec (fun a ha => Exists.intro a (h a ha)) h1
