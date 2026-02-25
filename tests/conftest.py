import pytest

SMALL_TREE = [
    {"path": "README.md", "type": "blob", "size": 500},
    {"path": "pyproject.toml", "type": "blob", "size": 300},
    {"path": "src/main.py", "type": "blob", "size": 1200},
    {"path": "src/utils.py", "type": "blob", "size": 800},
    {"path": "tests/test_main.py", "type": "blob", "size": 600},
]

LARGE_TREE_WITH_JUNK = [
    {"path": "README.md", "type": "blob", "size": 500},
    {"path": "package.json", "type": "blob", "size": 400},
    {"path": "package-lock.json", "type": "blob", "size": 500_000},
    {"path": "src/index.ts", "type": "blob", "size": 2000},
    {"path": "src/components/App.tsx", "type": "blob", "size": 3000},
    {"path": "src/components/Header.tsx", "type": "blob", "size": 1500},
    {"path": "node_modules/lodash/index.js", "type": "blob", "size": 50_000},
    {"path": "dist/bundle.min.js", "type": "blob", "size": 100_000},
    {"path": ".git/config", "type": "blob", "size": 200},
    {"path": "__pycache__/cache.pyc", "type": "blob", "size": 1000},
    {"path": "assets/logo.png", "type": "blob", "size": 20_000},
    {"path": "assets/logo.svg", "type": "blob", "size": 5000},
    {"path": ".github/workflows/ci.yml", "type": "blob", "size": 800},
    {"path": "Dockerfile", "type": "blob", "size": 300},
    # Tree entry (directory) — should be skipped by filter_tree
    {"path": "src/components", "type": "tree", "size": 0},
]

SAMPLE_FILE_CONTENTS = {
    "README.md": "# My Project\n\nA sample project for testing.",
    "pyproject.toml": '[project]\nname = "my-project"\ndependencies = ["fastapi"]',
    "src/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    "src/utils.py": "def helper():\n    return 42\n",
    "tests/test_main.py": "def test_app():\n    assert True\n",
}


@pytest.fixture
def small_tree():
    return [dict(e) for e in SMALL_TREE]


@pytest.fixture
def large_tree():
    return [dict(e) for e in LARGE_TREE_WITH_JUNK]


@pytest.fixture
def sample_contents():
    return dict(SAMPLE_FILE_CONTENTS)
