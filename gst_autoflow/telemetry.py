"""
Anonymous, opt-in usage telemetry.

Sends only aggregate, non-PII events to help understand which features get used.
Never sends file content, GSTINs, vendor names, or any user data.

Disabled by default. Enable by setting the env var GST_AUTOFLOW_TELEMETRY=1
and providing GST_AUTOFLOW_TELEMETRY_URL pointing at a collector endpoint
(any service that accepts a JSON POST — PostHog, a simple webhook, etc.).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_ENABLED = os.environ.get("GST_AUTOFLOW_TELEMETRY", "0") == "1"
_ENDPOINT = os.environ.get("GST_AUTOFLOW_TELEMETRY_URL", "").strip()
_TIMEOUT_SECONDS = 3


def is_enabled() -> bool:
    """Return True if telemetry is configured and active."""
    return _ENABLED and bool(_ENDPOINT)


def track(event: str, session_id: str, properties: dict[str, Any] | None = None) -> None:
    """
    Fire-and-forget event tracking. Never blocks the UI; never raises.

    Args:
        event: short event name (e.g. "module_run", "landing_cta_click")
        session_id: anonymous, per-browser-session opaque id
        properties: small dict of safe scalar values (counts, durations, types)
    """
    if not is_enabled():
        return

    payload = {
        "event": event,
        "session_id": session_id,
        "properties": _sanitize(properties or {}),
    }

    # Send in a background thread so the UI never waits for the network.
    threading.Thread(
        target=_post_safely, args=(_ENDPOINT, payload), daemon=True
    ).start()


def _sanitize(props: dict[str, Any]) -> dict[str, Any]:
    """Drop anything that isn't a primitive scalar."""
    safe: dict[str, Any] = {}
    for k, v in props.items():
        if isinstance(v, (int, float, bool, str)) and len(str(v)) <= 200:
            safe[k] = v
    return safe


def _post_safely(url: str, payload: dict[str, Any]) -> None:
    try:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(req, timeout=_TIMEOUT_SECONDS).close()
    except (URLError, TimeoutError, OSError) as exc:
        # Telemetry failure must never affect the user.
        logger.debug("telemetry post failed: %s", exc)
    except Exception as exc:  # noqa: BLE001 - intentional broad except
        logger.debug("telemetry unexpected error: %s", exc)
