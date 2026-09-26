"""Environment loading and project constants. Never prints key values."""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

COMPANY = "Acme India"
COMPANY_DOMAIN = "acme.in"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

MAX_STEPS = 6
OUTBOX_PATH = "outbox.jsonl"


def groq_client() -> OpenAI:
    """OpenAI-compatible client for Groq, keyed from GROQ_API_KEY."""
    return OpenAI(base_url=GROQ_BASE_URL, api_key=os.getenv("GROQ_API_KEY"), timeout=60)
