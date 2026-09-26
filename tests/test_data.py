import importlib

import hopguard.agent.data as data


def test_ten_employees():
    assert list(data.EMPLOYEES) == [f"E{i:03d}" for i in range(1, 11)]


def test_deterministic():
    first = data.EMPLOYEES
    again = importlib.reload(data).EMPLOYEES
    assert first == again


def test_emails_internal_ascii_lowercase():
    for e in data.EMPLOYEES.values():
        assert e["email"].endswith("@acme.in")
        assert e["email"].isascii() and e["email"] == e["email"].lower()


def test_field_ranges():
    for e in data.EMPLOYEES.values():
        assert 600_000 <= e["salary_inr"] <= 4_000_000
        assert len(e["bank_account"]) == 12 and e["bank_account"].isdigit()
        assert 0 <= e["leave_balance"] <= 30


def test_policy_docs():
    assert set(data.POLICY_DOCS) == {"leave-policy", "travel-policy", "payroll-faq", "wfh-policy", "holidays-2026"}
    assert "hr@acme.in" in data.POLICY_DOCS["leave-policy"]
