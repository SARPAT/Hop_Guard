"""Synthetic HR data: employees and policy docs. Seeded, so every import is identical."""
import random
import re
import unicodedata

from faker import Faker

from hopguard.config import COMPANY_DOMAIN

_DEPARTMENTS = ["Engineering", "Finance", "Sales", "Marketing", "Operations", "People"]


def _ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def _build_employees() -> dict[str, dict]:
    Faker.seed(42)
    random.seed(42)
    fake = Faker("en_IN")
    employees, used = {}, set()
    for i in range(1, 11):
        while True:
            first, last = fake.first_name(), fake.last_name()
            email = f"{_ascii_slug(first)}.{_ascii_slug(last)}@{COMPANY_DOMAIN}"
            if email not in used:
                used.add(email)
                break
        eid = f"E{i:03d}"
        employees[eid] = {
            "id": eid,
            "name": f"{first} {last}",
            "email": email,
            "department": random.choice(_DEPARTMENTS),
            "salary_inr": random.randint(600_000, 4_000_000),
            "bank_account": "".join(random.choice("0123456789") for _ in range(12)),
            "address": fake.address().replace("\n", ", "),
            "leave_balance": random.randint(0, 30),
        }
    return employees


EMPLOYEES: dict[str, dict] = _build_employees()

POLICY_DOCS: dict[str, str] = {
    "leave-policy": (
        "Full-time employees receive 24 days of paid leave per calendar year, accrued monthly. "
        "Up to 10 unused days may be carried over to the next year. "
        f"Leave requests and questions go to the HR desk at hr@{COMPANY_DOMAIN}."
    ),
    "travel-policy": (
        "Business travel must be approved by your manager before booking. "
        "Economy class is standard for flights under six hours. "
        "Submit expense claims with receipts within 30 days of returning."
    ),
    "payroll-faq": (
        "Salaries are credited on the last working day of each month. "
        "Payslips are available on the internal payroll portal. "
        "Tax declarations for the financial year are due by 31 January."
    ),
    "wfh-policy": (
        "Employees may work from home up to two days per week with manager approval. "
        "Core collaboration hours are 11:00 to 16:00 IST. "
        "A one-time home office allowance of INR 15,000 is available."
    ),
    "holidays-2026": (
        "Acme India observes 12 public holidays in 2026, including Republic Day, Holi, "
        "Independence Day, Diwali and Christmas. The full list is on the intranet calendar."
    ),
}


if __name__ == "__main__":
    print(f"{'ID':5} {'NAME':28} {'DEPT':12} LEAVE")
    for e in EMPLOYEES.values():
        print(f"{e['id']:5} {e['name']:28} {e['department']:12} {e['leave_balance']:5}")
