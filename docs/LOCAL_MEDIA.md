# Local media generation

Use the local Clip.api portal to animate an original photo with ComfyUI. The browser, queue, source photo, model, and library MP4 stay on the Mac. The private hosted portal remains available for other workflows.

## Animate a photo from the portal

1. Open ComfyUI from the Desktop **local ai models** folder and keep it running at `http://127.0.0.1:8188`.
2. In the Clip.api checkout, run `npm run install:ci` if dependencies are missing. For first-time setup, run `npm run build` and `npm run db:migrate:local`. Start the portal with `npm run dev`, then open [the local portal](http://localhost:5173/) and use its local sign-in.
3. Under **Controls & setup**, add a worker named **Mac photo renderer** and copy its one-time key. In a second terminal in the checkout, run the following. The prompt accepts the key without echoing it.

   ```sh
   printf 'Local worker key: '
   stty -echo
   IFS= read -r CONSTELLATION_WORKER_KEY
   stty echo
   printf '\n'
   CONSTELLATION_URL=http://localhost:5173 \
     COMFYUI_URL=http://127.0.0.1:8188 \
     WORKER_CONCURRENCY=1 \
     JOURNAL_DIR=./worker-state/local-photo \
     CONSTELLATION_WORKER_KEY="$CONSTELLATION_WORKER_KEY" \
     python3 worker/runtime.py --photo-only
   unset CONSTELLATION_WORKER_KEY
   ```

4. Open **Content library → Animate a photo**. Choose an original JPEG or PNG up to 4 MiB, describe the motion, and confirm you own the image. Select **Queue photo-to-video**. The Work queue shows progress, and the finished job has **Open generated video**.

The `--photo-only` worker claims only ComfyUI photo-to-video jobs. Other workers can handle ambient rendering, model work, and publishing separately.

The Wan 2.2 TI2V 5B preset creates a silent 384 × 224 H.264 preview with 33 frames at 16 fps. It center-crops the photo to landscape. The worker uses the existing render lease and saves one canonical MP4 in the local library. Generation uses zero cloud model tokens. Source photos remain in local portal storage and ComfyUI's input directory. The worker journal remembers accepted ComfyUI prompt IDs across retries on the same Mac. If submission was interrupted before a prompt ID was saved, inspect the ComfyUI queue before creating a replacement job.

The preset needs `wan2.2_ti2v_5B_fp16.safetensors` in `diffusion_models`, `wan2.2_vae.safetensors` in `vae`, and `umt5_xxl_fp16.safetensors` in `text_encoders`. These are installed on the configured Mac's model drive. For another machine, see the [official Wan workflow](https://docs.comfy.org/tutorials/video/wan/wan2_2). The FP16 text encoder is used on this Mac in place of the template's FP8 variant.

## Current machine

The configured instance is:

```text
http://127.0.0.1:8188/
```

It is currently running from `/Users/louisbrailey/local-media/ComfyUI` on an Apple M3 Max with 64 GB unified memory. The launcher is in the Desktop folder `local ai models`. Clip.api does not copy or re-download the model weights.

To bypass the portal for a trusted API-format workflow, run it from the Clip.api checkout:

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
