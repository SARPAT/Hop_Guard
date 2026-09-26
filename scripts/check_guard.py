"""Phase 2 check: every attack + benign case once in FULL mode; which layer stopped what; chain verify."""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.cases import RESULTS, all_cases, build_docs, session_for  # noqa: E402
from harness.detect import DETECTORS  # noqa: E402
from hopguard.agent.tools import read_outbox, reset_outbox  # noqa: E402
from hopguard.config import GROQ_MODEL  # noqa: E402
from hopguard.guard import AuditLog, verify_chain  # noqa: E402
from hopguard.guard.audit import read_rows  # noqa: E402
from hopguard.pipeline import MODES, guarded_run  # noqa: E402

AUDIT_PATH = os.path.join(RESULTS, "audit_check_guard.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=GROQ_MODEL)
    ap.add_argument("--mode", default="FULL", choices=sorted(MODES))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    if os.path.exists(AUDIT_PATH):
        os.remove(AUDIT_PATH)
    audit = AuditLog(AUDIT_PATH)
    print(f"MODEL: {args.model}   mode: {args.mode}\n")

    for case, is_attack in all_cases():
        reset_outbox()
        g = guarded_run(case["query"], session_for(case), build_docs(case), MODES[args.mode], audit, args.model)
        outbox = read_outbox()
        reset_outbox()
        hit, reason = DETECTORS[case["detector"]](g.result, outbox, session_for(case), case)
        if is_attack:
            label = "ATTACK SUCCEEDED" if hit else "safe"
        else:
            label = "PASS" if hit else "FAIL"
        stops = Counter(r["layer"] for r in read_rows(AUDIT_PATH)
                        if r["trace_id"] == g.trace_id and r["verdict"] in ("block", "quarantine"))
        stopped = ", ".join(f"{k}x{v}" for k, v in sorted(stops.items())) or "-"
        err = f"  error={g.result.error}" if g.result.error else ""
        print(f"{case['id']:3} {label:16} stopped_by=[{stopped}]  quarantined={g.quarantined}  "
              f"steps={g.result.steps}  ms={g.result.ms}  outbox_to={[r['to'] for r in outbox]}  ({reason}){err}")

    ok, bad = verify_chain(AUDIT_PATH)
    print(f"\naudit rows: {len(read_rows(AUDIT_PATH))}   verify_chain: {'OK' if ok else f'BROKEN at row {bad}'}")
    print(f"audit log: {os.path.relpath(AUDIT_PATH)}")


if __name__ == "__main__":
    main()
