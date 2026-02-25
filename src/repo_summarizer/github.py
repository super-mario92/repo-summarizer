import asyncio
import base64
import re
from urllib.parse import urlparse

import httpx


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def parse_github_url(url: str) -> tuple[str, str]:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    parsed = urlparse(url)
    if parsed.hostname not in ("github.com", "www.github.com"):
        raise GitHubError("Not a GitHub URL", status_code=400)

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise GitHubError("Invalid GitHub repository URL — expected github.com/owner/repo", status_code=400)

    owner, repo = parts[0], parts[1]
    if not re.match(r"^[\w.\-]+$", owner) or not re.match(r"^[\w.\-]+$", repo):
        raise GitHubError("Invalid owner or repo name", status_code=400)

    return owner, repo


def _make_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _get(client: httpx.AsyncClient, url: str, token: str | None, **kwargs) -> httpx.Response:
    try:
        return await client.get(url, headers=_make_headers(token), **kwargs)
    except httpx.HTTPError as exc:
        raise GitHubError(f"Failed to connect to GitHub: {exc}") from exc


def _handle_error(resp: httpx.Response, context: str) -> None:
    if resp.status_code == 404:
        raise GitHubError(f"{context}: not found (or private)", status_code=404)
    if resp.status_code == 403:
        if "rate limit" in resp.text.lower():
            raise GitHubError("GitHub API rate limit exceeded", status_code=429)
        raise GitHubError("Repository is private or access denied", status_code=403)
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub API error ({resp.status_code}): {resp.text[:200]}", status_code=502)


async def fetch_default_branch(
    client: httpx.AsyncClient, owner: str, repo: str, token: str | None = None
) -> str:
    resp = await _get(client, f"https://api.github.com/repos/{owner}/{repo}", token)
    _handle_error(resp, "Repository")
    data = resp.json()
    branch = data.get("default_branch")
    if not branch:
        raise GitHubError("Repository is empty", status_code=400)
    return branch


async def fetch_repo_tree(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    token: str | None = None,
) -> list[dict]:
    resp = await _get(client, f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}", token, params={"recursive": "1"})
    _handle_error(resp, "Repository tree")
    data = resp.json()
    return data.get("tree", [])


async def fetch_file_content(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    token: str | None = None,
) -> str:
    resp = await _get(client, f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", token)
    _handle_error(resp, f"File '{path}'")
    data = resp.json()

    if data.get("encoding") != "base64" or "content" not in data:
        raise GitHubError(f"Unexpected content format for '{path}'", status_code=502)

    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception as exc:
        raise GitHubError(f"Failed to decode '{path}': {exc}", status_code=502)


async def fetch_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    paths: list[str],
    token: str | None = None,
) -> dict[str, str]:
    semaphore = asyncio.Semaphore(10)

    async def _fetch_one(path: str) -> tuple[str, str | None]:
        async with semaphore:
            try:
                content = await fetch_file_content(client, owner, repo, path, token)
                return path, content
            except GitHubError:
                return path, None

    results = await asyncio.gather(*[_fetch_one(p) for p in paths])
    return {path: content for path, content in results if content is not None}
