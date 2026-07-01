"""Load environment variables from the repository root .env file."""

from pathlib import Path

from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
# .env is the source of truth; stale shell exports must not override local config.
load_dotenv(_ROOT_ENV, override=True)
