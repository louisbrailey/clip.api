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

def narrator_binary():
    configured=os.environ.get("NARRATOR_BIN")
    if configured:
        path=Path(configured)
        if Path(path.name).name in {"say","espeak","espeak-ng"} and path.is_absolute() and path.is_file() and os.access(path,os.X_OK):return str(path)
        raise SystemExit("NARRATOR_BIN must name say, espeak or espeak-ng")
    for name in ("say","espeak-ng","espeak"):
        found=shutil.which(name)
        if found:return found
    raise SystemExit("Narration requires say, espeak-ng or espeak on the worker")

def main():
    p=argparse.ArgumentParser();p.add_argument("output",type=Path);p.add_argument("--seconds",type=int,default=60)
    p.add_argument("--noise",choices=["white","pink","brown"],default="pink")
    p.add_argument("--theme",choices=["night","ocean","forest"],default="night");p.add_argument("--seed",type=int,default=42)
    p.add_argument("--source",type=Path);p.add_argument("--start",type=float,default=0);p.add_argument("--rights-evidence");p.add_argument("--script",help="Original narration synthesized locally by an approved system voice")
    args=p.parse_args()
    if not 1<=args.seconds<=3600 or args.start<0: p.error("Duration must be 1–3600 seconds; start must be nonnegative")
    if not 1<=args.seed<=2147483647:p.error("Seed must be a positive 31-bit integer")
    color={"night":"0x102029","ocean":"0x153e4b","forest":"0x163a2c"}[args.theme]
    if args.output.suffix.lower()!=".mp4" or args.output.exists(): p.error("Choose a new .mp4 output path")
    if args.source and (not args.source.is_file() or len(args.rights_evidence or "")<10): p.error("Licensed source requires an existing local file and a rights-evidence reference")
    npath=None
    if args.script and not args.source:
        npath=args.output.with_suffix(".narration.wav")
        if npath.exists():p.error("Narration temporary path already exists")
        narrator=narrator_binary()
        narration_command=[narrator]
        narration_command += ["-o",str(npath),"--data-format=LEI16@22050",args.script] if Path(narrator).name=="say" else ["-w",str(npath),"-s","155",args.script]
        subprocess.run(narration_command,check=True,timeout=max(30,min(300,args.seconds*4)),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        if not npath.is_file() or npath.stat().st_size<1000: p.error("Narration synthesis did not produce usable audio")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    command=[ffmpeg(),"-hide_banner","-loglevel","error","-nostdin","-n"]
    if args.source:
        command += ["-ss",str(args.start),"-i",str(args.source.resolve()),"-t",str(args.seconds),"-vf","scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x102029","-c:v","libx264","-preset","fast","-crf","24","-c:a","aac"]
    else:
        command += ["-f","lavfi","-i",f"color=c={color}:s=720x1280:r=24:d={args.seconds}","-f","lavfi","-i",f"anoisesrc=color={args.noise}:amplitude=0.06:sample_rate=48000:duration={args.seconds}:seed={args.seed}"]
        if npath:
            command += ["-i",str(npath),"-filter_complex",f"[1:a]volume=0.035[noise];[2:a]adelay=350|350,volume=2.0[voice];[noise][voice]amix=inputs=2:duration=first,afade=t=in:st=0:d=1,afade=t=out:st={max(0,args.seconds-1)}:d=1[a]","-t",str(args.seconds),"-c:v","libx264","-preset","fast","-crf","26","-map","0:v","-map","[a]","-c:a","aac","-b:a","128k"]
        else:
            command += ["-t",str(args.seconds),"-c:v","libx264","-preset","fast","-crf","26","-c:a","aac","-b:a","128k","-af",f"afade=t=in:st=0:d=1,afade=t=out:st={max(0,args.seconds-1)}:d=1"]
    command += ["-threads","1","-filter_threads","1","-pix_fmt","yuv420p","-movflags","+faststart",str(args.output.resolve())]
    subprocess.run(command,check=True,timeout=max(120,args.seconds*4))
    if npath:npath.unlink()
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    provenance={"name":args.output.name,"sha256":digest,"rights":"licensed" if args.source else "original","evidence":args.rights_evidence if args.source else ("Original procedural ambient color video, synthesized noise and the operator-approved original narration script. Generated locally; no third-party footage, soundtrack or voice recording." if args.script else "Original procedural ambient color video and synthesized noise. Generated locally with FFmpeg; no third-party footage or soundtrack."),"source":str(args.source.resolve()) if args.source else None,
               "narrated":bool(args.script),"created":time.time(),"duration_seconds":args.seconds}
    args.output.with_suffix(".rights.json").write_text(json.dumps(provenance,indent=2))
    print(json.dumps({"video":str(args.output),"sha256":digest,"bytes":args.output.stat().st_size}))
if __name__=="__main__":main()
