#!/usr/bin/env python3
"""youtube_streamer.py  ·  simple YouTube RTMP broadcaster

This script uses ffmpeg to stream a video file to YouTube Live.

Example:
  ./youtube_streamer.py --input video.mp4 --stream-key ABCD-1234-XYZ

ffmpeg must be installed and available on the PATH.
"""

from __future__ import annotations

import argparse
import subprocess
import shutil
from typing import List

YOUTUBE_RTMP_URL = "rtmp://a.rtmp.youtube.com/live2"


def run_ffmpeg(input_source: str, stream_key: str, extra_args: List[str]) -> None:
    """Run ffmpeg with sane defaults to push the input to YouTube."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    cmd = [
        "ffmpeg",
        "-re",
        "-i",
        input_source,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-maxrate",
        "3000k",
        "-bufsize",
        "6000k",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "50",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "44100",
        *extra_args,
        "-f",
        "flv",
        f"{YOUTUBE_RTMP_URL}/{stream_key}",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Stream a video file to YouTube using ffmpeg."
    )
    p.add_argument("-i", "--input", required=True, help="Video file to stream.")
    p.add_argument("-k", "--stream-key", required=True, help="YouTube stream key.")
    p.add_argument(
        "extra",
        nargs=argparse.REMAINDER,
        help="Additional ffmpeg arguments to append at the end.",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    run_ffmpeg(args.input, args.stream_key, args.extra)


if __name__ == "__main__":
    main()
