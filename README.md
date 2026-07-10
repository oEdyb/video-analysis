# Kimi Analysis

Most AI video analysis stops at the transcript. This CLI gives Kimi the MP4 and turns the visuals into timestamped scene data.

Kimi handles the frames. You can add a local Whisper transcript for the audio.

## Setup

```bash
uv sync
cp .env.example .env
```

Put your Moonshot API key in `.env`:

```dotenv
MOONSHOT_API_KEY=
```

Replace the empty value with your key.

Git ignores `.env`, so the key stays on your machine.

## Run

```bash
uv run --env-file .env kimi-analysis video.mp4 --out out/video.json
```

Pass a folder to analyze every MP4 inside it:

```bash
uv run --env-file .env kimi-analysis videos --out out/batch.json
```

Add a local transcript with Whisper:

```bash
uv sync --extra transcribe
uv run --env-file .env kimi-analysis video.mp4 --transcribe --out out/video.json
```

The CLI writes JSON plus one readable Markdown file per video. It deletes each remote Kimi upload after the analysis finishes.

Run `uv run kimi-analysis --help` for custom prompts, models, and transcript-only mode.

## Verify

```bash
uv run python -m unittest discover -s tests -q
uv run ruff check
```
