import A2A.Model

namespace A2A

def check (t : Task) : List Event → Bool
  | [] => true
  | e :: es => decide (Allowed t e) && check (advance t e) es

inductive Rule where
  | taskIdentity | contextIdentity | terminalState | contextMismatch | terminalMessage
  deriving DecidableEq, Repr

def Rule.code : Rule → String
  | .taskIdentity => "PROFILE-TASK-IDENTITY"
  | .contextIdentity => "CONTEXT-IDENTITY"
  | .terminalState => "TERMINAL-STABILITY"
  | .contextMismatch => "CONTEXT-MISMATCH"
  | .terminalMessage => "TERMINAL-MESSAGE"

def violation (t : Task) : Event → Option Rule
  | .snapshot next =>
      if next.id ≠ t.id then some .taskIdentity
      else if next.context ≠ t.context then some .contextIdentity
      else if t.state.terminal ∧ next.state ≠ t.state then some .terminalState
      else none
  | .followup context outcome =>
      if context.isSome ∧ context ≠ some t.context then
        if outcome = .accepted then some .contextMismatch else none
      else if t.state.terminal ∧ outcome ≠ .unsupportedOperation then some .terminalMessage
      else none

structure Diagnostic where
  /-- Zero-based index in the normalized event array. -/
  index : Nat
  rule : Rule
  deriving DecidableEq, Repr

def diagnose (t : Task) : List Event → Option Diagnostic
  | [] => none
  | e :: es =>
      match violation t e with
      | some rule => some ⟨0, rule⟩
      | none => (diagnose (advance t e) es).map fun d => { d with index := d.index + 1 }

end A2A
