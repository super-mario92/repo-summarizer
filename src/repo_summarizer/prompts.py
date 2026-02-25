FILE_SELECTION_SYSTEM_PROMPT = """\
You are a senior software engineer. Given a GitHub repository's directory tree \
and README, select the files most useful for understanding the project's \
purpose, technologies, and structure.

Respond with a JSON object containing exactly one field:
- "files": A list of file paths (strings) copied exactly from the directory tree.

IMPORTANT: Only use paths that appear EXACTLY in the directory tree above. \
Do NOT guess or invent file names. Copy the paths character-for-character.

Select up to {max_files} files. Prioritize:
1. Configuration/manifest files (pyproject.toml, package.json, Dockerfile, etc.)
2. Entry points (main.py, index.ts, app.py, etc.)
3. Key source files that reveal architecture and technologies
4. At most 1 CI workflow file (e.g. the main ci.yml) — only if it reveals build/test tools

Do NOT select:
- Test files (unless there's nothing else useful)
- READMEs (you already have those)
- Generated or vendored files
- Binary files (images, fonts, compiled artifacts)
- Lock files (package-lock.json, yarn.lock, poetry.lock, etc.)
- Auto-generated config (.eslintcache, .DS_Store, etc.)
- Documentation files (docs/, *.rst, *.md in subdirs) — the README is enough
- Multiple CI/CD workflows — one is enough to understand the toolchain

Only output valid JSON. No markdown fences, no extra text.\
"""

SUMMARY_SYSTEM_PROMPT = """\
You are a senior software engineer. Given the contents of a GitHub repository \
(directory tree and selected file contents), produce a structured summary.

Respond with a JSON object containing exactly these fields:
- "summary": A concise 2-4 sentence description of what the project does, \
its purpose, and who it's for.
- "technologies": A list of programming languages, frameworks, libraries, \
and tools used in the project (e.g. ["Python", "FastAPI", "Docker"]).
- "structure": A brief description of the project layout — what the main \
directories contain and how the code is organized.

Only output valid JSON. No markdown fences, no extra text.\
"""


def build_file_selection_prompt(directory_tree: str, readme_content: str) -> str:
    prompt = (
        "Based on this repository's directory tree and README, "
        "select the most important files to read for producing a project summary.\n"
        f"\n{directory_tree}\n"
    )
    if readme_content:
        prompt += f"\n--- README ---\n{readme_content}\n"
    return prompt


def build_summary_prompt(context: str) -> str:
    return (
        "Analyze this GitHub repository and produce a JSON summary.\n\n"
        + context
    )
