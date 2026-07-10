import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "video_scene.md"
DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k2.6"


def load_prompt(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    user_marker = "\n# User\n"
    if not text.startswith("# System\n") or user_marker not in text:
        raise ValueError("prompt must contain '# System' and '# User' sections")
    system, user = text.removeprefix("# System\n").split(user_marker, 1)
    return system.strip(), user.strip()


def parse_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        parts = [float(part) for part in str(value).strip().split(":")]
    except ValueError:
        return None
    return sum(part * 60**index for index, part in enumerate(reversed(parts)))


def scene_id(scene: dict[str, Any]) -> str:
    raw = "|".join(str(scene.get(key, "")) for key in ("start", "end", "description"))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    start = parse_seconds(scene.get("start")) or 0.0
    return f"sc_{int(round(start)):04d}_{digest}"


def enrich(data: dict[str, Any]) -> dict[str, Any]:
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Kimi response must include at least one scene")

    durations = []

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"scene {index} must be an object")
        scene.setdefault("index", index)
        scene["scene_id"] = scene_id(scene)
        start = parse_seconds(scene.get("start"))
        end = parse_seconds(scene.get("end"))
        if start is not None and end is not None and end > start:
            durations.append(end - start)

    data["derived"] = {
        "pacing": pacing_metrics(durations, len(scenes)),
    }
    return data


def pacing_metrics(durations: list[float], scene_count: int) -> dict[str, float | int | None]:
    if not durations:
        return {
            "scene_count": scene_count,
            "average_scene_length_s": None,
            "median_scene_length_s": None,
            "cuts_per_minute": None,
        }
    total = sum(durations)
    average = statistics.mean(durations)
    return {
        "scene_count": scene_count,
        "average_scene_length_s": round(average, 2),
        "median_scene_length_s": round(statistics.median(durations), 2),
        "cuts_per_minute": round(max(0, scene_count - 1) / (total / 60), 2) if total else None,
    }


def token_usage(usage: Any) -> dict[str, int | None]:
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def transcript_words(segments: list[Any]) -> list[dict[str, Any]]:
    words = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            text = word.word.strip()
            if text:
                words.append(
                    {
                        "index": len(words) + 1,
                        "start": round(float(word.start), 2),
                        "end": round(float(word.end), 2),
                        "text": text,
                    }
                )
    return words


def transcribe_video(model: Any, video_path: Path, model_name: str) -> dict[str, Any]:
    raw_segments, info = model.transcribe(str(video_path), word_timestamps=True)
    raw_segments = list(raw_segments)
    words = transcript_words(raw_segments)
    text = " ".join(segment.text.strip() for segment in raw_segments if segment.text.strip())
    word_count = len(words) or len(text.split())
    return {
        "schema_version": "transcript_words_v1",
        "text": text,
        "words": words,
        "meta": {
            "source": "faster-whisper",
            "model": model_name,
            "duration_seconds": round(float(info.duration), 2),
            "language": info.language,
            "word_count": word_count,
        },
    }


def transcript_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = []
    chunk = []
    start = None
    for word in words:
        start = word["start"] if start is None else start
        chunk.append(word)
        span = float(word.get("end", word["start"])) - float(start)
        is_sentence = str(word["text"]).endswith((".", "!", "?"))
        if span >= 7 or len(chunk) >= 24 or (is_sentence and len(chunk) >= 5):
            lines.append(transcript_line(chunk))
            chunk = []
            start = None
    if chunk:
        lines.append(transcript_line(chunk))
    return lines


def transcript_line(words: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "text": " ".join(word["text"] for word in words),
    }


def markdown(video: Path, result: dict[str, Any]) -> str:
    lines = [f"# {video.stem}", ""]
    scenes = result.get("scenes") or []
    if scenes:
        lines += ["## Visual Analysis", ""]
        for scene in scenes:
            lines += [
                f"### {scene.get('start')} - {scene.get('end')}",
                "",
                scene["description"],
                "",
            ]
    transcript = result.get("transcript")
    if transcript:
        lines += ["## Transcript", "", transcript["text"], "", "## Timestamped Transcript", ""]
        lines += [
            f"- `{line['start']}-{line['end']}` {line['text']}"
            for line in transcript_lines(transcript.get("words", []))
        ]
        lines.append("")
    return "\n".join(lines)


def analyze_video(
    client: OpenAI, video_path: Path, model: str, prompt_path: Path
) -> dict[str, Any]:
    system_prompt, user_prompt = load_prompt(prompt_path)
    uploaded = client.files.create(file=video_path, purpose="video")
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "video_url", "video_url": {"url": f"ms://{uploaded.id}"}},
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=6000,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Kimi returned an empty message")
        data = enrich(json.loads(content))
        data["meta"] = {
            "model": model,
            "source_video": str(video_path),
            "prompt": str(prompt_path),
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "finish_reason": response.choices[0].finish_reason,
            "file_id": uploaded.id,
            "usage": token_usage(response.usage),
        }
        return data
    finally:
        client.files.delete(file_id=uploaded.id)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Kimi visual scene extraction on MP4s.")
    parser.add_argument("input", type=Path, help="MP4 file or folder containing MP4 files")
    parser.add_argument("--out", type=Path, default=Path("out/kimi_analysis.json"))
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--model", default=os.getenv("KIMI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--transcribe", action="store_true", help="Add word-timestamped transcript")
    parser.add_argument(
        "--transcribe-only", action="store_true", help="Skip Kimi and only transcribe"
    )
    parser.add_argument("--whisper-model", default=os.getenv("WHISPER_MODEL", "base"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    needs_kimi = not args.transcribe_only
    needs_transcript = args.transcribe or args.transcribe_only
    api_key = os.getenv("MOONSHOT_API_KEY")
    if needs_kimi and not api_key:
        raise SystemExit("MOONSHOT_API_KEY is required")

    videos = [args.input] if args.input.is_file() else sorted(args.input.glob("*.mp4"))
    if not videos:
        raise SystemExit(f"no .mp4 files found in {args.input}")

    client = None
    if needs_kimi:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("MOONSHOT_BASE_URL", DEFAULT_BASE_URL),
            timeout=float(os.getenv("KIMI_TIMEOUT_SECONDS", "240")),
            max_retries=int(os.getenv("KIMI_MAX_RETRIES", "0")),
        )
    whisper = None
    if needs_transcript:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SystemExit("Install with: uv sync --extra transcribe") from exc

        whisper = WhisperModel(args.whisper_model, device="cpu", compute_type="int8")
    results = {}
    for video in videos:
        result = {}
        if client is not None:
            print(f"analyzing {video}")
            result = analyze_video(client, video, args.model, args.prompt)
        if whisper is not None:
            print(f"transcribing {video}")
            result["transcript"] = transcribe_video(whisper, video, args.whisper_model)
        results[video.stem] = result
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        args.out.with_name(f"{video.stem}.md").write_text(markdown(video, result), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
