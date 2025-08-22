import os
import json
import requests

def post_pr_comment(body: str) -> None:
    """
    Post a comment on the current PR if running in GitHub Actions.
    """
    token = os.getenv("GITHUB_TOKEN")
    event_path = os.getenv("GITHUB_EVENT_PATH")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not (token and event_path and repo):
        return

    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)
    pr_number = event.get("pull_request", {}).get("number")
    if not pr_number:
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    requests.post(url, headers=headers, json={"body": body}, timeout=30)