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
import re
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ComfyUIError(RuntimeError):
    """A bounded, redacted local ComfyUI failure."""


class WorkflowFailed(ComfyUIError):
    """ComfyUI confirmed that the submitted prompt failed."""


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


def _read(path, *, method="GET", payload=None, headers=None, timeout=10, limit=10 * 1024 * 1024):
    request = urllib.request.Request(
        _base_url() + path,
        data=payload,
        method=method,
        headers=headers or {},
    )
    try:
        with HTTP.open(request, timeout=timeout) as response:
            data = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ComfyUIError("ComfyUI request failed. Check its console and installed models.") from None
    if len(data) > limit:
        raise ComfyUIError("ComfyUI response exceeded its size limit")
    return data


def _decode(data):
    try:
        return json.loads(data)
    except ValueError:
        raise ComfyUIError("ComfyUI returned invalid JSON") from None


def _request(path: str, *, method: str = "GET", body: object | None = None, timeout: float = 10) -> object:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else None
    return _decode(_read(path, method=method, payload=payload, headers=headers, timeout=timeout))


def upload_photo(data, mime, job_id):
    boundary = uuid.uuid4().hex
    ext = "png" if mime == "image/png" else "jpg"
    filename = f"clip-api-{job_id}.{ext}"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    result = _decode(_read("/upload/image", method="POST", payload=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }, timeout=30))
    if not isinstance(result, dict) or result.get("name") != filename or result.get("subfolder") != "" or result.get("type") != "input":
        raise ComfyUIError("ComfyUI did not accept the expected source photo")
    return filename


def photo_workflow(filename, prompt, seed, job_id):
    # Based on ComfyUI's native Wan 2.2 TI2V template, with a fixed preview size.
    def node(kind, **inputs):
        return {"class_type": kind, "inputs": inputs}

    return {
        "1": node("UNETLoader", unet_name="wan2.2_ti2v_5B_fp16.safetensors", weight_dtype="default"),
        "2": node("CLIPLoader", clip_name="umt5_xxl_fp16.safetensors", type="wan", device="default"),
        "3": node("VAELoader", vae_name="wan2.2_vae.safetensors"),
        "4": node("LoadImage", image=filename),
        "5": node("CLIPTextEncode", clip=["2", 0], text=prompt),
        "6": node("CLIPTextEncode", clip=["2", 0], text="blurry, distorted, flickering, static"),
        "7": node("Wan22ImageToVideoLatent", vae=["3", 0], start_image=["4", 0],
                  width=384, height=224, length=33, batch_size=1),
        "8": node("ModelSamplingSD3", model=["1", 0], shift=8),
        "9": node("KSampler", model=["8", 0], positive=["5", 0], negative=["6", 0],
                  latent_image=["7", 0], seed=seed, steps=20, cfg=5, sampler_name="uni_pc",
                  scheduler="simple", denoise=1),
        "10": node("VAEDecode", samples=["9", 0], vae=["3", 0]),
        "11": node("CreateVideo", images=["10", 0], fps=16.0),
        "12": node("SaveVideo", video=["11", 0], filename_prefix=f"ClipAPI/{job_id}",
                   format="mp4", codec={"codec": "h264"}),
    }


def video_output(result, job_id):
    try:
        files = result["outputs"]["12"]["images"]
        item, = files
        name = item["filename"]
        if item["type"] != "output" or item["subfolder"] != "ClipAPI" or not re.fullmatch(
            re.escape(job_id) + r"_\d+_\.mp4", name
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ComfyUIError("ComfyUI did not return the expected MP4") from None
    query = urllib.parse.urlencode({"filename": name, "subfolder": "ClipAPI", "type": "output"})
    return _read("/view?" + query, timeout=30, limit=16 * 1024 * 1024)


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


def wait(prompt_id: str, *, timeout: float = 900, poll: float = 1.0, lease_valid=lambda: True) -> dict:
    """Wait for one queued prompt, bounded by a caller-supplied timeout."""
    if not prompt_id or len(prompt_id) > 200:
        raise ComfyUIError("Invalid ComfyUI prompt id")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not lease_valid():
            raise ComfyUIError("Render lease lost while ComfyUI was running")
        value = _request("/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=min(15, max(0.1, deadline - time.monotonic())))
        if isinstance(value, dict) and prompt_id in value:
            item = value[prompt_id]
            if isinstance(item, dict):
                status = item.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise WorkflowFailed("ComfyUI workflow failed")
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
