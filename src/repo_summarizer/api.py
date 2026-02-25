import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from repo_summarizer import core, github, llm, models

logger = logging.getLogger(__name__)


app = FastAPI(title="GitHub Repository Summarizer")


@app.exception_handler(github.GitHubError)
async def github_error_handler(request: Request, exc: github.GitHubError) -> JSONResponse:
    logger.error(f"GitHub error: {exc}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message},
    )


@app.exception_handler(llm.LLMError)
async def llm_error_handler(request: Request, exc: llm.LLMError) -> JSONResponse:
    logger.error(f"LLM error: {exc}")
    return JSONResponse(
        status_code=502,
        content={"status": "error", "message": f"Failed to generate summary: {exc}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": messages},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


@app.get("/")
async def root():
    return {
        "service": "GitHub Repository Summarizer",
        "usage": "POST /summarize with {\"github_url\": \"https://github.com/owner/repo\"}",
        "docs": "/docs",
    }


@app.post(
    "/summarize",
    response_model=models.SummaryResponse,
)
async def summarize(request: models.SummarizeRequest) -> models.SummaryResponse:
    return await core.summarize_repo(request.github_url)
