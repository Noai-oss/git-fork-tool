import http.client
import json
from contextlib import closing
from urllib.parse import urlencode


GITCODE_API_HOST = "api.gitcode.com"
GITHUB_API_HOST = "api.github.com"


def api_request(
    host: str,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Send a JSON HTTP request and return the status code and response text."""
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    payload: bytes | None = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    url = path
    if query:
        url = f"{path}?{urlencode(query)}"

    with closing(http.client.HTTPSConnection(host, timeout=30)) as conn:
        conn.request(method, url, body=payload, headers=request_headers)
        res = conn.getresponse()
        text = res.read().decode("utf-8")

    return res.status, text


def gitcode_api_request(
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Call the GitCode API."""
    return api_request(GITCODE_API_HOST, method, path, query, body)


def github_api_request(
    method: str,
    path: str,
    access_token: str,
    body: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Call the GitHub API."""
    return api_request(
        GITHUB_API_HOST,
        method,
        path,
        body=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "git-fork-tool",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
