# GitHub Repository Summarizer

API service that generates LLM-powered summaries of GitHub repositories. Given a repo URL, it fetches the directory tree and README via the GitHub API, uses a fast LLM to identify the most important files, fetches those, and then uses a second LLM to produce a structured summary including what the project does, technologies used, and how it's organized.

See [DESIGN.md](DESIGN.md) for detailed design decisions, trade-offs, and performance analysis (including model choice and how repository content is filtered, selected, and assembled).

## Project Structure

```
src/repo_summarizer/
  api.py        # FastAPI routes and error mapping
  core.py       # Orchestration — single entry point: summarize_repo()
  github.py     # GitHub API client (tree, files, URL parsing)
  llm.py        # LLM API calls (file selection + summary generation)
  context.py    # Data transforms (filtering, formatting, license stripping, budget)
  config.py     # Settings and skip lists
  models.py     # Pydantic request/response models
  prompts.py    # LLM prompt templates
```

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Install & Run

```bash
cd repo-summarizer
uv sync
```

Create a `.env` file from the example (or export the variables):

```bash
cp .env.example .env
# Edit .env with your actual keys
```

Start the server:

```bash
uv run uvicorn repo_summarizer.api:app --host 0.0.0.0 --port 8000
```

### Usage

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

Response:

```json
{
  "summary": "A popular, elegant HTTP library for Python...",
  "technologies": ["Python", "urllib3", "certifi"],
  "structure": "Single-package layout with src/requests/ containing..."
}
```

### Tests

```bash
uv run pytest tests/ -v
```
