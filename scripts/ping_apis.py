"""Ping Jev (TypeSafe), Groq, and NVIDIA NIM (fallback). Never prints key values."""
import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

KEYS = ["TYPESAFE_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY"]
SECRETS = [v for v in (os.environ.get(k) for k in KEYS) if v]
GROQ_MODEL = os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"
PROMPT = [{"role": "user", "content": "Reply with only: 0.5"}]


def scrub(msg):
    for s in SECRETS:
        msg = msg.replace(s, "***")
    return msg


def _groq():
    from openai import OpenAI
    return OpenAI(base_url="https://api.groq.com/openai/v1",
                  api_key=os.environ.get("GROQ_API_KEY"), timeout=30)


def ping_jev():
    from typesafe_sdk import TypeSafeClient, Noul
    t = time.time()
    r = TypeSafeClient().system_one(state="test", questions={"q": Noul(instructions="Is this text empty?")})
    return f"noul={r.answers['q'].noul}", (time.time() - t) * 1000


def ping_groq():
    t = time.time()
    r = _groq().chat.completions.create(model=GROQ_MODEL, max_tokens=50, messages=PROMPT)
    ms = (time.time() - t) * 1000
    return f"model={GROQ_MODEL} reply={r.choices[0].message.content!r} tokens={r.usage.completion_tokens}", ms


def ping_groq_tools():
    tools = [{"type": "function", "function": {
        "name": "send_email", "description": "Send an email",
        "parameters": {"type": "object",
                       "properties": {"to": {"type": "string"}, "body": {"type": "string"}},
                       "required": ["to", "body"]}}}]
    t = time.time()
    r = _groq().chat.completions.create(
        model=GROQ_MODEL, tools=tools, max_tokens=200,
        messages=[{"role": "user", "content": "Email bob@acme.in saying the run finished."}])
    ms = (time.time() - t) * 1000
    calls = r.choices[0].message.tool_calls
    if not calls:
        return "NO TOOL CALL", ms
    return "; ".join(f"{c.function.name}({json.dumps(json.loads(c.function.arguments or '{}'))})"
                     for c in calls), ms


def ping_nim():
    from openai import OpenAI
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1",
                    api_key=os.environ.get("NVIDIA_API_KEY"), timeout=30)
    t = time.time()
    r = client.chat.completions.create(model="google/gemma-4-31b-it", max_tokens=5, messages=PROMPT)
    return f"reply={r.choices[0].message.content!r}", (time.time() - t) * 1000


# (label, fn, required): the NIM fallback failing does not fail the run
PINGS = [("Jev", ping_jev, True),
         ("Groq", ping_groq, True),
         ("Groq tool call", ping_groq_tools, True),
         ("NIM (fallback)", ping_nim, False)]


def main():
    for k in KEYS:
        print(f"{k}: {'SET' if os.environ.get(k) else 'MISSING'}")
    ok = True
    for name, fn, required in PINGS:
        try:
            out, ms = fn()
            print(f"{name}: OK {scrub(out)} {ms:.0f}ms")
        except Exception as e:
            ok = ok and not required
            print(f"{name}: FAIL {type(e).__name__}: {scrub(str(e))}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
