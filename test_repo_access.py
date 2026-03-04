#!/usr/bin/env python
"""
Quick test: can we discover, list, and read files from frontend-monorepo?
Run: uv run python test_repo_access.py
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GITLAB_TOKEN = os.getenv("GITLAB_API_KEY")
BASE_URL = "https://gitlab.com/api/v4"
HEADERS = {"Authorization": f"Bearer {GITLAB_TOKEN}", "Accept": "application/json"}
GROUP = "radical-app"

TARGET_REPOS = {
    "APIv3":              {"path": "radical-app/api-v3",            "id": 10979721},
    "Admin catalog":      {"path": "radical-app/admin-catalog",     "id": 46138506},
    "Pages next":         {"path": "radical-app/pages-next",        "id": 43022201},
    "Pages (legacy)":     {"path": "radical-app/pages",             "id": 10974647},
    "Frontend monorepo":  {"path": "radical-app/frontend-monorepo", "id": 51415524},
    "Booking":            {"path": "radical-app/booking",           "id": 14509262},
}


def step1_verify_repos():
    """Verify access to each of the 6 target repos by project ID."""
    print("=" * 60)
    print("STEP 1: Verify access to 6 target repos")
    print("=" * 60)

    matched = {}
    for target_name, info in TARGET_REPOS.items():
        pid = info["id"]
        r = requests.get(
            f"{BASE_URL}/projects/{pid}",
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  FAIL  {target_name} (id={pid}): HTTP {r.status_code}")
            continue
        p = r.json()
        matched[target_name] = {
            "id": p["id"],
            "name": p["name"],
            "path_with_namespace": p["path_with_namespace"],
            "default_branch": p.get("default_branch", "main"),
        }
        print(f"  OK  {target_name}")
        print(f"      id={p['id']}  path={p['path_with_namespace']}  branch={p.get('default_branch', 'main')}")

    print(f"\n  Result: {len(matched)}/6 repos accessible")
    return matched


def step2_list_tree(project_id, path_with_namespace, branch):
    """List root directory of a repo."""
    print(f"\nSTEP 2: List root tree for {path_with_namespace}")
    print("-" * 60)
    encoded_id = requests.utils.quote(str(project_id), safe="")
    r = requests.get(
        f"{BASE_URL}/projects/{encoded_id}/repository/tree",
        headers=HEADERS,
        params={"ref": branch, "per_page": 50},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  ERROR: {r.status_code} - {r.text[:200]}")
        return []
    items = r.json()
    print(f"  Found {len(items)} items at root:")
    for item in items[:20]:
        icon = "DIR " if item["type"] == "tree" else "FILE"
        print(f"    {icon}  {item['path']}")
    if len(items) > 20:
        print(f"    ... and {len(items) - 20} more")
    return items


def step3_read_file(project_id, path_with_namespace, branch, file_path):
    """Read a specific file."""
    print(f"\nSTEP 3: Read file {path_with_namespace}@{branch}:{file_path}")
    print("-" * 60)
    encoded_id = requests.utils.quote(str(project_id), safe="")
    encoded_path = requests.utils.quote(file_path, safe="")
    r = requests.get(
        f"{BASE_URL}/projects/{encoded_id}/repository/files/{encoded_path}/raw",
        headers=HEADERS,
        params={"ref": branch},
        timeout=30,
    )
    if r.status_code == 404:
        print(f"  NOT FOUND: {file_path}")
        return None
    if r.status_code != 200:
        print(f"  ERROR: {r.status_code} - {r.text[:200]}")
        return None
    content = r.text
    print(f"  SUCCESS: {len(content)} bytes")
    print(f"  First 500 chars:\n")
    print(content[:500])
    if len(content) > 500:
        print(f"\n  ... ({len(content) - 500} more bytes)")
    return content


def main():
    if not GITLAB_TOKEN:
        print("ERROR: GITLAB_API_KEY not set in .env")
        return

    print(f"Using token: {GITLAB_TOKEN[:10]}...{GITLAB_TOKEN[-4:]}\n")

    # Step 1: Discover
    matched = step1_verify_repos()
    if not matched:
        return

    # Step 2 & 3: For each matched repo, list tree and try reading a file
    print("\n" + "=" * 60)
    print("STEP 2 & 3: Access test for each repo")
    print("=" * 60)

    for target_name, info in matched.items():
        pid = info["id"]
        path = info["path_with_namespace"]
        branch = info["default_branch"]

        items = step2_list_tree(pid, path, branch)
        if not items:
            continue

        # Try reading common files
        common_files = ["README.md", "package.json", "pyproject.toml", ".gitlab-ci.yml"]
        root_file_names = [i["path"] for i in items if i["type"] == "blob"]

        read_success = False
        for f in common_files:
            if f in root_file_names:
                result = step3_read_file(pid, path, branch, f)
                if result:
                    read_success = True
                    break

        if not read_success and root_file_names:
            # Try the first file we find
            step3_read_file(pid, path, branch, root_file_names[0])

    print("\n" + "=" * 60)
    print("DONE - Review results above")
    print("=" * 60)


if __name__ == "__main__":
    main()
