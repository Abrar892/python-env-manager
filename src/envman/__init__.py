"""envman — a small, careful manager for .env files."""

from .manager import EnvFile
from .parser import Entry, parse_env_text

__all__ = ["EnvFile", "Entry", "parse_env_text"]
__version__ = "1.0.0"
