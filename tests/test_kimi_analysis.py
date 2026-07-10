from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from kimi_analysis import (
    enrich,
    load_prompt,
    markdown,
    parse_seconds,
    token_usage,
    transcript_lines,
    transcript_words,
)


class KimiAnalysisTest(TestCase):
    def test_parse_seconds(self) -> None:
        self.assertEqual(parse_seconds("1:02"), 62.0)
        self.assertEqual(parse_seconds("1:02:03"), 3723.0)
        self.assertEqual(parse_seconds(4), 4.0)
        self.assertIsNone(parse_seconds("not-time"))

    def test_load_prompt_sections(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prompt.md"
            path.write_text("# System\nsystem text\n# User\nuser text", encoding="utf-8")

            self.assertEqual(load_prompt(path), ("system text", "user text"))

    def test_enrich_adds_stable_fields(self) -> None:
        data = {
            "scenes": [
                {
                    "start": "0:00",
                    "end": "0:03",
                    "description": "A terminal shows a passing test run with green output.",
                },
                {
                    "start": "0:03",
                    "end": "0:09",
                    "description": "The creator is on facecam explaining the result.",
                },
            ]
        }

        enriched = enrich(data)

        self.assertTrue(enriched["scenes"][0]["scene_id"].startswith("sc_0000_"))
        self.assertEqual(enriched["derived"]["pacing"]["scene_count"], 2)

    def test_token_usage(self) -> None:
        usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        )

        self.assertEqual(
            token_usage(usage),
            {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

    def test_transcript_words_are_not_phrase_batched(self) -> None:
        segment = SimpleNamespace(
            words=[
                SimpleNamespace(start=0.1, end=0.3, word=" hello"),
                SimpleNamespace(start=0.31, end=0.5, word=" world"),
            ]
        )

        self.assertEqual(
            transcript_words([segment]),
            [
                {"index": 1, "start": 0.1, "end": 0.3, "text": "hello"},
                {"index": 2, "start": 0.31, "end": 0.5, "text": "world"},
            ],
        )

    def test_transcript_lines_group_words_for_markdown(self) -> None:
        words = [
            {"start": 0.0, "end": 0.2, "text": "one"},
            {"start": 0.2, "end": 0.4, "text": "two"},
            {"start": 0.4, "end": 0.6, "text": "three"},
            {"start": 0.6, "end": 0.8, "text": "four"},
            {"start": 0.8, "end": 1.0, "text": "five."},
            {"start": 1.0, "end": 1.2, "text": "six"},
        ]

        self.assertEqual(
            transcript_lines(words),
            [
                {"start": 0.0, "end": 1.0, "text": "one two three four five."},
                {"start": 1.0, "end": 1.2, "text": "six"},
            ],
        )

    def test_markdown_contains_visuals_and_transcript(self) -> None:
        result = {
            "scenes": [{"start": "0:00", "end": "0:03", "description": "Screen changes."}],
            "transcript": {
                "text": "hello world",
                "words": [
                    {"start": 0.0, "end": 0.5, "text": "hello"},
                    {"start": 0.5, "end": 1.0, "text": "world"},
                ],
            },
        }

        text = markdown(Path("video.mp4"), result)

        self.assertIn("## Visual Analysis", text)
        self.assertIn("## Transcript", text)
        self.assertIn("## Timestamped Transcript", text)
        self.assertIn("`0.0-1.0` hello world", text)
