import pytest

from repo_summarizer import config, context


class TestFilterTree:
    def test_removes_node_modules(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "node_modules/lodash/index.js" not in paths

    def test_removes_git_dir(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert ".git/config" not in paths

    def test_removes_pycache(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "__pycache__/cache.pyc" not in paths

    def test_removes_lock_files(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "package-lock.json" not in paths

    def test_removes_binary_files(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "assets/logo.png" not in paths
        assert "assets/logo.svg" not in paths

    def test_removes_min_js(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "dist/bundle.min.js" not in paths

    def test_removes_tree_entries(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "src/components" not in paths

    def test_keeps_source_files(self, large_tree):
        result = context.filter_tree(large_tree, config.SKIP_DIRS, config.SKIP_EXTENSIONS, config.SKIP_FILENAMES)
        paths = [e["path"] for e in result]
        assert "README.md" in paths
        assert "package.json" in paths
        assert "src/index.ts" in paths
        assert "src/components/App.tsx" in paths
        assert ".github/workflows/ci.yml" in paths
        assert "Dockerfile" in paths


class TestFormatDirectoryTree:
    def test_includes_header(self, small_tree):
        result = context.format_directory_tree(small_tree)
        assert "Directory structure:" in result

    def test_includes_full_paths(self, small_tree):
        result = context.format_directory_tree(small_tree)
        assert "README.md" in result
        assert "src/main.py" in result

    def test_truncates_large_trees(self):
        tree = [{"path": f"src/file_{i}.py", "type": "blob", "size": 100} for i in range(1000)]
        result = context.format_directory_tree(tree, max_size=500)
        assert "more files" in result
        assert len(result) < 600


class TestBuildContext:
    def test_includes_file_contents(self, sample_contents):
        ctx = context.build_context(sample_contents, budget=100_000, max_file_size=10_000)
        assert "--- README.md ---" in ctx
        assert "# My Project" in ctx

    def test_respects_budget(self, sample_contents):
        ctx = context.build_context(sample_contents, budget=100, max_file_size=10_000)
        assert len(ctx) <= 100

    def test_truncates_large_files(self):
        contents = {"big.py": "x" * 20_000}
        ctx = context.build_context(contents, budget=100_000, max_file_size=100)
        assert "... (truncated)" in ctx

    def test_empty_contents(self):
        ctx = context.build_context({}, budget=100_000, max_file_size=10_000)
        assert ctx == ""

    def test_strips_license_headers(self):
        content = "/* Copyright 2024 Acme Corp. Licensed under MIT. */\nimport foo\n"
        ctx = context.build_context({"main.py": content}, budget=100_000, max_file_size=10_000)
        assert "Copyright" not in ctx
        assert "import foo" in ctx


class TestCleanContent:
    def test_collapses_blank_lines(self):
        content = "line1\n\n\n\n\nline2\n"
        assert context.clean_content(content) == "line1\n\nline2"

    def test_strips_trailing_whitespace(self):
        content = "line1   \nline2  \n"
        assert context.clean_content(content) == "line1\nline2"

    def test_strips_license_and_cleans(self):
        content = "# Copyright 2024\n\n\n\n\nimport os   \n"
        result = context.clean_content(content)
        assert "Copyright" not in result
        assert result == "import os"

    def test_strips_html_avatar_blocks(self):
        content = 'Some text\n<a href="https://github.com/user"><img src="avatar.png"></a>\nMore text'
        result = context.clean_content(content)
        assert "<img" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_strips_shield_badges(self):
        content = '# Project\n![build](https://img.shields.io/badge/build-passing-green)\nDescription'
        result = context.clean_content(content)
        assert "img.shields.io" not in result
        assert "# Project" in result
        assert "Description" in result


class TestStripLicenseHeader:
    def test_block_comment_license(self):
        content = "/* Copyright 2024 MIT License */\nimport os\n"
        assert context.strip_license_header(content) == "import os\n"

    def test_hash_comment_license(self):
        content = "# Copyright 2024 Acme Corp\n# Licensed under Apache 2.0\n\nimport os\n"
        assert context.strip_license_header(content) == "import os\n"

    def test_double_slash_license(self):
        content = "// Copyright 2024 Google LLC\n// SPDX-License-Identifier: Apache-2.0\n\npackage main\n"
        assert context.strip_license_header(content) == "package main\n"

    def test_no_license_untouched(self):
        content = "# This is a regular comment\nimport os\n"
        assert context.strip_license_header(content) == content

    def test_no_comments_untouched(self):
        content = "import os\nprint('hello')\n"
        assert context.strip_license_header(content) == content

    def test_mit_license_block(self):
        content = (
            "/*\n"
            " * Permission is hereby granted, free of charge, to any person\n"
            " * obtaining a copy of this software...\n"
            " */\n"
            "const x = 1;\n"
        )
        result = context.strip_license_header(content)
        assert "Permission" not in result
        assert "const x = 1;" in result
