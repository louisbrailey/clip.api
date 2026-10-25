"""Small, local-only ComfyUI client for approved media-generation workflows.

The client deliberately accepts a workflow JSON document supplied by the operator
or a trusted local controller. It never downloads models, follows redirects, or
contacts a remote host. ComfyUI remains optional; the existing FFmpeg renderer is
the fallback when COMFYUI_URL is unset.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid


class ComfyUIError(RuntimeError):
    """A bounded, redacted local ComfyUI failure."""


def _base_url() -> str:
    value = os.environ.get("COMFYUI_URL", "").strip().rstrip("/")
    if not value:
        raise ComfyUIError("COMFYUI_URL is not configured")
    if not value.startswith("http://127.0.0.1:") and not value.startswith("http://localhost:"):
        raise ComfyUIError("ComfyUI must be bound to loopback for local generation")
    return value


def _request(path: str, *, method: str = "GET", body: object | None = None, timeout: float = 10) -> object:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        _base_url() + path,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read(10 * 1024 * 1024))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ComfyUIError("ComfyUI is unavailable or returned invalid JSON") from exc


def health() -> dict:
    """Return a small local status payload without exposing system details."""
    value = _request("/system_stats")
    if not isinstance(value, dict):
        raise ComfyUIError("ComfyUI returned an invalid status payload")
    return {"ok": True, "version": value.get("system", {}).get("comfyui_version")}


def queue(workflow: dict, *, client_id: str | None = None) -> str:
    """Queue a trusted API-format workflow and return its opaque prompt id."""
    if not isinstance(workflow, dict) or not workflow:
        raise ComfyUIError("A non-empty ComfyUI workflow is required")
    value = _request(
        "/prompt",
        method="POST",
        body={"prompt": workflow, "client_id": client_id or str(uuid.uuid4())},
    )
    prompt_id = value.get("prompt_id") if isinstance(value, dict) else None
    if not isinstance(prompt_id, str) or not prompt_id:
        raise ComfyUIError("ComfyUI did not return a prompt id")
    return prompt_id


def wait(prompt_id: str, *, timeout: float = 900, poll: float = 1.0) -> dict:
    """Wait for one queued prompt, bounded by a caller-supplied timeout."""
    if not prompt_id or len(prompt_id) > 200:
        raise ComfyUIError("Invalid ComfyUI prompt id")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = _request("/history/" + prompt_id, timeout=15)
        if isinstance(value, dict) and prompt_id in value:
            item = value[prompt_id]
            if isinstance(item, dict):
                status = item.get("status", {})
                if isinstance(status, dict) and status.get("completed"):
                    return item
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise ComfyUIError("ComfyUI workflow failed")
        time.sleep(min(max(poll, 0.1), 10.0))
    raise ComfyUIError("ComfyUI workflow timed out")
