# Local media generation

Clip.api can use the ComfyUI instance already installed on this Mac for approved image-to-video or text-to-video workflows. The integration is loopback-only and token-free: cloud coordinators may produce instructions, but the local worker performs generation and returns a reviewable artifact.

## Current machine

The configured instance is:

```text
http://127.0.0.1:8188/
```

It is currently running from `/Users/louisbrailey/local-media/ComfyUI` on an Apple M3 Max with 64 GB unified memory. The launcher is in the Desktop folder `local ai models`. Clip.api does not copy or re-download the model weights.

Set this only in the worker environment:

```sh
COMFYUI_URL=http://127.0.0.1:8188
```

The bounded client is [worker/comfyui.py](../worker/comfyui.py). It checks health, queues a trusted API-format workflow, and waits for one prompt with a timeout. It rejects non-loopback hosts and does not accept arbitrary URLs, shell commands or model-generated workflow changes.

## Model choice

For this Mac, start with Wan 2.2 TI2V 5B in ComfyUI. It supports text and image conditioning and is the practical local baseline for 64 GB unified memory. Wan 2.2 14B is the higher-quality option but is documented around much larger GPU memory for direct inference. LTX-Video 2B distilled is the fast fallback for previews; LTX-Video 13B is a quality option when memory and render time allow. Check each model card and license before commercial use.

- [Wan 2.2 ComfyUI workflows](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 model card](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B)
- [LTX-Video model card](https://huggingface.co/Lightricks/LTX-Video-0.9.5)

Generated media still needs an operator review, rights record and separate publication approval. Local generation removes model-token charges; it does not remove electricity, storage, licensing or platform limits.
