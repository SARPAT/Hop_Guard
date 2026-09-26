"""Shared helpers for harness scripts: load cases, build docs/session, redact saved output."""
import json
import os
import re

from hopguard.agent.data import EMPLOYEES, POLICY_DOCS
from hopguard.agent.tools import Session

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
SENSITIVE = sorted({str(e["salary_inr"]) for e in EMPLOYEES.values()} |
                   {e["bank_account"] for e in EMPLOYEES.values()}, key=len, reverse=True)


def load(name: str) -> list[dict]:
    with open(os.path.join(HERE, name)) as f:
        return [json.loads(line) for line in f if line.strip()]


def all_cases() -> list[tuple[dict, bool]]:
    """(case, is_attack) for every attack seed and benign case."""
    return [(c, True) for c in load("seeds.jsonl")] + [(c, False) for c in load("benign.jsonl")]


def build_docs(case: dict) -> dict[str, str]:
    docs = dict(POLICY_DOCS)
    if case.get("poison_doc"):
        docs[case["poison_doc"]["id"]] = case["poison_doc"]["text"]
    if case.get("extra_doc"):
        docs[case["extra_doc"]["id"]] = case["extra_doc"]["text"]
    return docs


def session_for(case: dict) -> Session:
    return Session(case["user_id"], case["role"])


def redact(obj):
    """Replace every synthetic salary/bank number (comma-grouped or not) with <REDACTED>."""
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        for value in SENSITIVE:
            obj = re.sub(r"(?<!\d)(?<!\d,)" + r",?".join(value) + r"(?!,?\d)", "<REDACTED>", obj)
    return obj
