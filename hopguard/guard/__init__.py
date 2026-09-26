"""HopGuard: the one interface the agent, UI and harness use.

Must not import from hopguard.agent or ui. Sessions are duck-typed (`.user_id`, `.role`).
"""
import json
import re
from dataclasses import asdict, dataclass

from hopguard.guard.audit import AuditLog, verify_chain  # noqa: F401 (re-exported)
from hopguard.guard.config import ALLOW_DOMAINS, LAYER_TOGGLES, Q_DOC, Q_TASK, ROLE_SCOPE, THRESHOLD
from hopguard.guard.jev import jev_ask

_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_URL = re.compile(r"https?://([\w.-]+)", re.IGNORECASE)


@dataclass
class Verdict:
    decision: str  # allow | block | quarantine
    layer: str
    p: float | None = None
    reason: str = ""
    ms: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _toggles(toggles: dict | None) -> dict:
    return {**LAYER_TOGGLES, **(toggles or {})}


def _allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in ALLOW_DOMAINS)


# ---------------------------------------------------------------- G1: ingest
def screen_docs(docs: dict[str, str], audit: AuditLog, trace_id: str,
                toggles: dict | None = None) -> dict[str, str]:
    """G1: drop (quarantine) any doc Jev says instructs an AI. Returns the clean docs."""
    if not _toggles(toggles)["G1"]:
        return dict(docs)
    clean = {}
    for doc_id, text in docs.items():
        p, ms = jev_ask(text, Q_DOC)
        decision = "quarantine" if p >= THRESHOLD else "allow"
        audit.append("G1", {"doc": doc_id, "text": text}, decision, p, ms,
                     f"doc {doc_id}", trace_id=trace_id)
        if decision == "allow":
            clean[doc_id] = text
    return clean


# ---------------------------------------------------------------- G4: code
def egress_hosts(tool: str, args: dict) -> set[str]:
    """Every email domain (send_email to/cc/body) and URL host (any string arg) in a tool call."""
    hosts = set()
    for key, value in args.items():
        if not isinstance(value, str):
            continue
        hosts |= {h.lower() for h in _URL.findall(value)}
        if tool == "send_email" and key in ("to", "cc", "body"):
            hosts |= {h.lower() for h in _EMAIL.findall(value)}
    return hosts


def check_g4(session, tool: str, args: dict) -> Verdict:
    """Deterministic checks: egress allowlist, then role scope."""
    bad = sorted(h for h in egress_hosts(tool, args) if not _allowed(h))
    if bad:
        return Verdict("block", "G4", reason=f"egress to non-allowlisted {bad}")
    scope = ROLE_SCOPE.get(session.role, {}).get(tool)
    if scope == "self":
        target = str(args.get("employee_id", "")).strip().upper()
        if target != session.user_id.upper():
            return Verdict("block", "G4", reason=f"scope: {session.role} {session.user_id} may not read {target}")
    return Verdict("allow", "G4", reason="egress+scope ok")


# ---------------------------------------------------------------- G3: Jev
def check_g3(query: str, tool: str, args: dict) -> Verdict:
    p, ms = jev_ask(f"User request: {query}\nProposed action: {tool}({json.dumps(args)})", Q_TASK)
    decision = "block" if p >= THRESHOLD else "allow"
    return Verdict(decision, "G3", p, "beyond what the user asked" if decision == "block" else "on task", ms)


class Guard:
    """Callable tool-call guard. `last` holds the Verdicts of the most recent call."""

    def __init__(self, session, query: str, audit: AuditLog, trace_id: str, toggles: dict | None = None):
        self.session, self.query, self.audit, self.trace_id = session, query, audit, trace_id
        self.toggles = _toggles(toggles)
        self.last: list[Verdict] = []

    def __call__(self, hop: str, payload: dict, ctx: dict | None = None) -> str:
        self.last = []
        tool, args = payload["tool"], payload.get("args", {})
        verdicts = []
        if self.toggles["G4"]:
            verdicts.append(check_g4(self.session, tool, args))
        if self.toggles["G3"]:  # always evaluated, even if G4 already blocked, for the audit trail
            verdicts.append(check_g3(self.query, tool, args))
        for v in verdicts:
            self.audit.append(v.layer, payload, v.decision, v.p, v.ms, v.reason, trace_id=self.trace_id)
        self.last = verdicts
        return "block" if any(v.decision == "block" for v in verdicts) else "allow"


def make_guard(session, query: str, audit: AuditLog, trace_id: str, toggles: dict | None = None) -> Guard:
    """Build the per-request tool-call guard (G4 code first, then G3 Jev)."""
    return Guard(session, query, audit, trace_id, toggles)
