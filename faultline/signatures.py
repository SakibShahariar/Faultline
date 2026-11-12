"""Stable event signatures that ignore volatile process and address values."""
from __future__ import annotations

import hashlib
import re

_PID = re.compile(r"\b(?:pid|process)[=: ]+\d+\b", re.IGNORECASE)
_HEX_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]+\b")
_KERNEL_ADDRESS = re.compile(r"\b[0-9a-fA-F]{8,16}\b")
_WHITESPACE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    text = _PID.sub("pid=<pid>", message)
    text = _HEX_ADDRESS.sub("<addr>", text)
    text = _KERNEL_ADDRESS.sub("<addr>", text)
    return _WHITESPACE.sub(" ", text).strip().lower()


def signature_for(message: str, source: str = "") -> str:
    normalized = f"{source.lower()}:{normalize_message(message)}"
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:20]
