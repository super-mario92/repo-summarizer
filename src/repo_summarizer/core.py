import logging
import time
from typing import NamedTuple

import httpx

from repo_summarizer import config, context, github, llm, models


class RepoData(NamedTuple):
    filtered_tree: list[dict]
    readme_content: str | None
    readme_path: str | None

logger = logging.getLogger(__name__)


async def _fetch_tree_and_readme(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    token: str | None,
) -> RepoData:
    branch = await github.fetch_default_branch(client, owner, repo, token)
    tree = await github.fetch_repo_tree(client, owner, repo, branch, token)

    if not tree:
        raise github.GitHubError("Repository is empty", status_code=400)

    filtered = context.filter_tree(tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
    logger.info(f"Tree: {len(tree)} entries, {len(filtered)} after filtering")

    readme_path = next(
        (e["path"] for e in filtered if e["path"].lower() in context.README_NAMES),
        None,
    )
    readme_content = (
        await github.fetch_file_content(client, owner, repo, readme_path, token)
        if readme_path else None
    )

    return RepoData(filtered, readme_content, readme_path)


async def _select_files(
    filtered: list[dict],
    root_readme_content: str | None,
    max_readme_for_selection: int,
) -> list[str]:
    dir_tree = context.format_directory_tree(filtered)
    # Cap README for file selection — the LLM only needs the overview, not the full doc
    readme_for_selection = ""
    if root_readme_content:
        readme_for_selection = root_readme_content[:max_readme_for_selection]
        if len(root_readme_content) > max_readme_for_selection:
            readme_for_selection += "\n... (truncated)"

    logger.info(f"File selection input: dir_tree={len(dir_tree)} chars, readme={len(readme_for_selection)} chars")
    t0 = time.monotonic()
    selected_paths = await llm.select_files(dir_tree, readme_for_selection)
    logger.info(f"File selection completed in {time.monotonic() - t0:.1f}s")

    tree_paths = {entry["path"] for entry in filtered}
    all_valid = [p for p in selected_paths if p in tree_paths]
    valid_paths = all_valid[:15]
    logger.info(f"LLM selected {len(selected_paths)} files, {len(all_valid)} valid (using top {len(valid_paths)}):")
    for p in selected_paths:
        status = "ok" if p in tree_paths else "INVALID"
        logger.debug(f"  [{status}] {p}")

    return valid_paths


async def summarize_repo(github_url: str) -> models.SummaryResponse:
    cfg = config.get_config()
    owner, repo = github.parse_github_url(github_url)
    logger.info(f"Summarizing {owner}/{repo}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        repo_data = await _fetch_tree_and_readme(
            client, owner, repo, cfg.github_token,
        )
        valid_paths = await _select_files(
            repo_data.filtered_tree, repo_data.readme_content, cfg.context.max_readme_for_selection,
        )

        # Fetch selected files, reusing already-fetched README
        paths_to_fetch = [p for p in valid_paths if p != repo_data.readme_path]
        file_contents = await github.fetch_files(
            client, owner, repo, paths_to_fetch, cfg.github_token,
        )
        if repo_data.readme_content and repo_data.readme_path:
            file_contents[repo_data.readme_path] = repo_data.readme_content

    ctx = context.build_context(file_contents, cfg.context.context_budget, cfg.context.max_file_size)
    logger.info(f"Built context: {len(ctx)} chars")

    t0 = time.monotonic()
    result = await llm.generate_summary(ctx)
    logger.info(f"Summary generated in {time.monotonic() - t0:.1f}s")
    return result
