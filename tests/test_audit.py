import json

from hopguard.guard.audit import GENESIS, AuditLog, read_rows, redact, verify_chain


def _log(tmp_path, n=3):
    path = str(tmp_path / "audit.jsonl")
    log = AuditLog(path)
    for i in range(n):
        log.append("G4", {"i": i}, "allow", trace_id="t-1")
    return path


def test_chain_ok(tmp_path):
    path = _log(tmp_path)
    assert verify_chain(path) == (True, None)
    rows = read_rows(path)
    assert rows[0]["prev"] == GENESIS and rows[1]["prev"] == rows[0]["hash"]


def test_tamper_detected(tmp_path):
    path = _log(tmp_path)
    lines = open(path).read().splitlines()
    row = json.loads(lines[1])
    row["verdict"] = "block"
    lines[1] = json.dumps(row)
    open(path, "w").write("\n".join(lines) + "\n")
    assert verify_chain(path) == (False, 1)


def test_deleted_row_detected(tmp_path):
    path = _log(tmp_path)
    lines = open(path).read().splitlines()
    open(path, "w").write("\n".join([lines[0], lines[2]]) + "\n")
    assert verify_chain(path) == (False, 1)


def test_reopen_continues_chain(tmp_path):
    path = _log(tmp_path, 2)
    AuditLog(path).append("G1", "x", "allow")
    assert verify_chain(path) == (True, None)


def test_redaction():
    s = redact("salary 1234567 or 12,34,567 bank 123456789012 key sk-test-FAKE-9f2c days 24")
    assert "1234567" not in s and "12,34,567" not in s and "123456789012" not in s and "sk-" not in s
    assert "days 24" in s


def test_row_is_redacted(tmp_path):
    path = str(tmp_path / "a.jsonl")
    AuditLog(path).append("G3", {"body": "Salary: INR 2345678, bank 987654321098"}, "block")
    raw = open(path).read()
    assert "2345678" not in raw and "987654321098" not in raw
    row = read_rows(path)[0]
    assert set(row) >= {"ts", "trace_id", "layer", "input_sha256", "snippet", "verdict", "p",
                        "threshold", "ms", "reason", "prev", "hash"}
    assert len(row["input_sha256"]) == 16 and len(row["snippet"]) <= 120


def test_redaction_leaves_words_containing_sk_alone():
    assert redact("doc hr-desk-contact and task-list") == "doc hr-desk-contact and task-list"
    assert redact("key=sk-live-abc") == "key=<REDACTED>"
