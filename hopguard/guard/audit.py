"""Hash-chained, redacted JSONL audit log. Editing any row breaks the chain."""
import hashlib
import json
import os
import re
import time

from hopguard.guard.config import THRESHOLD

GENESIS = "0" * 64

# Any number with 6+ digits (comma grouping allowed) covers salaries (6-7 digits) and 12-digit bank numbers.
_BIG_NUMBER = re.compile(r"(?<![\d,])\d(?:,?\d){5,}(?![\d,]*\d)")
_SECRET = re.compile(r"\bsk-[\w-]+")


def redact(text: str) -> str:
    """Replace salary-like and bank-like numbers and sk-... tokens with <REDACTED>."""
    return _BIG_NUMBER.sub("<REDACTED>", _SECRET.sub("<REDACTED>", text))


def _row_hash(row: dict) -> str:
    body = {k: v for k, v in row.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


class AuditLog:
    """Append-only JSONL audit log. Continues the chain of an existing file."""

    def __init__(self, path: str):
        self.path = path
        self._prev = GENESIS
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if line.strip():
                        self._prev = json.loads(line)["hash"]

    def append(self, layer: str, payload, verdict: str, p: float | None = None, ms: int | None = None,
               reason: str = "", *, trace_id: str = "") -> dict:
        raw = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
        clean = redact(raw)
        row = {"ts": round(time.time(), 3), "trace_id": trace_id, "layer": layer,
               "input_sha256": hashlib.sha256(clean.encode()).hexdigest()[:16],
               "snippet": clean[:120], "verdict": verdict,
               "p": None if p is None else round(p, 4), "threshold": THRESHOLD,
               "ms": ms, "reason": redact(reason), "prev": self._prev}
        row["hash"] = _row_hash(row)
        self._prev = row["hash"]
        with open(self.path, "a") as f:
            f.write(json.dumps(row) + "\n")
        return row


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_chain(path: str) -> tuple[bool, int | None]:
    """(True, None) if every row links to the previous and its hash matches; else (False, first bad index)."""
    prev = GENESIS
    for i, row in enumerate(read_rows(path)):
        if row.get("prev") != prev or row.get("hash") != _row_hash(row):
            return False, i
        prev = row["hash"]
    return True, None
