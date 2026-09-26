"""One guarded request end to end: G1 ingest screening, then the agent with the tool-call guard.

Shared by the guard check script, the harness and the UI so every path runs the same code.
"""
import uuid
from dataclasses import dataclass, field

from hopguard.agent.agent import RunResult, run
from hopguard.agent.tools import Session
from hopguard.guard import AuditLog, make_guard, screen_docs

MODES = {
    "OFF": None,
    "FULL": {"G1": True, "G3": True, "G4": True},
    "G1_OFF": {"G1": False, "G3": True, "G4": True},
}


@dataclass
class GuardedRun:
    trace_id: str
    result: RunResult
    quarantined: list[str] = field(default_factory=list)


def new_trace_id() -> str:
    return "t-" + uuid.uuid4().hex[:10]


def guarded_run(query: str, session: Session, docs: dict[str, str], toggles: dict | None,
                audit: AuditLog, model: str | None = None, trace_id: str | None = None) -> GuardedRun:
    """toggles=None means defence OFF (no screening, no guard; request and answer still audited)."""
    trace_id = trace_id or new_trace_id()
    if toggles is None or not any(toggles.values()):
        return GuardedRun(trace_id, run(query, session, docs, None, model, audit, trace_id))
    clean = screen_docs(docs, audit, trace_id, toggles)
    guard = make_guard(session, query, audit, trace_id, toggles)
    result = run(query, session, clean, guard, model, audit, trace_id)
    return GuardedRun(trace_id, result, sorted(set(docs) - set(clean)))
