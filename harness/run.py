"""Mini harness: every attack + benign case x modes (OFF / FULL / G1_OFF) x n runs.

Writes one JSON line per run as it goes (so a quota cut-off keeps what finished) and can resume.
Runs are interleaved (run 1 of every mode/case, then run 2, ...) so partial results stay balanced.
Finishes by scoring: see harness/score.py.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import score  # noqa: E402
from harness.cases import RESULTS, all_cases, build_docs, redact, session_for  # noqa: E402
from harness.detect import DETECTORS  # noqa: E402
from hopguard.agent.tools import read_outbox, reset_outbox  # noqa: E402
from hopguard.config import GROQ_MODEL  # noqa: E402
from hopguard.guard import AuditLog  # noqa: E402
from hopguard.guard.audit import read_rows  # noqa: E402
from hopguard.pipeline import MODES, guarded_run  # noqa: E402


def one_run(mode: str, case: dict, is_attack: bool, run_idx: int, audit: AuditLog, model: str) -> dict:
    session = session_for(case)
    reset_outbox()
    g = guarded_run(case["query"], session, build_docs(case), MODES[mode], audit, model)
    outbox = read_outbox()
    reset_outbox()
    hit, reason = DETECTORS[case["detector"]](g.result, outbox, session, case)
    rows = [r for r in read_rows(audit.path) if r["trace_id"] == g.trace_id]
    return {
        "model": model, "mode": mode, "case": case["id"], "attack": is_attack, "run": run_idx, "trace_id": g.trace_id,
        "hit": hit, "reason": reason, "error": g.result.error,
        "stopped_by": sorted({r["layer"] for r in rows if r["verdict"] in ("block", "quarantine")}),
        "quarantined": g.quarantined,
        "jev_ms": [r["ms"] for r in rows if r["layer"] in ("G1", "G3") and r["ms"] is not None],
        "steps": g.result.steps, "ms": g.result.ms, "tokens": g.result.tokens,
        "answer": redact(g.result.answer), "trace": redact(g.result.trace), "outbox": redact(outbox),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3, help="runs per case per mode")
    ap.add_argument("--model", default=GROQ_MODEL)
    ap.add_argument("--modes", default="OFF,FULL,G1_OFF")
    ap.add_argument("--resume", help="existing run_*.jsonl to continue")
    args = ap.parse_args()
    modes = args.modes.split(",")
    assert all(m in MODES for m in modes), f"modes must be in {list(MODES)}"

    os.makedirs(RESULTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = args.resume or os.path.join(RESULTS, f"run_{re.sub(r'[^A-Za-z0-9.-]+', '_', args.model)}_{stamp}.jsonl")
    audit_path = path.replace("/run_", "/audit_run_")
    done = {(r["mode"], r["case"], r["run"]) for r in score.load(path)} if os.path.exists(path) else set()
    audit = AuditLog(audit_path)

    cases = all_cases()
    total = args.n * len(modes) * len(cases)
    print(f"MODEL: {args.model}   modes: {modes}   n={args.n}   runs: {total} ({len(done)} already done)")
    print(f"results: {os.path.relpath(path)}\naudit:   {os.path.relpath(audit_path)}\n")
    for run_idx in range(1, args.n + 1):
        for mode in modes:
            for case, is_attack in cases:
                if (mode, case["id"], run_idx) in done:
                    continue
                rec = one_run(mode, case, is_attack, run_idx, audit, args.model)
                with open(path, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                status = ("ERROR" if rec["error"] else
                          ("SUCCEEDED" if rec["hit"] else "safe") if is_attack else ("PASS" if rec["hit"] else "FAIL"))
                print(f"run {run_idx}  {mode:6} {case['id']:3} {status:9} stopped_by={rec['stopped_by'] or '-'}  "
                      f"steps={rec['steps']} ms={rec['ms']} tok={rec['tokens']}"
                      + (f"  error={rec['error'][:80]}" if rec["error"] else ""), flush=True)

    print()
    score.report(path, model=args.model)


if __name__ == "__main__":
    main()
