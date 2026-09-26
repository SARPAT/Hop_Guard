"""HopGuard demo UI (Gradio). Run: python ui/app.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr  # noqa: E402

from harness.cases import all_cases  # noqa: E402
from hopguard.agent.data import EMPLOYEES, POLICY_DOCS  # noqa: E402
from hopguard.agent.tools import Session, read_outbox, reset_outbox  # noqa: E402
from hopguard.config import GROQ_MODEL  # noqa: E402
from hopguard.guard import AuditLog, verify_chain  # noqa: E402
from hopguard.guard.audit import read_rows, redact  # noqa: E402
from hopguard.pipeline import guarded_run  # noqa: E402

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
AUDIT_PATH = os.path.join(LOG_DIR, "audit_ui.jsonl")
os.makedirs(LOG_DIR, exist_ok=True)
AUDIT = AuditLog(AUDIT_PATH)

CLEAN = "(none) clean corpus, type your own question"
PRESETS = {CLEAN: None} | {f"{c['id']} · {c.get('description', c['query'])[:60]}": c for c, _ in all_cases()}
USERS = [f"{e['id']} · {e['name']}" for e in EMPLOYEES.values()]
TRACE_HEADERS = ["step", "hop", "verdict", "layer", "p", "ms"]
AUDIT_HEADERS = ["trace_id", "layer", "verdict", "p", "ms", "reason", "snippet"]


def _uid(label: str) -> str:
    return label.split(" · ")[0]


def load_preset(name: str):
    """Preset → query, user, role, and the extra (possibly poisoned) doc added to the corpus."""
    case = PRESETS[name]
    if case is None:
        return gr.update(value=""), gr.update(), gr.update(), None, corpus_note(None)
    user = next(u for u in USERS if _uid(u) == case["user_id"])
    extra = case.get("poison_doc") or case.get("extra_doc")
    return case["query"], user, case["role"], extra, corpus_note(extra)


def corpus_note(extra: dict | None) -> str:
    base = f"**Corpus:** {len(POLICY_DOCS)} HR policy docs"
    return base + (f" + untrusted doc `{extra['id']}`" if extra else " (no untrusted docs)")


def flip_all(on: bool):
    return on, on, on


def trace_rows(g, toggles) -> list[list]:
    rows = []
    for r in read_rows(AUDIT_PATH):
        if r["trace_id"] == g.trace_id and r["layer"] == "G1":
            rows.append([0, f"ingest: {r['reason'].removeprefix('doc ')}", r["verdict"], "G1", r["p"], r["ms"]])
    for t in g.result.trace:
        shown = {k: v for k, v in t["args"].items() if k != "body"}
        hop = f"{t['tool']}({redact(', '.join(f'{k}={v}' for k, v in shown.items()))[:70]})"
        if not t["layers"]:
            rows.append([t["step"], hop, t["verdict"], "-" if toggles is None else "?", None, None])
        for v in t["layers"]:
            rows.append([t["step"], hop, v["decision"], v["layer"], v["p"], v["ms"]])
    return rows


def outbox_md() -> str:
    box = read_outbox()
    if not box:
        return "_Outbox empty: nothing was sent by this request._"
    lines = []
    for r in box:
        ext = [a for a in [r["to"], *r.get("cc", [])] if not a.lower().endswith("@acme.in")]
        flag = "🔴 **EXTERNAL**" if ext else "✅ internal"
        cc = f"  cc: `{', '.join(r['cc'])}`" if r.get("cc") else ""
        lines.append(f"{flag} → to: `{r['to']}`{cc}\n\n> " + redact(r["body"]).replace("\n", "\n> "))
    return "\n\n---\n\n".join(lines)


def audit_view():
    ok, bad = verify_chain(AUDIT_PATH)
    rows = read_rows(AUDIT_PATH)
    badge = (f"### ✓ Audit chain intact ({len(rows)} rows)" if ok
             else f"### ✗ Audit chain BROKEN at row {bad}")
    table = [[r["trace_id"], r["layer"], r["verdict"], r["p"], r["ms"], r["reason"], r["snippet"][:80]]
             for r in rows[-60:]][::-1]
    return badge, table


def ask(message, history, user, role, g1, g3, g4, extra):
    history = list(history or [])
    if not (message or "").strip():
        return history, "", [], outbox_md(), *audit_view()
    toggles = {"G1": g1, "G3": g3, "G4": g4}
    toggles = toggles if any(toggles.values()) else None
    docs = dict(POLICY_DOCS)
    if extra:
        docs[extra["id"]] = extra["text"]
    reset_outbox()
    g = guarded_run(message, Session(_uid(user), role), docs, toggles, AUDIT)
    mode = "OFF" if toggles is None else "+".join(k for k, v in toggles.items() if v)
    answer = g.result.answer or f"(error: {g.result.error})"
    note = f"\n\n_trace `{g.trace_id}` · defence {mode} · {g.result.ms} ms_"
    if g.quarantined:
        note += f"\n\n_G1 quarantined: {', '.join(g.quarantined)}_"
    history += [{"role": "user", "content": message}, {"role": "assistant", "content": redact(answer) + note}]
    return history, "", trace_rows(g, toggles), outbox_md(), *audit_view()


def build() -> gr.Blocks:
    with gr.Blocks(title="HopGuard demo") as demo:
        gr.Markdown(f"# HopGuard: per-hop guardrails for an HR agent\n"
                    f"Agent model `{GROQ_MODEL}` · all data synthetic · email goes to a local outbox only")
        extra = gr.State(None)
        with gr.Row():
            with gr.Column(scale=5):
                with gr.Row():
                    user = gr.Dropdown(USERS, value=USERS[2], label="User (session)")
                    role = gr.Dropdown(["employee", "hr_admin"], value="employee", label="Role (session)")
                with gr.Row():
                    defence = gr.Checkbox(True, label="Defence ON")
                    g1 = gr.Checkbox(True, label="G1 ingest (Jev)")
                    g3 = gr.Checkbox(True, label="G3 tool call (Jev)")
                    g4 = gr.Checkbox(True, label="G4 egress + scope (code)")
                preset = gr.Dropdown(list(PRESETS), value=CLEAN, label="Preset attack / benign case")
                corpus = gr.Markdown(corpus_note(None))
                chat = gr.Chatbot(label="Chat", height=420)
                msg = gr.Textbox(label="Message", placeholder="Ask the HR assistant…", lines=2)
                send = gr.Button("Send", variant="primary")
            with gr.Column(scale=6):
                gr.Markdown("### Live trace")
                trace = gr.Dataframe(headers=TRACE_HEADERS, value=[], wrap=True, interactive=False)
                gr.Markdown("### Outbox (redacted)")
                outbox = gr.Markdown(outbox_md())
                badge0, rows0 = audit_view()
                badge = gr.Markdown(badge0)
                audit = gr.Dataframe(headers=AUDIT_HEADERS, value=rows0, wrap=True, interactive=False,
                                     label="Audit log (newest first)")
                refresh = gr.Button("Verify chain / refresh")

        defence.change(flip_all, defence, [g1, g3, g4])
        preset.change(load_preset, preset, [msg, user, role, extra, corpus])
        inputs = [msg, chat, user, role, g1, g3, g4, extra]
        outputs = [chat, msg, trace, outbox, badge, audit]
        send.click(ask, inputs, outputs)
        msg.submit(ask, inputs, outputs)
        refresh.click(audit_view, None, [badge, audit])
    return demo


if __name__ == "__main__":
    build().launch(server_name="127.0.0.1")
