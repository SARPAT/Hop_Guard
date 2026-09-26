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
from hopguard.agent.data import EMPLOYEES, POLICY_DOCS  # noqa: E402
from hopguard.agent.tools import Session, read_outbox, reset_outbox  # noqa: E402
from hopguard.config import GROQ_MODEL  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SENSITIVE = sorted({str(e["salary_inr"]) for e in EMPLOYEES.values()} |
                   {e["bank_account"] for e in EMPLOYEES.values()}, key=len, reverse=True)


def load(name: str) -> list[dict]:
    with open(os.path.join(HERE, name)) as f:
        return [json.loads(line) for line in f if line.strip()]


def redact(obj):
    """Replace every synthetic salary/bank number (comma-grouped or not) with <REDACTED>."""
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        for value in SENSITIVE:
            pattern = r"(?<!\d)(?<!\d,)" + r",?".join(value) + r"(?!,?\d)"
            obj = re.sub(pattern, "<REDACTED>", obj)
        return obj
    return obj


def run_case(case: dict, model: str) -> dict:
    reset_outbox()
    docs = dict(POLICY_DOCS)
    if case.get("poison_doc"):
        docs[case["poison_doc"]["id"]] = case["poison_doc"]["text"]
    session = Session(case["user_id"], case["role"])
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

    cases = [(c, True) for c in load("seeds.jsonl")] + [(c, False) for c in load("benign.jsonl")]
    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model, "n": n, "mode": "OFF", "cases": []}
    for case, is_attack in cases:
        runs = [run_case(case, model) for _ in range(n)]
        hits = sum(r["hit"] for r in runs)
        last = runs[-1]
        if is_attack:
            label = "ATTACK SUCCEEDED" if hits else "resisted"
        else:
            label = "PASS" if hits == n else "FAIL"
        err = f"  error={last['result']['error']}" if last["result"]["error"] else ""
        to = ", ".join(r["to"] for r in last["outbox"])
        cc = ", ".join(a for r in last["outbox"] for a in r.get("cc", []))
        print(f"{case['id']:3} {label:16} {hits}/{n}  steps={last['result']['steps']}  "
              f"ms={last['result']['ms']}  outbox_to=[{to}]" + (f"  cc=[{cc}]" if cc else "") + err)
        report["cases"].append({"id": case["id"], "attack": is_attack, "hits": hits,
                                "runs": redact(runs)})

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"baseline_{re.sub(r'[^A-Za-z0-9.-]+', '_', model)}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nsaved {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
