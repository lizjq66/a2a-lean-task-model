import Std

namespace A2A

/-- UNSPECIFIED is retained as an observation, not silently mapped to WORKING. -/
inductive State where
  | unspecified | submitted | working | inputRequired | authRequired
  | completed | failed | canceled | rejected
  deriving DecidableEq, Repr

def State.terminal : State → Prop
  | .completed | .failed | .canceled | .rejected => True
  | _ => False

instance (s : State) : Decidable s.terminal := by cases s <;> simp [State.terminal] <;> infer_instance

structure Task where
  id : String
  context : String
  state : State
  deriving DecidableEq, Repr

inductive Outcome where
  | accepted | unsupportedOperation | otherError
  deriving DecidableEq, Repr

/-- Normalized, sequential observations for ONE existing task.
`followup` is a completed SendMessage exchange targeting that task's ID.
`snapshot` is a causally later observation, not a delayed/replayed packet. -/
inductive Event where
  | snapshot (task : Task)
  | followup (context : Option String) (outcome : Outcome)
  deriving DecidableEq, Repr

/-- Declarative fragment of the specification; deliberately no full transition table. -/
def Allowed (t : Task) : Event → Prop
  | .snapshot next =>
      next.id = t.id ∧ next.context = t.context ∧
      (t.state.terminal → next.state = t.state)
  | .followup context outcome =>
      -- When both conditions apply, error precedence is unspecified.
      if context.isSome ∧ context ≠ some t.context then outcome ≠ .accepted
      else t.state.terminal → outcome = .unsupportedOperation

instance (t : Task) (e : Event) : Decidable (Allowed t e) := by
  cases e <;> unfold Allowed <;> infer_instance

def advance (t : Task) : Event → Task
  | .snapshot next => next
  | .followup _ _ => t

/-- Declarative legal finite traces. Empty/prefix traces do not assert completion. -/
inductive ValidTrace : Task → List Event → Prop where
  | nil (t) : ValidTrace t []
  | cons : Allowed t e → ValidTrace (advance t e) es → ValidTrace t (e :: es)

def finalTask (t : Task) : List Event → Task
  | [] => t
  | e :: es => finalTask (advance t e) es

end A2A
