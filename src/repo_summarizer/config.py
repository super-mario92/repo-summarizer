from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nebius_api_key: str
    nebius_base_url: str = "https://api.studio.nebius.com/v1"
    model_name: str = "moonshotai/Kimi-K2.5"
    file_selection_model: str = "meta-llama/Llama-3.3-70B-Instruct-fast"


class ContextConfig(BaseSettings):
    context_budget: int = 75_000  # chars total for LLM context
    max_file_size: int = 15_000  # chars per file
    max_readme_for_selection: int = 10_000  # chars of README sent to file-selection LLM


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    llm: LLMConfig = LLMConfig()
    context: ContextConfig = ContextConfig()
    github_token: str | None = None


@lru_cache
def get_config() -> Config:
    return Config()


SKIP_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    ".venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".next",
    ".nuxt",
    "target",
    "coverage",
}

SKIP_EXTENSIONS = {
    ".lock",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".obj",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "composer.lock",
    "Gemfile.lock",
    "Cargo.lock",
}
