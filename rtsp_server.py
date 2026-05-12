import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT_DIR / "mediamtx.yml"
DEFAULT_VIDEO_DIR = ROOT_DIR / "ai_camera_monitoring" / "assets" / "videos"


def resolve_path(path):
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = ROOT_DIR / resolved
    return resolved


def start_process(command):
    return subprocess.Popen(command, cwd=ROOT_DIR)


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def build_ffmpeg_command(video_path, url):
    return [
        "ffmpeg",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-f",
        "rtsp",
        url,
    ]


def get_streams(args):
    if args.videos:
        video_paths = [resolve_path(video) for video in args.videos]
    else:
        end_index = args.start_index + args.count
        video_paths = [DEFAULT_VIDEO_DIR / f"camera_{index}.mp4" for index in range(args.start_index, end_index)]

    streams = []
    for index, video_path in enumerate(video_paths, start=args.start_index):
        if not video_path.exists():
            print(f"Video not found: {video_path}")
            return None
        name = f"{args.prefix}_{index}"
        url = f"rtsp://{args.host}:{args.port}/{name}"
        streams.append((name, video_path, url))
    return streams


def main():
    parser = argparse.ArgumentParser(description="Start local RTSP camera streams from video files.")
    parser.add_argument("--count", type=int, default=4, choices=range(1, 5), help="Number of default camera videos to stream.")
    parser.add_argument("--start-index", type=int, default=1, choices=range(1, 5), help="First default camera index to stream.")
    parser.add_argument("--videos", nargs="+", help="Custom video files. Each file becomes one RTSP camera.")
    parser.add_argument("--prefix", default="camera", help="RTSP path prefix.")
    parser.add_argument("--publish-only", action="store_true", help="Only publish streams to an already running MediaMTX server.")
    parser.add_argument("--host", default="127.0.0.1", help="RTSP host.")
    parser.add_argument("--port", default="8554", help="RTSP port.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="MediaMTX config path.")
    args = parser.parse_args()

    config_path = resolve_path(args.config)
    if not args.publish_only and not config_path.exists():
        print(f"MediaMTX config not found: {config_path}")
        return 1

    if args.start_index + args.count - 1 > 4 and not args.videos:
        print("Default camera index is out of range. Use --videos for custom sources.")
        return 1

    streams = get_streams(args)
    if streams is None:
        return 1

    mediamtx_process = None
    ffmpeg_processes = []

    def shutdown(*_):
        print("\nStopping RTSP streams...")
        for process in ffmpeg_processes:
            stop_process(process)
        stop_process(mediamtx_process)
        print("Stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.publish_only:
        print("Using existing MediaMTX server.")
    else:
        mediamtx_process = start_process(["mediamtx", str(config_path)])
        time.sleep(1)
        if mediamtx_process.poll() is not None:
            print("Failed to start MediaMTX.")
            return 1

    for name, video_path, url in streams:
        process = start_process(build_ffmpeg_command(video_path, url))
        ffmpeg_processes.append(process)
        print(f"Starting {name}: {url}")
        print(f"  video: {video_path}")

    time.sleep(2)
    for index, process in enumerate(ffmpeg_processes):
        if process.poll() is not None:
            print(f"Failed to start FFmpeg stream: {streams[index][0]}")
            shutdown()

    print("\nRTSP streams are publishing:")
    for name, _, url in streams:
        print(f"  {name}: {url}")
    print("Press Ctrl+C to stop.")

    while True:
        if mediamtx_process is not None and mediamtx_process.poll() is not None:
            print("MediaMTX stopped unexpectedly.")
            for process in ffmpeg_processes:
                stop_process(process)
            return 1

        for index, process in enumerate(ffmpeg_processes):
            if process.poll() is not None:
                print(f"FFmpeg stopped unexpectedly: {streams[index][0]}")
                for other_process in ffmpeg_processes:
                    stop_process(other_process)
                stop_process(mediamtx_process)
                return 1

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
