#!/usr/bin/env python3
"""Generate an RSS feed for China CDC respiratory sentinel surveillance posts."""

from __future__ import annotations

import argparse
import email.utils
import html
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape


COLUMN_URL = "https://www.chinacdc.cn/jksj/jksj04_14275/"
TITLE = "中国疾控：全国急性呼吸道传染病哨点监测情况"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
CHINA_TZ = timezone(timedelta(hours=8), "CST")


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    pub_date: str
    description: str


ITEM_RE = re.compile(
    r'<a\s+href="(?P<href>[^"]+)"[^>]*>'
    r"(?P<title>.*?)"
    r"<span>\s*(?P<date>\d{4}-\d{2}-\d{2})\s*</span>\s*</a>\s*"
    r'<p\s+class="zy">\s*(?P<desc>.*?)\s*</p>',
    re.S,
)
LIST_RE = re.compile(r'<ul\s+class="xw_list">\s*(?P<body>.*?)\s*</ul>', re.S)
LI_RE = re.compile(r"<li>\s*(?P<body>.*?)\s*</li>", re.S)


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    if re.search(br"charset\s*=\s*[\"']?utf-8", raw[:2048], re.I):
        charset = "utf-8"
    return raw.decode(charset, errors="replace")


def clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def page_urls(pages: int) -> list[str]:
    urls = [COLUMN_URL]
    for i in range(1, max(1, pages)):
        urls.append(urljoin(COLUMN_URL, f"index_{i}.html"))
    return urls


def parse_items(page_url: str, text: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    list_match = LIST_RE.search(text)
    if not list_match:
        return items
    for li_match in LI_RE.finditer(list_match.group("body")):
        match = ITEM_RE.search(li_match.group("body"))
        if not match:
            continue
        title = clean_html_text(match.group("title"))
        desc = clean_html_text(match.group("desc"))
        date_text = match.group("date")
        link = urljoin(page_url, match.group("href"))
        if "全国急性呼吸道传染病哨点监测情况" not in title:
            continue
        items.append(
            FeedItem(
                title=title,
                link=link,
                pub_date=date_text,
                description=desc,
            )
        )
    return items


def collect_items(pages: int, limit: int) -> list[FeedItem]:
    seen: set[str] = set()
    items: list[FeedItem] = []
    for url in page_urls(pages):
        try:
            text = fetch_text(url)
        except Exception as exc:  # noqa: BLE001 - command-line diagnostics
            print(f"warning: failed to fetch {url}: {exc}", file=sys.stderr)
            continue
        for item in parse_items(url, text):
            if item.link in seen:
                continue
            seen.add(item.link)
            items.append(item)

    items.sort(key=lambda item: (item.pub_date, item.title), reverse=True)
    return items[:limit]


def rfc822(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=CHINA_TZ)
    return email.utils.format_datetime(dt)


def build_rss(items: list[FeedItem], feed_url: str | None = None) -> str:
    now = email.utils.format_datetime(datetime.now(CHINA_TZ))
    atom_link = ""
    if feed_url:
        atom_link = (
            f'    <atom:link href="{escape(feed_url)}" rel="self" '
            'type="application/rss+xml" />\n'
        )

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n',
        "  <channel>\n",
        f"    <title>{escape(TITLE)}</title>\n",
        f"    <link>{escape(COLUMN_URL)}</link>\n",
        "    <description>中国疾病预防控制中心每周发布的全国急性呼吸道传染病哨点监测情况。</description>\n",
        "    <language>zh-CN</language>\n",
        f"    <lastBuildDate>{escape(now)}</lastBuildDate>\n",
        "    <ttl>720</ttl>\n",
        atom_link,
    ]

    for item in items:
        parts.extend(
            [
                "    <item>\n",
                f"      <title>{escape(item.title)}</title>\n",
                f"      <link>{escape(item.link)}</link>\n",
                f"      <guid isPermaLink=\"true\">{escape(item.link)}</guid>\n",
                f"      <pubDate>{escape(rfc822(item.pub_date))}</pubDate>\n",
                f"      <description>{escape(item.description)}</description>\n",
                "    </item>\n",
            ]
        )

    parts.extend(["  </channel>\n", "</rss>\n"])
    return "".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="chinacdc-respiratory-sentinel.xml",
        help="RSS output path",
    )
    parser.add_argument("--pages", type=int, default=2, help="column pages to scan")
    parser.add_argument("--limit", type=int, default=30, help="maximum feed items")
    parser.add_argument("--feed-url", default=None, help="public URL of the generated feed")
    args = parser.parse_args()

    items = collect_items(pages=args.pages, limit=args.limit)
    if not items:
        print("error: no matching China CDC surveillance posts found", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_rss(items, feed_url=args.feed_url), encoding="utf-8")
    print(f"wrote {output} with {len(items)} items")
    print(f"latest: {items[0].title} {items[0].pub_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
