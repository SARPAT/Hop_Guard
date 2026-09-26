"""Thin, timed wrapper around one Jev (TypeSafe System One) call."""
import time

from typesafe_sdk import Noul, TypeSafeClient

_client: TypeSafeClient | None = None


def _jev() -> TypeSafeClient:
    global _client
    if _client is None:
        _client = TypeSafeClient()  # reads TYPESAFE_API_KEY from the environment
    return _client


def jev_ask(state: str, question: str) -> tuple[float, int]:
    """Ask Jev one question about `state`. Returns (probability 0..1, latency ms)."""
    t = time.time()
    r = _jev().system_one(state=state, questions={"x": Noul(instructions=question)})
    return float(r.answers["x"].noul), round((time.time() - t) * 1000)
