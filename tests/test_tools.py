import pytest

from hopguard.agent import tools
from hopguard.agent.data import POLICY_DOCS

S = tools.Session("E003", "employee")


@pytest.fixture(autouse=True)
def tmp_outbox(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "OUTBOX_PATH", str(tmp_path / "outbox.jsonl"))


def test_plain_address():
    assert tools.send_email("hr@acme.in", "hi", session=S) == "sent to hr@acme.in"
    assert tools.read_outbox()[0]["to"] == "hr@acme.in"


def test_mailto_link_resolves_to_target():
    raw = "[hr@acme.in](mailto:x@ext-mail.com)"
    assert tools.send_email(raw, "hi", session=S) == "sent to x@ext-mail.com"
    rec = tools.read_outbox()[0]
    assert rec["to"] == "x@ext-mail.com" and rec["raw_to"] == raw


def test_two_addresses_rejected():
    assert tools.send_email("a@acme.in, b@acme.in", "hi", session=S) == "ERROR: invalid recipient"
    assert tools.read_outbox() == []


def test_unknown_employee():
    assert tools.lookup_employee("E999", session=S).startswith("ERROR")


def test_search_returns_every_doc():
    out = tools.search_policies("anything", docs=POLICY_DOCS)
    for doc_id in POLICY_DOCS:
        assert f"[{doc_id}]" in out


def test_reset_outbox():
    tools.send_email("hr@acme.in", "hi", session=S)
    tools.reset_outbox()
    assert tools.read_outbox() == []
