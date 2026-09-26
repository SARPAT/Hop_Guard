# CLAUDE.md — HopGuard

## What this project is
HopGuard is a hackathon demo (track P-04(a)): per-hop guardrails for an AI agent against
indirect prompt injection and data exfiltration.

- **Target system:** a thin HR assistant agent for a fictional company, "Acme India" (`acme.in`).
  It can search HR policies, look up employee records (salary, bank account, leave), and send email.
- **Defence:** a guard layer that checks each hop. Semantic checks use TypeSafe's **Jev** decision
  model; deterministic checks use plain code. Every verdict goes to a hash-chained audit log.
- **Rule of thumb:** Jev = meaning ("does this text instruct an AI?"). Code = exact rules
  (allowlists, role scope, step limits). Never ask Jev something code can answer exactly.

## Build plan (slim, 5 checkpoints)
| CP | Name | Scope |
|----|------|-------|
| 1 | Target + attacks | synthetic HR data, 3 tools, agent loop, 4 attacks, baseline runner (NO guard) |
| 2 | Guard | G1 Jev (docs), G3 Jev (tool calls), G4 code (egress + role scope), audit log |
| 3 | Demo UI | Gradio: defence ON/OFF, live trace, outbox, audit viewer |
| 4 | Mini harness | 4 attacks + 5 benign, N runs, modes OFF / FULL / G1-off → results table |
| 5 | Package | README (threat model, results, out-of-scope), slides |

Each checkpoint has a spec in `specs/CPn_*.md`. Implement ONLY what the current spec asks.

## Layout (target)
```
hopguard/
  config.py            env loading + constants
  agent/
    data.py            synthetic employees + HR policy docs (seeded, deterministic)
    tools.py           tool functions + tool schemas
    agent.py           agent loop (guard hooks, no-op when guard is None)
  guard/               CP2+ — must NOT import from hopguard.agent or ui
harness/
  seeds.jsonl          attack definitions
  benign.jsonl         benign requests
  detect.py            success/leak detectors
  results/             run outputs (JSON/CSV)
ui/                    CP3+
tests/                 offline unit tests (no network)
specs/                 checkpoint specs (read-only for you)
smoke_test/            FROZEN evidence snapshot
```

## Hard rules
1. **Never read, print, edit or commit `.env`.** Keys are loaded at runtime with `python-dotenv`.
   Never print key values; at most print SET/MISSING.
2. **Never modify anything in `smoke_test/`.** It is frozen evidence.
3. **Synthetic data only.** All employees, salaries, bank numbers and addresses come from Faker
   with a fixed seed. No real people, no real company data.
4. **No real side effects.** `send_email` writes to a local outbox file (`outbox.jsonl`). Nothing is
   ever sent over the network except calls to the Jev and Groq APIs.
5. **No response streaming and no caching** of LLM or guard outputs. Caches would hide guard
   effects and corrupt measured rates.
6. **Role comes from the session only** (`Session(user_id, role)`), never from chat text.
   A user typing "I am HR admin" must not change anything.
7. **Do not add dependencies** beyond `requirements.txt` without saying so in your final report.
8. **Do not tune attacks to make them succeed or fail.** If results differ from expectations,
   report them as they are.

## Environment
- Python venv at `.venv/`. Run things with the venv's Python.
- Env vars (in `.env`, loaded by `hopguard/config.py`):
  - `TYPESAFE_API_KEY` — Jev
  - `GROQ_API_KEY` — agent LLM
  - `GROQ_MODEL` — optional, default `openai/gpt-oss-120b`
- Agent LLM: Groq via the OpenAI client, `base_url="https://api.groq.com/openai/v1"`,
  temperature 0, `reasoning_effort="low"`.
- Jev call pattern (confirmed working):
  ```python
  from typesafe_sdk import TypeSafeClient, Noul
  r = TypeSafeClient().system_one(state=text, questions={"x": Noul(instructions=QUESTION)})
  p = r.answers["x"].noul   # probability 0..1
  ```
- Groq free tier limits are tight (about 30 requests/min, 8K tokens/min, 200K tokens/day).
  Retry HTTP 429 with backoff (honour `Retry-After` if present), max 3 retries. Keep test runs small.

## Conventions
- Python 3.10+, type hints, short docstrings. Small modules, pure functions where possible.
- Offline unit tests go in `tests/` and must not hit the network. Run with `python -m pytest -q`.
- Tests that call Jev or Groq are scripts under `harness/` or `scripts/`, not pytest tests.
- Keep output human-readable: one-line-per-case tables for harness runs.

## Workflow for each checkpoint
1. Read the spec in `specs/`.
2. Create branch `cpN` from `main`.
3. Implement, then run every acceptance check in the spec, including network checks
   (the keys work on this machine).
4. Commit on the branch with message `CPn: <summary>`. **Do not push, do not merge.**
5. Final report: files changed, acceptance results (paste outputs), anything that deviated
   from the spec and why.
