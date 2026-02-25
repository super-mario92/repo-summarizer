# Design Decisions

This document explains the key design decisions and trade-offs. For setup and usage, see [README.md](README.md).

## Architecture

```
Client  →  FastAPI (/summarize)
               │
               ▼
         GitHub REST API  (fetch tree + root README)
               │
               ▼
         Nebius LLM API   (pass 1: select files from tree + README)
               │
               ▼
         GitHub REST API  (fetch selected files only)
               │
               ▼
         Nebius LLM API   (pass 2: generate summary from file contents)
               │
               ▼
         JSON Response     (summary, technologies, structure)
```

Dependency flow: `api` → `core` → `github`, `llm`, `context`, `config`

The API layer is a thin HTTP wrapper that only maps exceptions to status codes. All orchestration lives in `core.py`, which wires together the other modules.

## Why GitHub REST API (not git clone)

**Chosen over:** `git clone`, GitHub archive download

- **Selective fetching** — only download the ~15 files we need, not the entire repo
- **No disk I/O** — everything stays in memory
- **Clean filtering** — skip binary/vendor files before downloading content
- **Concurrent fetching** — semaphore-limited (max 10 parallel requests) for speed without hitting rate limits

Only the root README is fetched for file selection. Early versions fetched all READMEs, which for large repos (e.g. PyTorch) meant 125+ unnecessary API calls.

## Why Two-Pass LLM File Selection (not heuristics)

**Chosen over:** Greedy fill by hardcoded priority tiers

A previous approach classified files into priority tiers (READMEs > manifests > entry points > other) and fetched greedily until a budget was exhausted. Two problems:

1. **API rate limits** — fetching all filtered files (often 500+) burned through GitHub's 5,000 req/hour limit quickly
2. **Heuristic blindness** — hardcoded rules can't know that `src/routes.py` is more informative than `setup.cfg` for a specific project

The two-pass approach solves both: the LLM picks ~15 files based on actual context (README + directory tree), reducing GitHub API calls by ~30x while making smarter selections.

**Trade-off:** Two LLM calls instead of one. The first call is cheap (small output: just a list of paths), so added latency is minimal.

## Why Dual Models (Llama Fast + Kimi)

| Pass | Model | Rationale |
|------|-------|-----------|
| File selection | Llama 3.3 70B Fast (~120 tok/s) | Simple extraction task — just pick paths from a list. 6x faster than Kimi. |
| Summary | Kimi-K2.5 (~60 tok/s, 256k context) | Needs strong code reasoning. GPQA 87.6, SWE-Bench 76.8, LiveCodeBench 85.0. |

**Why not Kimi for both?** File selection went from ~30s to ~5s by switching to Llama Fast, with comparable selection quality.

**Why not Llama for both?** Llama hallucinates ~30% of file paths (guesses plausible names like `gateway/gateway.ts` instead of actual `gateway/server.ts`). Acceptable for file selection (we skip invalid paths), but not for the summary where accuracy matters.

**Hallucination mitigation:** Request 25 files, take the first 15 valid ones. Combined with a stricter prompt ("copy paths character-for-character"), this consistently yields 12-15 usable files.

## Prompt Engineering

Both prompts use `response_format: {"type": "json_object"}` to guarantee parseable output without markdown fences or extra text.

**File selection prompt** — designed to fight Llama's tendency to hallucinate paths:
- Explicit instruction to "copy paths character-for-character" from the directory tree
- Positive priority list (manifests, entry points, core source) and negative exclusion list (tests, docs, generated files, lock files, binaries) to focus the selection
- `temperature=0.0` for deterministic output — creativity isn't useful here

**Summary prompt** — structured to produce the exact response schema:
- Specifies the three output fields (`summary`, `technologies`, `structure`) with descriptions of what each should contain
- `temperature=0.2` for slight variation without hallucination — summaries benefit from natural phrasing

Both use a "senior software engineer" role to ground the model in technical analysis rather than generic descriptions.

## Context Budget Tuning

All values were tuned by testing against repos of varying sizes (small: psf/requests, medium: Netflix/metaflow, large: PyTorch, NVIDIA/openclaw).

**Pass 1 — file selection input:**

| Input | Cap | Why |
|-------|-----|-----|
| Directory tree | 100k chars | Depth-sorted (root files first), so truncation only cuts deeply nested files. Without this cap, PyTorch's 600k+ char tree overflows Kimi's 256k token limit. |
| Root README | 10k chars | LLM only needs the project overview. openclaw's 113k char README caused 3+ minute response times without this cap. |

**Pass 2 — summary input:**

| Parameter | Value | Why |
|-----------|-------|-----|
| `context_budget` | 75k chars | Sufficient for ~15 files after cleaning. Keeps summary latency under 30s. |
| `max_file_size` | 15k chars | Prevents one large file from consuming the budget. Most config/entry point files fit entirely. |

**Content cleaning** removes noise before truncation:
- License/copyright headers (block and line comments)
- HTML contributor/avatar grids (openclaw's README was ~40% avatar grid)
- Shield.io badge images
- Excessive blank lines

**Directory tree sorting:** Depth-first, then alphabetical. Ensures root configs and entry points appear before deeply nested files — critical when the tree gets truncated for large repos.

## Performance

Typical latency for a large repo (~7k files):

| Step | Duration | Notes |
|------|----------|-------|
| GitHub tree + README fetch | ~2s | 3 API calls |
| LLM file selection | ~5s | Llama 3.3 70B Fast, ~110k chars input |
| GitHub file fetch | ~1s | ~15 concurrent API calls |
| LLM summary | ~25s | Kimi-K2.5, ~55-75k chars input |
| **Total** | **~35s** | |

Key optimizations:
- Dual-model strategy: file selection from ~30s → ~5s (6x faster)
- Content cleaning + reduced budgets: summary input ~100k → ~55-75k chars, roughly halving summary time

**Timeouts and retries:** Nebius inference latency fluctuates significantly (observed 104s vs. typical 30s for identical input). To handle this:

| Call | Timeout | Retries |
|------|---------|---------|
| File selection (Llama) | 30s | None — fast model, spikes are rare |
| Summary (Kimi) | 90s | 1 retry — if the first attempt times out or returns invalid output, retry once (likely hits a warm instance) |

This caps worst-case latency instead of waiting for the OpenAI client's 10-minute default timeout.

## Known Limitations

- **Tree truncation:** Repos with 20k+ files hit the 100k char cap. Deeply nested important files may be invisible to file selection.
- **Llama path hallucination:** ~30% invalid paths, mitigated by over-requesting (25 → 15). Could fall back to Kimi if too few paths are valid.
- **Fixed budgets:** Not tuned per repo size — a small repo doesn't need 15 files, a monorepo might benefit from more.
- **Evaluation setup:** Currently I manually checked a few repos but for future performance and quality optimization, a more structured evaluation approach is needed. The first step for that would be to clearly define good answers for the three criteria: summary quality, technology extraction, and structure extraction. Then we can first create an evalaution dataset and manually score the results and maybe later try to align an llm to match our judgement in order to scale evaluation.
