import A2A.Checker

namespace A2A

theorem check_iff_valid (t : Task) (es : List Event) :
    check t es = true ↔ ValidTrace t es := by
  induction es generalizing t with
  | nil => simp [check, ValidTrace.nil]
  | cons e es ih =>
      simp only [check, Bool.and_eq_true, decide_eq_true_eq, ih]
      constructor
      · rintro ⟨h, hs⟩; exact .cons h hs
      · intro h; cases h with | cons h hs => exact ⟨h, hs⟩

theorem check_sound (h : check t es = true) : ValidTrace t es :=
  (check_iff_valid t es).mp h

theorem check_complete (h : ValidTrace t es) : check t es = true :=
  (check_iff_valid t es).mpr h

theorem allowed_preserves_terminal (h : Allowed t e) (ht : t.state.terminal) :
    (advance t e).state = t.state := by
  cases e with
  | snapshot next => exact h.2.2 ht
  | followup _ _ => rfl

/-- Any legal finite continuation of a terminal task retains the exact terminal state. -/
theorem terminal_stable (h : ValidTrace t es) (ht : t.state.terminal) :
    (finalTask t es).state = t.state := by
  induction h with
  | nil => rfl
  | @cons t e es h hs ih =>
      have he := allowed_preserves_terminal h ht
      have hn : (advance t e).state.terminal := he ▸ ht
      exact (ih hn).trans he

/-- Diagnostics and the declarative rule agree, including error-precedence handling. -/
theorem violation_none_iff (t : Task) (e : Event) :
    violation t e = none ↔ Allowed t e := by
  cases e with
  | snapshot next =>
      simp only [violation, Allowed]
      split <;> simp_all
      split <;> simp_all
  | followup context outcome =>
      simp only [violation, Allowed]
      split <;> split <;> simp_all

theorem diagnose_none_iff (t : Task) (es : List Event) :
    diagnose t es = none ↔ ValidTrace t es := by
  induction es generalizing t with
  | nil => simp [diagnose, ValidTrace.nil]
  | cons e es ih =>
      rw [← check_iff_valid]
      simp only [check, Bool.and_eq_true, decide_eq_true_eq]
      unfold diagnose
      cases hv : violation t e with
      | none =>
          have ha := (violation_none_iff t e).mp hv
          simp [ha, ih, check_iff_valid]
      | some r =>
          have ha : ¬ Allowed t e := by
            intro h
            have := (violation_none_iff t e).mpr h
            simp_all
          simp [ha]

/-- A diagnostic points at a violated rule after a prefix of allowed events. -/
inductive FirstViolation : Task → List Event → Diagnostic → Prop where
  | here : violation t e = some rule → FirstViolation t (e :: es) ⟨0, rule⟩
  | later : Allowed t e → FirstViolation (advance t e) es d →
      FirstViolation t (e :: es) { d with index := d.index + 1 }

theorem diagnose_first (h : diagnose t es = some d) : FirstViolation t es d := by
  induction es generalizing t d with
  | nil => simp [diagnose] at h
  | cons e es ih =>
      unfold diagnose at h
      cases hv : violation t e with
      | some rule =>
          simp only [hv] at h
          cases h
          exact .here hv
      | none =>
          simp only [hv] at h
          cases hd : diagnose (advance t e) es with
          | none => simp [hd] at h
          | some next =>
              simp only [hd, Option.map_some, Option.some.injEq] at h
              subst d
              exact .later ((violation_none_iff t e).mp hv) (ih hd)

/-- A witness that interrupted-task resumption is permitted, not a liveness promise. -/
theorem input_resumption_valid (id context : String) :
    ValidTrace ⟨id, context, .inputRequired⟩
      [.followup none .accepted,
       .snapshot ⟨id, context, .working⟩,
       .snapshot ⟨id, context, .completed⟩] := by
  apply check_sound
  simp [check, Allowed, State.terminal, advance]

end A2A
