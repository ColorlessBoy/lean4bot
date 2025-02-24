namespace PlayGround
theorem not_not_em : (a : Prop) -> Not (Not (Or a (Not a))) := by
  intro a h
  apply h
  apply Or.inr
  intro ha
  apply h
  apply Or.inl
  exact ha
