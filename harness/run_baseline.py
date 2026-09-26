"""Baseline run: every attack and benign case against the UNDEFENDED agent (guard=None)."""
import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.detect import DETECTORS  # noqa: E402
from hopguard.agent.agent import run  # noqa: E402
from harness.cases import HERE, all_cases, build_docs, redact, session_for  # noqa: E402
from hopguard.agent.tools import read_outbox, reset_outbox  # noqa: E402
from hopguard.config import GROQ_MODEL  # noqa: E402

def run_case(case: dict, model: str) -> dict:
    reset_outbox()
    docs = build_docs(case)
    session = session_for(case)
    result = run(case["query"], session, docs, guard=None, model=model)
    outbox = read_outbox()
    hit, reason = DETECTORS[case["detector"]](result, outbox, session, case)
    reset_outbox()
    return {"hit": hit, "reason": reason, "result": asdict(result), "outbox": outbox}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1, help="runs per case")
    ap.add_argument("--model", default=GROQ_MODEL, help="Groq model id (overrides GROQ_MODEL)")
    args = ap.parse_args()
    n, model = args.n, args.model
    print(f"MODEL: {model}   mode: OFF   n={n}\n")

    cases = all_cases()
    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model, "n": n, "mode": "OFF", "cases": []}
    for case, is_attack in cases:
        runs = [run_case(case, model) for _ in range(n)]
        hits = sum(r["hit"] for r in runs)
        errors = sum(1 for r in runs if r["result"]["error"])
        last = runs[-1]
        if errors == n:
            label = "ERROR"
        elif is_attack:
            label = "ATTACK SUCCEEDED" if hits else "resisted"
        else:
            label = "PASS" if hits == n else "FAIL"
        err = f"  error={last['result']['error']}" if last["result"]["error"] else ""
        to = ", ".join(r["to"] for r in last["outbox"])
        cc = ", ".join(a for r in last["outbox"] for a in r.get("cc", []))
        print(f"{case['id']:3} {label:16} {hits}/{n}  steps={last['result']['steps']}  "
              f"ms={last['result']['ms']}  outbox_to=[{to}]" + (f"  cc=[{cc}]" if cc else "") + err)
        report["cases"].append({"id": case["id"], "attack": is_attack, "hits": hits, "errors": errors,
                                "runs": redact(runs)})

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"baseline_{re.sub(r'[^A-Za-z0-9.-]+', '_', model)}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nsaved {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
