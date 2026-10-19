import A2A
import A2A.Json

open A2A Lean

/-- Exit 0: accepted fragment; 1: violated modeled rule/profile; 2: malformed input or I/O. -/
def main (args : List String) : IO UInt32 := do
  let stdout ← IO.getStdout
  let stderr ← IO.getStderr
  let [path] := args | do
    stderr.putStrLn "Usage: a2a-check TRACE.json"
    return 2
  try
    let content ← IO.FS.readFile path
    match Json.parse content >>= parseTrace with
    | .error err =>
        stderr.putStrLn s!"INPUT ERROR: {err}"
        return 2
    | .ok trace =>
        match diagnose trace.initial trace.events with
        | none =>
            stdout.putStrLn "PASS: satisfies the modeled single-task fragment (not full A2A conformance)"
            return 0
        | some d =>
            stdout.putStrLn s!"FAIL: events[{d.index}] {d.rule.code}"
            return 1
  catch err =>
    stderr.putStrLn s!"INPUT ERROR: {err}"
    return 2
