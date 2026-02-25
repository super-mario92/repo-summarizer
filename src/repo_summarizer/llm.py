import json
import logging
from functools import lru_cache

from openai import AsyncOpenAI

from repo_summarizer import config, models, prompts

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
FILE_SELECTION_TIMEOUT = 30.0
SUMMARY_TIMEOUT = 90.0


class LLMError(Exception):
    pass


@lru_cache
def _get_client(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def select_files(
    directory_tree: str,
    readme_content: str,
    max_files: int = 25,
) -> list[str]:
    cfg = config.get_config()
    client = _get_client(cfg.llm.nebius_api_key, cfg.llm.nebius_base_url)

    system_prompt = prompts.FILE_SELECTION_SYSTEM_PROMPT.format(max_files=max_files)
    user_prompt = prompts.build_file_selection_prompt(directory_tree, readme_content)
    try:
        response = await client.chat.completions.create(
            model=cfg.llm.file_selection_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=FILE_SELECTION_TIMEOUT,
        )
    except Exception as exc:
        raise LLMError(f"LLM file selection request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise LLMError("LLM returned empty response for file selection")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON for file selection: {exc}") from exc

    files = data.get("files", [])
    if not isinstance(files, list):
        raise LLMError("LLM did not return a 'files' list")

    return [f for f in files if isinstance(f, str)][:max_files]


async def generate_summary(context: str) -> models.SummaryResponse:
    cfg = config.get_config()
    client = _get_client(cfg.llm.nebius_api_key, cfg.llm.nebius_base_url)

    messages = [
        {"role": "system", "content": prompts.SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": prompts.build_summary_prompt(context)},
    ]

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=cfg.llm.model_name,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=SUMMARY_TIMEOUT,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(f"LLM summary attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            continue

        text = response.choices[0].message.content
        if not text:
            last_exc = LLMError("LLM returned empty response")
            logger.warning(f"LLM summary attempt {attempt}/{MAX_RETRIES}: empty response")
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            last_exc = exc
            logger.warning(f"LLM summary attempt {attempt}/{MAX_RETRIES}: invalid JSON: {exc}")
            continue

        try:
            return models.SummaryResponse(**data)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"LLM summary attempt {attempt}/{MAX_RETRIES}: missing fields: {exc}")
            continue

    raise LLMError(f"LLM summary failed after {MAX_RETRIES} attempts: {last_exc}")
