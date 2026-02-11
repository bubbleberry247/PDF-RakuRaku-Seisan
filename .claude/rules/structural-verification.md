# Structural Verification Protocol

Rules alone don't change behavior. This file defines **structures** that prevent shortcuts.

## 1. Mandatory Report Format (Source Citation)

ALL factual claims in reports MUST use this format:

```
## Claim
(What you are asserting)

## Primary Source
(Where the data came from: URL, file path, command executed, tool output)
(If tool output: include tool name, parameters, and key output values)

## Known Facts Check
(List relevant known facts from: past CSVs, decisions.md, previous sessions)
(Mark each: ✅ consistent / ❌ contradicts)
(If ANY contradiction: STOP. Investigate the contradiction before reporting.)

## Confidence
(High / Medium / Low + one-line reason)
```

If you cannot fill "Primary Source" with a concrete source → you are guessing. STOP.
If "Known Facts Check" has any ❌ → your claim is likely wrong. Investigate first.

## 2. Negative Claim Gate (Contradiction Check)

Before asserting any of these:
- "Data does not exist"
- "Feature is not implemented"
- "System does not support X"
- "No records found"

You MUST:
1. State what you expected to find
2. Show the exact query/command that returned no results
3. Check at least ONE alternative source (existing CSV, project decisions, past session memory)
4. If the alternative source contradicts your claim → your tool/query is broken, not the data

This is Jidoka: stop when the result is abnormal.

## 3. Autonomy Levels by Task Type

| Task Type | Autonomy | Required Checkpoints |
|-----------|----------|---------------------|
| Code edit (clear instruction) | High | None extra |
| File operation / execution | High | None extra |
| Investigation / analysis | **Low** | Report format required. Each conclusion needs user confirmation before proceeding to next step. |
| Factual claims / reporting | **Low** | Report format required. Negative claims require Gate check. |
| Design / architecture | **Low** | Codex consultation + user approval before implementation. |

When autonomy is "Low": do NOT chain multiple conclusions. Present ONE finding, wait for confirmation, then proceed.

## 4. Anti-Shortcut Checklist (Before Every Report)

Before presenting any investigation results, verify:

- [ ] Did I go to the PRIMARY source? (not secondary data like old CSVs)
- [ ] Does my conclusion match KNOWN FACTS from previous sessions?
- [ ] If "no data found": did I verify the tool/query worked correctly?
- [ ] Am I taking the EASY path instead of the CORRECT path?

If you catch yourself checking a CSV instead of running the actual tool → STOP. That's the shortcut.
If you catch yourself accepting "0 results" without questioning the query → STOP. That's the shortcut.
