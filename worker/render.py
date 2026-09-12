"""Render an original white/pink-noise MP4, or trim explicitly licensed media.

No scraped inputs, shell interpolation, external downloads, or model commands.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

def ffmpeg():
    binary=os.getenv("FFMPEG_BIN") or shutil.which("ffmpeg")
    if binary: return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError: raise SystemExit("Install FFmpeg or the optional imageio-ffmpeg package")

def main():
    p=argparse.ArgumentParser();p.add_argument("output",type=Path);p.add_argument("--seconds",type=int,default=60)
    p.add_argument("--noise",choices=["white","pink","brown"],default="pink")
    p.add_argument("--theme",choices=["night","ocean","forest"],default="night");p.add_argument("--seed",type=int,default=42)
    p.add_argument("--source",type=Path);p.add_argument("--start",type=float,default=0);p.add_argument("--rights-evidence")
    args=p.parse_args()
    if not 1<=args.seconds<=3600 or args.start<0: p.error("Duration must be 1–3600 seconds; start must be nonnegative")
    if not 1<=args.seed<=2147483647:p.error("Seed must be a positive 31-bit integer")
    color={"night":"0x102029","ocean":"0x153e4b","forest":"0x163a2c"}[args.theme]
    if args.output.suffix.lower()!=".mp4" or args.output.exists(): p.error("Choose a new .mp4 output path")
    if args.source and (not args.source.is_file() or len(args.rights_evidence or "")<10): p.error("Licensed source requires an existing local file and a rights-evidence reference")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    command=[ffmpeg(),"-hide_banner","-loglevel","error","-nostdin","-n"]
    if args.source:
        command += ["-ss",str(args.start),"-i",str(args.source.resolve()),"-t",str(args.seconds),"-vf","scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x102029","-c:v","libx264","-preset","fast","-crf","24","-c:a","aac"]
    else:
        command += ["-f","lavfi","-i",f"color=c={color}:s=720x1280:r=24:d={args.seconds}","-f","lavfi","-i",f"anoisesrc=color={args.noise}:amplitude=0.06:sample_rate=48000:duration={args.seconds}:seed={args.seed}","-t",str(args.seconds),"-c:v","libx264","-preset","fast","-crf","26","-c:a","aac","-b:a","128k","-af",f"afade=t=in:st=0:d=1,afade=t=out:st={max(0,args.seconds-1)}:d=1"]
    command += ["-threads","1","-filter_threads","1","-pix_fmt","yuv420p","-movflags","+faststart",str(args.output.resolve())]
    subprocess.run(command,check=True,timeout=max(120,args.seconds*4))
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    provenance={"name":args.output.name,"sha256":digest,"rights":"licensed" if args.source else "original","evidence":args.rights_evidence if args.source else "Original procedural ambient color video and synthesized noise. Generated locally with FFmpeg; no third-party footage or soundtrack.","source":str(args.source.resolve()) if args.source else None,"created":time.time(),"duration_seconds":args.seconds}
    args.output.with_suffix(".rights.json").write_text(json.dumps(provenance,indent=2))
    print(json.dumps({"video":str(args.output),"sha256":digest,"bytes":args.output.stat().st_size}))
if __name__=="__main__":main()
