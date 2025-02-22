example : {a b c : Prop} -> Or a b -> (a -> c) -> (b -> c) -> c := by
  intro a b c hab hac hbc
  apply Or.rec
  exact hac
  exact hbc
