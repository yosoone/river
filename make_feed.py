#!/usr/bin/env python3
"""Build feed.xml (RSS) for River from the TEXTS list in index.html.

Run it from this folder after adding or changing a text, then commit both files:

    python3 make_feed.py

Each text becomes one feed item linking to its page (https://river.yoso.one/#tN), in English,
newest (highest number) first. The texts have no dates of their own, so every item carries the
date the feed was built, a second apart, which keeps feed readers in the right order.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

SITE = "https://river.yoso.one/"
HERE = Path(__file__).resolve().parent

html = (HERE / "index.html").read_text(encoding="utf-8")
block = re.search(r"const TEXTS = \[(.*?)\n\];", html, re.S).group(1)
STR = r'"((?:[^"\\]|\\.)*)"'
texts = []
for m in re.finditer(r"\{n:(\d+),\s*t:" + STR + r",\s*v:" + STR, block):
    texts.append({"n": int(m.group(1)), "t": json.loads('"' + m.group(2) + '"'), "v": json.loads('"' + m.group(3) + '"')})
if not texts:
    raise SystemExit("No texts found in index.html; has the TEXTS list changed shape?")

jst = timezone(timedelta(hours=9))
built = datetime.now(jst).replace(microsecond=0)


def body(v):
    stanzas = re.split(r"\n\s*\n", v)
    return "".join("<p>" + "<br>".join(escape(l) for l in s.split("\n")) + "</p>" for s in stanzas) + "<p>– Yoso</p>"


items = []
for i, x in enumerate(sorted(texts, key=lambda x: -x["n"])):
    items.append(
        "  <item>\n"
        f"    <title>{escape(x['t'])}</title>\n"
        f"    <link>{SITE}#t{x['n']}</link>\n"
        f"    <guid isPermaLink=\"false\">river-t{x['n']}</guid>\n"
        f"    <pubDate>{format_datetime(built - timedelta(seconds=i))}</pubDate>\n"
        f"    <description>{escape(body(x['v']))}</description>\n"
        "  </item>"
    )

feed = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
    "<channel>\n"
    "  <title>River 川</title>\n"
    f"  <link>{SITE}</link>\n"
    f'  <atom:link href="{SITE}feed.xml" rel="self" type="application/rss+xml"/>\n'
    "  <description>Short texts by Yoso, Miyazaki: on breath, love, spring and surrendering to the flow.</description>\n"
    "  <language>en</language>\n"
    "  <copyright>© Yoso</copyright>\n"
    f"  <lastBuildDate>{format_datetime(built)}</lastBuildDate>\n"
    + "\n".join(items)
    + "\n</channel>\n</rss>\n"
)
(HERE / "feed.xml").write_text(feed, encoding="utf-8")
print(f"feed.xml: {len(texts)} texts")
