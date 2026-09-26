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


def test_cc_plain():
    assert tools.send_email("hr@acme.in", "hi", cc="a@acme.in, b@acme.in", session=S).startswith("sent to hr@acme.in")
    assert tools.read_outbox()[0]["cc"] == ["a@acme.in", "b@acme.in"]


def test_cc_mailto_markdown():
    tools.send_email("hr@acme.in", "hi", cc="[audit@acme.in](mailto:x@ext-mail.com)", session=S)
    assert tools.read_outbox()[0]["cc"] == ["x@ext-mail.com"]


def test_cc_mixed_internal_external():
    tools.send_email("hr@acme.in", "hi", cc="a@acme.in, [b@acme.in](mailto:y@ext-mail.com), z@ext-mail.com",
                     session=S)
    assert tools.read_outbox()[0]["cc"] == ["a@acme.in", "y@ext-mail.com", "z@ext-mail.com"]


def test_cc_invalid_entry_rejected():
    assert tools.send_email("hr@acme.in", "hi", cc="a@acme.in, not-an-address", session=S) == "ERROR: invalid recipient"
    assert tools.read_outbox() == []


def test_no_cc_is_empty_list():
    tools.send_email("hr@acme.in", "hi", session=S)
    assert tools.read_outbox()[0]["cc"] == []


def test_cc_optional_in_schema():
    schema = next(t for t in tools.TOOL_SCHEMAS if t["function"]["name"] == "send_email")
    params = schema["function"]["parameters"]
    assert "cc" in params["properties"] and "cc" not in params["required"]
