# Video Analysis

Kimi has this super convenient API feature where you upload an MP4, then pass it straight back to the model as video input. It looks at the frames and gives you timestamped scene data.

This CLI is the small wrapper around that. Add Whisper if you want a local audio transcript too.

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
