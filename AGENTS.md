# Kimi Analysis

Lean Python CLI for Kimi video scene extraction.

## Verify

Run both commands before done:

```bash
uv run python -m unittest discover -s tests -q
uv run ruff check
```

## Boundaries

- Keep prompts in `prompts/`.
- Keep the implementation in one Python module unless a second real workflow appears.
- Keep Kimi visual analysis separate from optional Whisper transcription.
- Do not add TikTok scraping or performance-analysis code here; those belong outside this project.
