#!/usr/bin/env python3
"""
自動發文腳本：掃描 science/ 下所有 .md 檔案，
找出 status=ready 且 publish_date <= 現在 的文章，
發到 Facebook Page 與 Instagram，成功後將 status 改為 published。
"""

import os
import glob
import requests
import frontmatter
from datetime import datetime, timezone
import pytz
import re

TAIPEI = pytz.timezone("Asia/Taipei")
NOW = datetime.now(tz=timezone.utc)

FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_ACCESS_TOKEN = os.environ["FB_ACCESS_TOKEN"]
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")

SITE_BASE = "https://horowolf.github.io/daily-science-tw"


def build_post_url(filepath: str) -> str:
    # science/physics/bernoulli-principle.md → /physics/bernoulli-principle/
    parts = filepath.replace("science/", "").replace(".md", "").split("/")
    return f"{SITE_BASE}/{'/'.join(parts)}/"


def build_fb_message(post, url: str) -> str:
    lines = [
        post.metadata.get("title", ""),
        "",
        post.content.strip(),
        "",
        f"🔗 {url}",
    ]
    tags = post.metadata.get("tags", [])
    if tags:
        hashtags = " ".join(f"#{t}" for t in tags)
        lines += ["", hashtags]
    return "\n".join(lines)


def post_to_facebook(message: str) -> bool:
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    resp = requests.post(url, data={
        "message": message,
        "access_token": FB_ACCESS_TOKEN,
    }, timeout=30)
    if resp.ok:
        print(f"  ✅ Facebook 發文成功：{resp.json().get('id')}")
        return True
    print(f"  ❌ Facebook 發文失敗：{resp.status_code} {resp.text}")
    return False


def post_to_instagram(caption: str) -> bool:
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        print("  ⚠️  Instagram 環境變數未設定，略過。")
        return False

    # Instagram Graph API 需要先建立 media container，再 publish
    # 純文字貼文需要圖片；此處若無 cover_chart 則略過 IG
    print("  ℹ️  Instagram 發文需要圖片，目前無 cover_chart，略過。")
    return False


def parse_publish_date(raw) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else TAIPEI.localize(raw).astimezone(timezone.utc)
    try:
        # 嘗試解析 ISO 8601 字串
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = TAIPEI.localize(dt)
        return dt.astimezone(timezone.utc)
    except ValueError:
        print(f"  ⚠️  無法解析 publish_date：{raw}")
        return None


def set_status_published(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # 用正規表示式把 status: ready 改為 status: published
    updated = re.sub(r"^(status:\s*)ready\s*$", r"\1published", content, flags=re.MULTILINE)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"  📝 status → published：{filepath}")


def main():
    md_files = glob.glob("science/**/*.md", recursive=True)
    published_count = 0

    for filepath in sorted(md_files):
        post = frontmatter.load(filepath)
        status = post.metadata.get("status", "")
        if status != "ready":
            continue

        publish_date = parse_publish_date(post.metadata.get("publish_date"))
        if publish_date is None:
            print(f"[跳過] {filepath}：publish_date 未設定")
            continue
        if publish_date > NOW:
            print(f"[跳過] {filepath}：publish_date 尚未到 ({publish_date.isoformat()})")
            continue

        title = post.metadata.get("title", filepath)
        print(f"\n[發文] {title}")
        print(f"  檔案：{filepath}")

        url = build_post_url(filepath)
        message = build_fb_message(post, url)
        platforms = post.metadata.get("platforms", {})

        fb_ok = False
        if platforms.get("facebook", False):
            fb_ok = post_to_facebook(message)

        ig_ok = False
        if platforms.get("instagram", False):
            ig_ok = post_to_instagram(message)

        if fb_ok or ig_ok:
            set_status_published(filepath)
            published_count += 1

    print(f"\n完成：共發出 {published_count} 篇文章。")


if __name__ == "__main__":
    main()
