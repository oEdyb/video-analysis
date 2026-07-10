# Known Bugs & Fixes

Non-trivial bugs and their solutions. Check here before debugging.

<!-- Format: ## YYYY-MM-DD: Bug title
Symptom: what happened
Root cause: why
Fix: what solved it
Prevention: how to avoid it recurring
-->

## 2026-07-10: Cost estimate ignored the selected model

Symptom: `--model` changed the API model, but the output still estimated cost with K2.6 prices.
Root cause: Pricing constants were embedded in the CLI.
Fix: Store raw token usage and leave pricing outside the analysis output.
Prevention: Do not calculate cost without pricing tied to the exact model and request date.
