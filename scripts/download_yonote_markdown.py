"""
Download all 115 Yonote calendar documents as Markdown via documents.export API.

The documents.list `text` field is plain text (no images, no links).
The documents.export endpoint returns full Markdown with:
  - ![](url) images
  - **bold** formatting
  - - list items
  - ## headers
  - --- separators

Flow per document:
  1. POST documents.export → get fileOperation ID
  2. Poll fileOperations.info until state == "complete"
  3. POST fileOperations.redirect → get signed download URL
  4. GET download URL → save .md file
"""

import json
import os
import time
import re
import requests
from pathlib import Path

API_BASE = "https://app.yonote.ru/api"
TOKEN = "3bSOPZrpWMV0kvvraIF7DmFZ1MGBGZRLJRDERv"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

SRC_JSON = Path("/tmp/yonote_all_115.json")
OUT_DIR = Path("/tmp/yonote_markdown")
OUT_COMBINED = Path("/tmp/yonote_all_115_markdown.json")


def api_post(endpoint: str, data: dict) -> dict:
    resp = requests.post(f"{API_BASE}/{endpoint}", json=data, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def export_document(doc_id: str) -> str:
    """Start export, wait for completion, return markdown text."""
    # 1. Start export
    result = api_post("documents.export", {"id": doc_id})
    fop_id = result["data"]["fileOperation"]["id"]

    # 2. Wait for completion (max 30 seconds)
    for _ in range(30):
        info = api_post("fileOperations.info", {"id": fop_id})
        state = info["data"]["state"]
        if state == "complete":
            break
        if state == "error":
            raise RuntimeError(f"Export failed for {doc_id}: {info['data'].get('error')}")
        time.sleep(1)
    else:
        raise TimeoutError(f"Export timed out for {doc_id}")

    # 3. Get redirect URL
    redirect_resp = requests.post(
        f"{API_BASE}/fileOperations.redirect",
        json={"id": fop_id},
        headers=HEADERS,
        allow_redirects=False,
    )
    if redirect_resp.status_code in (301, 302):
        download_url = redirect_resp.headers["Location"]
    else:
        # Some APIs return the URL in body
        download_url = redirect_resp.headers.get("Location", "")
        if not download_url:
            # Try following redirects
            redirect_resp = requests.post(
                f"{API_BASE}/fileOperations.redirect",
                json={"id": fop_id},
                headers=HEADERS,
                allow_redirects=True,
            )
            return redirect_resp.text

    # 4. Download markdown (force UTF-8)
    md_resp = requests.get(download_url)
    md_resp.raise_for_status()
    md_resp.encoding = "utf-8"
    return md_resp.text


def main():
    # Load document list
    with open(SRC_JSON) as f:
        docs = json.load(f)

    print(f"Loaded {len(docs)} documents from {SRC_JSON}")

    OUT_DIR.mkdir(exist_ok=True)

    results = []
    failed = []

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        title = doc.get("title", "untitled")
        safe_name = re.sub(r'[^\w\s-]', '', title)[:60].strip().replace(' ', '_')

        print(f"[{i+1}/{len(docs)}] Exporting: {title[:60]}...", end=" ", flush=True)

        try:
            markdown = export_document(doc_id)

            # Save individual file
            md_path = OUT_DIR / f"{safe_name}.md"
            md_path.write_text(markdown, encoding="utf-8")

            # Store for combined output
            results.append({
                "id": doc_id,
                "title": title,
                "markdown": markdown,
            })

            print(f"OK ({len(markdown)} chars)")

            # Rate limit: be gentle with the API
            time.sleep(0.5)

        except Exception as e:
            print(f"FAILED: {e}")
            failed.append({"id": doc_id, "title": title, "error": str(e)})

    # Save combined JSON
    with open(OUT_COMBINED, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {len(results)} exported, {len(failed)} failed")
    print(f"Combined JSON: {OUT_COMBINED}")
    print(f"Individual files: {OUT_DIR}/")

    if failed:
        print("\nFailed documents:")
        for f_ in failed:
            print(f"  - {f_['title']}: {f_['error']}")


if __name__ == "__main__":
    main()
