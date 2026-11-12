"""Run a real loopback portal → worker → ComfyUI → library smoke test."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid


BASE = "http://localhost:5173"
ROOT = Path(__file__).resolve().parents[1]
browser = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
)


def request(path, *, body=None, content_type=None, key=None, extra=None):
    headers = {"Origin": BASE, **(extra or {})}
    if key:
        headers["Authorization"] = "Bearer " + key
    if content_type:
        headers["Content-Type"] = content_type
    try:
        with browser.open(urllib.request.Request(BASE + path, data=body, headers=headers), timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def control(action, *, key=None, **fields):
    return request("/api/control", body=json.dumps({"action": action, **fields}).encode(),
                   content_type="application/json", key=key)


def main():
    source, output = map(Path, sys.argv[1:])
    assert not output.exists(), "Choose a new output filename"
    photo = source.read_bytes()
    assert photo.startswith(b"\x89PNG\r\n\x1a\n"), "Use an original PNG test photo"
    assert request("/signin-with-chatgpt?return_to=/")[0] == 200
    boundary = uuid.uuid4().hex
    request_id = str(uuid.uuid4())

    def queue(prompt, approved=True):
        fields = {"request_id": request_id, "title": "Local photo animation smoke test", "prompt": prompt}
        if approved:
            fields["approved"] = "on"
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                 for k, v in fields.items()]
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="source.png"\r\n'
                     'Content-Type: image/png\r\n\r\n'.encode() + photo + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return request("/api/photo-video", body=b"".join(parts),
                       content_type=f"multipart/form-data; boundary={boundary}")

    prompt = "A slow smooth camera slide to the right. Subtle reflections move across the cyan ceramic camera."
    assert queue(prompt, approved=False)[0] == 400
    status, data = queue(prompt)
    assert status == 200, (status, data)
    assert json.loads(data)["id"] == request_id
    assert queue(prompt)[0] == 200
    assert queue("A different prompt")[0] == 409
    status, data = control("worker-key", name="Photo video smoke test")
    assert status == 200, status
    key = json.loads(data)["token"]
    status, data = control("claim", key=key, request_id=str(uuid.uuid4()))
    assert status == 200 and json.loads(data)["job"] is None, "Worker without ComfyUI claimed the job"
    status, _ = request("/api/photo-video", key=key, extra={
        "X-Render-Job": request_id, "X-Render-Lease": str(uuid.uuid4()),
    })
    assert status == 409, "Unleased worker read the photo"
    print(f"Queued {request_id}. Approval, replay and worker capability checks passed.", flush=True)
    with tempfile.TemporaryDirectory(prefix="clip-api-photo-worker-") as journal:
        env = {"PATH": os.environ["PATH"], "CONSTELLATION_URL": BASE,
               "CONSTELLATION_WORKER_KEY": key, "COMFYUI_URL": "http://127.0.0.1:8188",
               "JOURNAL_DIR": journal, "WORKER_CONCURRENCY": "1"}
        subprocess.run([sys.executable, str(ROOT / "worker/runtime.py"), "--once"],
                       env=env, check=True, timeout=1020)
    status, data = request("/api/control?q=" + request_id)
    assert status == 200
    job = next(job for job in json.loads(data)["jobs"] if job["id"] == request_id)
    assert job["status"] == "succeeded" and job["tokens"] == 0, job.get("error")
    asset = job["asset"]
    assert job["receipt"] == "asset:" + asset
    status, data = request("/api/assets/" + asset)
    assert status == 200 and data[4:8] == b"ftyp"
    assert hashlib.sha256(data).hexdigest() in job["result"]
    status, prefix = request("/api/assets/" + asset, extra={"Range": "bytes=0-31"})
    assert status == 206 and prefix == data[:32]
    with output.open("xb") as file:
        file.write(data)
    print(f"Downloaded and digest-verified portal asset {asset} to {output}")


if __name__ == "__main__":
    main()
