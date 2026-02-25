import re
from pathlib import PurePosixPath


README_NAMES = {"readme", "readme.md", "readme.rst", "readme.txt"}

_LICENSE_BLOCK_COMMENT = re.compile(
    r"\A\s*/\*.*?(?:license|copyright|spdx|permission is hereby granted|redistribution).*?\*/\s*",
    re.DOTALL | re.IGNORECASE,
)


def strip_license_header(content: str) -> str:
    # Try block comment first (/* ... */)
    m = _LICENSE_BLOCK_COMMENT.match(content)
    if m:
        return content[m.end():]

    # Try line comments (# or // or -- or ;)
    # Only strip if the comment block contains license/copyright keywords
    lines = content.split("\n")
    comment_prefixes = ("#", "//", "--", ";", "rem ")
    i = 0
    while i < len(lines) and (
        lines[i].strip() == "" or any(lines[i].lstrip().startswith(p) for p in comment_prefixes)
    ):
        i += 1

    if i == 0:
        return content

    header = "\n".join(lines[:i]).lower()
    if any(kw in header for kw in ("license", "copyright", "spdx", "permission is hereby granted", "redistribution")):
        return "\n".join(lines[i:]).lstrip("\n")

    return content


def filter_tree(
    tree: list[dict],
    skip_dirs: set[str],
    skip_extensions: set[str],
    skip_filenames: set[str],
) -> list[dict]:
    result = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue

        parts = PurePosixPath(entry["path"]).parts

        if any(part in skip_dirs for part in parts[:-1]):
            continue

        filename = parts[-1]
        if filename in skip_filenames:
            continue

        if PurePosixPath(filename).suffix.lower() in skip_extensions:
            continue

        # Handle compound extensions like .min.js
        if filename.endswith((".min.js", ".min.css")):
            continue

        result.append(entry)
    return result


def format_directory_tree(tree: list[dict], max_size: int = 100_000) -> str:
    lines = ["Directory structure:", ""]
    paths = sorted(
        (entry["path"] for entry in tree),
        key=lambda p: (p.count("/"), p),
    )
    used = 0
    included = 0
    for path in paths:
        if used + len(path) + 1 > max_size:
            lines.append(f"... ({len(paths) - included} more files)")
            break
        lines.append(path)
        used += len(path) + 1
        included += 1
    return "\n".join(lines)


_CONSECUTIVE_BLANK_LINES = re.compile(r"\n{3,}")
# HTML blocks with images (contributor grids, badge sections, avatar lists)
_HTML_IMG_BLOCKS = re.compile(r"<a[^>]*>\s*<img[^>]*>\s*</a>", re.IGNORECASE)
# Markdown badge images: [![alt](badge-url)](link-url) or ![alt](badge-url)
_MARKDOWN_BADGES = re.compile(r"!?\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)|!\[[^\]]*\]\(https?://img\.shields\.io[^)]*\)")


def clean_content(content: str) -> str:
    content = strip_license_header(content)
    # Remove HTML image/avatar blocks (contributor grids etc.)
    content = _HTML_IMG_BLOCKS.sub("", content)
    # Remove shield.io badges
    content = _MARKDOWN_BADGES.sub("", content)
    # Collapse 3+ consecutive blank lines into 1
    content = _CONSECUTIVE_BLANK_LINES.sub("\n\n", content)
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in content.split("\n")]
    return "\n".join(lines).strip()


def build_context(
    file_contents: dict[str, str],
    budget: int,
    max_file_size: int,
) -> str:
    parts: list[str] = []
    used = 0

    for path, content in file_contents.items():
        content = clean_content(content)
        if len(content) > max_file_size:
            content = content[:max_file_size] + "\n... (truncated)"

        file_block = f"--- {path} ---\n{content}"
        if parts:
            file_block = "\n\n" + file_block

        if used + len(file_block) > budget:
            continue

        parts.append(file_block)
        used += len(file_block)

    return "".join(parts)
