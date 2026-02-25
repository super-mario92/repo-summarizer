import pytest

from repo_summarizer import github


class TestParseGitHubUrl:
    def test_standard_url(self):
        assert github.parse_github_url("https://github.com/psf/requests") == ("psf", "requests")

    def test_trailing_slash(self):
        assert github.parse_github_url("https://github.com/psf/requests/") == ("psf", "requests")

    def test_dot_git_suffix(self):
        assert github.parse_github_url("https://github.com/psf/requests.git") == ("psf", "requests")

    def test_extra_path_segments(self):
        assert github.parse_github_url("https://github.com/psf/requests/tree/main/src") == ("psf", "requests")

    def test_http_url(self):
        assert github.parse_github_url("http://github.com/psf/requests") == ("psf", "requests")

    def test_whitespace_stripped(self):
        assert github.parse_github_url("  https://github.com/psf/requests  ") == ("psf", "requests")

    def test_not_github(self):
        with pytest.raises(github.GitHubError, match="Not a GitHub URL"):
            github.parse_github_url("https://gitlab.com/user/repo")

    def test_missing_repo(self):
        with pytest.raises(github.GitHubError, match="Invalid GitHub repository URL"):
            github.parse_github_url("https://github.com/psf")

    def test_empty_path(self):
        with pytest.raises(github.GitHubError, match="Invalid GitHub repository URL"):
            github.parse_github_url("https://github.com/")

    def test_random_string(self):
        with pytest.raises(github.GitHubError):
            github.parse_github_url("not a url at all")
