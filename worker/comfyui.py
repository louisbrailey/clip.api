"""Small, local-only ComfyUI client for approved media-generation workflows.

The client deliberately accepts a workflow JSON document supplied by the operator
or a trusted local controller. It never downloads models, follows redirects, or
contacts a remote host. ComfyUI remains optional; the existing FFmpeg renderer is
the fallback when COMFYUI_URL is unset.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ComfyUIError(RuntimeError):
    """A bounded, redacted local ComfyUI failure."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ComfyUIError("Unexpected redirect from ComfyUI")


HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def _base_url() -> str:
    value = os.environ.get("COMFYUI_URL", "").strip().rstrip("/")
    if not value:
        raise ComfyUIError("COMFYUI_URL is not configured")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ComfyUIError("Invalid ComfyUI URL") from None
    if parsed.scheme != "http" or not port or parsed.netloc not in (
        f"127.0.0.1:{port}", f"localhost:{port}"
    ) or parsed.path or parsed.query or parsed.fragment:
        raise ComfyUIError("ComfyUI must be bound to loopback for local generation")
    return f"http://127.0.0.1:{port}"


def _request(path: str, *, method: str = "GET", body: object | None = None, timeout: float = 10) -> object:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        _base_url() + path,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload else {},
    )
    try:
        with HTTP.open(request, timeout=timeout) as response:
            return json.loads(response.read(10 * 1024 * 1024))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ComfyUIError("ComfyUI is unavailable or returned invalid JSON") from exc


def health() -> dict:
    """Return a small local status payload without exposing system details."""
    value = _request("/system_stats")
    system = value.get("system") if isinstance(value, dict) else None
    if not isinstance(system, dict) or not isinstance(system.get("comfyui_version"), str):
        raise ComfyUIError("ComfyUI returned an invalid status payload")
    return {"ok": True, "version": system["comfyui_version"]}


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
        value = _request("/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=min(15, max(0.1, deadline - time.monotonic())))
        if isinstance(value, dict) and prompt_id in value:
            item = value[prompt_id]
            if isinstance(item, dict):
                status = item.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise ComfyUIError("ComfyUI workflow failed")
                if isinstance(status, dict) and status.get("completed"):
                    return item
        time.sleep(max(0, min(max(poll, 0.1), 10.0, deadline - time.monotonic())))
    raise ComfyUIError("ComfyUI workflow timed out")


def main():
    parser = argparse.ArgumentParser(description="Run a trusted ComfyUI API workflow on this Mac")
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--prompt-node")
    parser.add_argument("--prompt")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("--timeout must be between 1 and 3600 seconds")
    if (args.prompt_node is None) != (args.prompt is None):
        parser.error("--prompt and --prompt-node must be used together")
    try:
        with args.workflow.open("rb") as file:
            raw = file.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ComfyUIError("Workflow exceeds 2 MiB")
        workflow = json.loads(raw)
        if args.prompt_node is not None:
            try:
                node = workflow[args.prompt_node]
                if node["class_type"] != "CLIPTextEncode" or not isinstance(node["inputs"]["text"], str):
                    raise ValueError
                node["inputs"]["text"] = args.prompt
            except (ValueError, KeyError, TypeError):
                raise ComfyUIError("Prompt node must be a CLIPTextEncode node with literal text") from None
        prompt_id = queue(workflow)
        print(json.dumps({"prompt_id": prompt_id}), flush=True)
        result = wait(prompt_id, timeout=args.timeout)
        print(json.dumps({"outputs": result.get("outputs", {})}))
    except (ComfyUIError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc if isinstance(exc, ComfyUIError) else 'Could not read workflow JSON'}\n")


if __name__ == "__main__":
    main()
