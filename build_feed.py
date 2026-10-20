#!/usr/bin/env python3
"""Build feed.xml for River 川 from the TEXTS list in index.html.

Run from the river folder after adding or editing texts:

    python3 build_feed.py

One item per text, linking to its page (https://river.yoso.one/#t<n>).
Texts have no dates of their own, so each item's date is the day it first
appeared in the feed: dates already in feed.xml are kept, and only new texts
get the time of this run. Feed readers therefore show only what is new.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

SITE = "https://river.yoso.one/"
HERE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))

STRING = r'"((?:[^"\\]|\\.)*)"'
ITEM = re.compile(r"\{n:(\d+),\s*t:" + STRING + r",\s*v:" + STRING)


def js_string(s):
    return json.loads('"' + s + '"')


def texts():
    html = (HERE / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const TEXTS = ["):]
    block = block[: block.index("\n];")]
    found = [(int(n), js_string(t), js_string(v)) for n, t, v in ITEM.findall(block)]
    if not found:
        raise SystemExit("No texts found in index.html")
    return found


def known_dates():
    """guid -> pubDate already in feed.xml, so dates never move."""
    feed = HERE / "feed.xml"
    if not feed.exists():
        return {}
    xml = feed.read_text(encoding="utf-8")
    return dict(re.findall(r"<guid[^>]*>([^<]+)</guid>\s*<pubDate>([^<]+)</pubDate>", xml))


def verse_html(v):
    stanzas = re.split(r"\n\s*\n", v)
    return "".join("<p>" + "<br>".join(escape(l) for l in st.split("\n")) + "</p>" for st in stanzas)


def main():
    items = texts()
    dates = known_dates()
    now = datetime.now(JST).replace(microsecond=0)
    out = []
    for i, (n, t, v) in enumerate(items):
        guid = f"river-t{n}"
        # New texts: list order, first text newest, one second apart.
        date = dates.get(guid) or format_datetime(now - timedelta(seconds=i))
        body = verse_html(v) + "<p>– Yoso</p>"
        out.append(
            "  <item>\n"
            f"    <title>{xml_escape(t)}</title>\n"
            f"    <link>{SITE}#t{n}</link>\n"
            f'    <guid isPermaLink="false">{guid}</guid>\n'
            f"    <pubDate>{date}</pubDate>\n"
            f"    <description>{xml_escape(body)}</description>\n"
            "  </item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        "  <title>River 川</title>\n"
        f"  <link>{SITE}</link>\n"
        f'  <atom:link href="{SITE}feed.xml" rel="self" type="application/rss+xml"/>\n'
        "  <description>Short texts by Yoso that move like a quiet river: on breath, love, spring and surrendering to the flow.</description>\n"
        "  <language>en</language>\n"
        "  <copyright>© Yoso</copyright>\n"
        f"  <lastBuildDate>{format_datetime(now)}</lastBuildDate>\n"
        + "\n".join(out)
        + "\n</channel>\n</rss>\n"
    )
    (HERE / "feed.xml").write_text(feed, encoding="utf-8")
    print(f"feed.xml: {len(items)} texts, {sum(1 for n, *_ in items if f'river-t{n}' not in dates)} new")


if __name__ == "__main__":
    main()
