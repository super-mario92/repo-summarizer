import base64
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from repo_summarizer import api


@pytest.fixture
def client():
    return TestClient(api.app, raise_server_exceptions=False)


FILE_SELECTION_RESPONSE = json.dumps({"files": ["setup.py"]})

LLM_RESPONSE = json.dumps(
    {
        "summary": "A popular HTTP library for Python.",
        "technologies": ["Python", "setuptools"],
        "structure": "Simple single-package layout.",
    }
)


def _mock_github_api(owner: str = "psf", repo: str = "requests"):
    """Set up respx mocks for GitHub API calls."""
    respx.get(f"https://api.github.com/repos/{owner}/{repo}").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    respx.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/main",
        params={"recursive": "1"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "tree": [
                    {"path": "README.md", "type": "blob", "size": 100},
                    {"path": "setup.py", "type": "blob", "size": 200},
                ]
            },
        )
    )
    readme_content = base64.b64encode(b"# Requests\nHTTP for Humans.").decode()
    setup_content = base64.b64encode(b'from setuptools import setup\nsetup(name="requests")').decode()
    respx.get(f"https://api.github.com/repos/{owner}/{repo}/contents/README.md").mock(
        return_value=httpx.Response(200, json={"content": readme_content, "encoding": "base64"})
    )
    respx.get(f"https://api.github.com/repos/{owner}/{repo}/contents/setup.py").mock(
        return_value=httpx.Response(200, json={"content": setup_content, "encoding": "base64"})
    )


def _mock_llm_calls():
    """Mock both LLM calls: file selection and summary."""
    respx.post("https://api.studio.nebius.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": FILE_SELECTION_RESPONSE}, "index": 0}],
                    "model": "moonshotai/Kimi-K2.5",
                },
            ),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": LLM_RESPONSE}, "index": 0}],
                    "model": "moonshotai/Kimi-K2.5",
                },
            ),
        ]
    )


@respx.mock
def test_successful_summarize(client, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    _mock_github_api()
    _mock_llm_calls()

    resp = client.post("/summarize", json={"github_url": "https://github.com/psf/requests"})
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "technologies" in data
    assert "structure" in data
    assert isinstance(data["technologies"], list)


def test_invalid_url(client):
    resp = client.post("/summarize", json={"github_url": "https://gitlab.com/user/repo"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "error"
    assert "message" in data


def test_missing_url(client):
    resp = client.post("/summarize", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert data["status"] == "error"
    assert "message" in data


@respx.mock
def test_repo_not_found(client, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    respx.get("https://api.github.com/repos/nonexist/nonexist").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )

    resp = client.post("/summarize", json={"github_url": "https://github.com/nonexist/nonexist"})
    assert resp.status_code == 404


@respx.mock
def test_llm_error(client, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    _mock_github_api()

    # File selection LLM call fails
    respx.post("https://api.studio.nebius.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    resp = client.post("/summarize", json={"github_url": "https://github.com/psf/requests"})
    assert resp.status_code == 502
