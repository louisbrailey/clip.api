# Local media generation

The Clip.api command line runs trusted ComfyUI workflows on the Mac and prints their output references. Generation uses the installed weights without a cloud model API call. Portal queue integration is still pending.

## Current machine

The configured instance is:

```text
http://127.0.0.1:8188/
```

It is currently running from `/Users/louisbrailey/local-media/ComfyUI` on an Apple M3 Max with 64 GB unified memory. The launcher is in the Desktop folder `local ai models`. Clip.api does not copy or re-download the model weights.

From the Clip.api checkout, run an installed API-format workflow:

```sh
export COMFYUI_URL=http://127.0.0.1:8188
python3 worker/comfyui.py ~/local-media/workflows/image-api.json \
  --prompt-node 4 --prompt "A cyan ceramic camera on an indigo backdrop"
python3 worker/comfyui.py ~/local-media/workflows/video-api.json --timeout 900
```

The image example replaces the text on node 4 of the installed image workflow. The video example runs the installed text-to-video workflow as saved. For image-to-video, export a locally configured image-to-video graph in ComfyUI API format and pass its file to the same command. Use workflows you have reviewed and keep any source files and model weights in ComfyUI's configured directories.

The command prints a prompt ID first, then the output filenames and subfolders from ComfyUI's history. Open the files in ComfyUI's output directory and review them before importing them into Clip.api's content library. If the command times out, inspect that prompt ID in ComfyUI before submitting again. The timeout stops the command from waiting and the render can continue on the Mac.

## Model choice

For this Mac, start with Wan 2.2 TI2V 5B in ComfyUI. It supports text and image conditioning and is the practical local baseline for 64 GB unified memory. Wan 2.2 14B is the higher-quality option but is documented around much larger GPU memory for direct inference. LTX-Video 2B distilled is the fast fallback for previews; LTX-Video 13B is a quality option when memory and render time allow. Check each model card and license before commercial use.

- [Wan 2.2 ComfyUI workflows](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2 model card](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B)
- [LTX-Video model card](https://huggingface.co/Lightricks/LTX-Video-0.9.5)

Generated media still needs an operator review, rights record and separate publication approval. Local generation removes model-token charges; it does not remove electricity, storage, licensing or platform limits.
