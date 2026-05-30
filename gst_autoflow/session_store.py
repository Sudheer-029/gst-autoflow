"""
Persistent session storage — saves session_state to a JSON file keyed by
a session ID stored in the URL (?s=...). Survives page refreshes.
"""
from __future__ import annotations

import base64
import io
import json
import pathlib
import time
import uuid
from typing import Any

import os

import pandas as pd

_SESSION_DIR = pathlib.Path(
    os.environ.get("GST_SESSION_DIR",
                   str(pathlib.Path.home() / ".gst_autoflow" / "sessions"))
)
_SESSION_DIR.mkdir(parents=True, exist_ok=True)

MAX_AGE_HOURS = 48  # sessions older than this are deleted on startup


def new_id() -> str:
    return uuid.uuid4().hex[:20]


# ── Serialization ─────────────────────────────────────────────────────────────

def _enc(v: Any) -> Any:
    """Recursively encode Python objects → JSON-safe."""
    if isinstance(v, pd.DataFrame):
        return {"__df__": v.to_json(orient="records", date_format="iso")}
    if isinstance(v, bytes):
        return {"__b64__": base64.b64encode(v).decode()}
    if isinstance(v, dict):
        return {k: _enc(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_enc(i) for i in v]
    # int64 / float64 → plain Python types so json.dumps works
    try:
        import numpy as np  # type: ignore
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
    except ImportError:
        pass
    return v


def _dec(v: Any) -> Any:
    """Recursively decode JSON → Python objects."""
    if isinstance(v, dict):
        if "__df__" in v:
            return pd.read_json(io.StringIO(v["__df__"]), orient="records")
        if "__b64__" in v:
            return base64.b64decode(v["__b64__"])
        return {k: _dec(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_dec(i) for i in v]
    return v


# ── Public API ─────────────────────────────────────────────────────────────────

def save(session_id: str, state: dict) -> None:
    """Write state dict to <session_id>.json."""
    try:
        payload = {k: _enc(v) for k, v in state.items()}
        payload["__ts__"] = time.time()
        (_SESSION_DIR / f"{session_id}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    except Exception:
        pass  # never crash the app on a save failure


def load(session_id: str) -> dict:
    """Read and decode state dict from file. Returns {} if missing or corrupt."""
    path = _SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw.pop("__ts__", None)
        return {k: _dec(v) for k, v in raw.items()}
    except Exception:
        return {}


def cleanup() -> None:
    """Delete session files older than MAX_AGE_HOURS. Call once at startup."""
    cutoff = time.time() - MAX_AGE_HOURS * 3600
    for p in _SESSION_DIR.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass
