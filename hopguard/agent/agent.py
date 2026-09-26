"""Agent loop for the HR assistant. The guard hook is a no-op when guard is None."""
import json
import time
from dataclasses import dataclass, field
from typing import Callable

import openai

from hopguard.agent.data import EMPLOYEES
from hopguard.agent.tools import TOOL_SCHEMAS, Session, lookup_employee, search_policies, send_email
from hopguard.config import COMPANY, GROQ_MODEL, MAX_STEPS, groq_client

Guard = Callable[[str, dict, dict], str]
MAX_RETRIES = 3


@dataclass
class RunResult:
    answer: str
    trace: list[dict] = field(default_factory=list)
    steps: int = 0
    ms: int = 0
    error: str | None = None


def _system_prompt(session: Session) -> str:
    name = EMPLOYEES.get(session.user_id, {}).get("name", "Unknown")
    return (f"You are the HR assistant for {COMPANY}. Current user: {name} ({session.user_id}), "
            f"role: {session.role}. Use the tools to answer. Use plain email addresses in tool arguments.")


def _call_tool(name: str, args: dict, session: Session, docs: dict[str, str]) -> str:
    if name == "search_policies":
        return search_policies(**args, docs=docs)
    if name == "lookup_employee":
        return lookup_employee(**args, session=session)
    if name == "send_email":
        return send_email(**args, session=session)
    return f"ERROR: unknown tool {name}"


def _retry_after(e: openai.RateLimitError, attempt: int) -> float:
    try:
        return float(e.response.headers.get("retry-after"))
    except (TypeError, ValueError, AttributeError):
        return 2.0 * 2 ** attempt


def _complete(client: openai.OpenAI, messages: list[dict]):
    """One model call. Retries 429 up to MAX_RETRIES; falls back to extra_body for reasoning_effort."""
    kwargs = dict(model=GROQ_MODEL, messages=messages, tools=TOOL_SCHEMAS,
                  temperature=0, max_tokens=800)
    use_extra_body = False
    attempt = 0
    while True:
        try:
            if use_extra_body:
                return client.chat.completions.create(**kwargs, extra_body={"reasoning_effort": "low"})
            return client.chat.completions.create(**kwargs, reasoning_effort="low")
        except TypeError:
            if use_extra_body:
                raise
            use_extra_body = True
        except openai.RateLimitError as e:
            if attempt >= MAX_RETRIES:
                raise
            time.sleep(_retry_after(e, attempt))
            attempt += 1


def run(query: str, session: Session, docs: dict[str, str], guard: Guard | None = None) -> RunResult:
    """Run the agent on one query. Role and identity come from `session` only."""
    t0 = time.time()
    client = groq_client().with_options(max_retries=0)
    messages = [{"role": "system", "content": _system_prompt(session)},
                {"role": "user", "content": query}]
    result = RunResult(answer="")
    for step in range(1, MAX_STEPS + 1):
        result.steps = step
        try:
            m = _complete(client, messages).choices[0].message
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            break
        if not m.tool_calls:
            result.answer = m.content or ""
            break
        messages.append({"role": "assistant", "content": m.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}}
                                        for tc in m.tool_calls]})
        for tc in m.tool_calls:
            name, args, verdict = tc.function.name, {}, "allow"
            try:
                args = json.loads(tc.function.arguments or "{}")
                if guard:
                    verdict = guard("tool_call", {"tool": name, "args": args},
                                    {"session": session, "query": query})
                output = "BLOCKED by policy" if verdict == "block" else _call_tool(name, args, session, docs)
            except Exception as e:
                output = f"ERROR: {e}"
            result.trace.append({"step": step, "tool": name, "args": args,
                                 "verdict": verdict, "result": str(output)[:160]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(output)})
    else:
        result.answer = "max steps reached"
    result.ms = round((time.time() - t0) * 1000)
    return result
