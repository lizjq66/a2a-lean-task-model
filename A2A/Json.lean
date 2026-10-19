import A2A.Checker
import Lean.Data.Json

namespace A2A
open Lean

/-- This adapter is outside the proved core. Input is our normalized format, not wire A2A. -/
def parseState : String → Except String State
  | "unspecified" => .ok .unspecified
  | "submitted" => .ok .submitted
  | "working" => .ok .working
  | "input-required" => .ok .inputRequired
  | "auth-required" => .ok .authRequired
  | "completed" => .ok .completed
  | "failed" => .ok .failed
  | "canceled" => .ok .canceled
  | "rejected" => .ok .rejected
  | s => .error s!"Unknown state: {s}"

def stringField (j : Json) (key : String) : Except String String := do
  (← j.getObjVal? key).getStr?

def parseTask (j : Json) : Except String Task := do
  let id ← stringField j "taskId"
  let context ← stringField j "contextId"
  if id.isEmpty || context.isEmpty then throw "Task and context IDs must be nonempty in this profile"
  return ⟨id, context, ← parseState (← stringField j "state")⟩

def parseOutcome : String → Except String Outcome
  | "accepted" => .ok .accepted
  | "unsupported-operation" => .ok .unsupportedOperation
  | "other-error" => .ok .otherError
  | s => .error s!"Unknown outcome: {s}"

def parseEvent (initial : Task) (j : Json) : Except String Event := do
  match ← stringField j "kind" with
  | "snapshot" => return .snapshot (← parseTask j)
  | "followup" =>
      let id ← stringField j "taskId"
      if id != initial.id then throw "Followup targets another task; outside the single-task profile"
      let obj ← j.getObj?
      let context : Option String ← match obj.get? "contextId" with
        | none => pure none
        | some value => some <$> value.getStr?
      return .followup context (← parseOutcome (← stringField j "outcome"))
  | kind => throw s!"Unknown event kind: {kind}"

structure TraceInput where
  initial : Task
  events : List Event

def parseTrace (j : Json) : Except String TraceInput := do
  let version ← stringField j "format"
  if version != "a2a-task-trace-v1" then throw s!"Unsupported trace format: {version}"
  let initial ← parseTask (← j.getObjVal? "initial")
  let raw ← (← j.getObjVal? "events").getArr?
  let mut events := []
  for i in [:raw.size] do
    match parseEvent initial raw[i]! with
    | .ok event => events := event :: events
    | .error err => throw s!"events[{i}]: {err}"
  return ⟨initial, events.reverse⟩

end A2A
