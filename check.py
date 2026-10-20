#!/usr/bin/env python3
"""Safety check for a Yoso microsite. Run before publishing:

    python3 check.py

It exits with an error, and the site is not published, if any page:
  - has broken HTML (a tag left open or closed in the wrong order);
  - links to a file or image in this site that does not exist;
  - has a script with a syntax error (needs Node; skipped with a warning if Node is missing);
  - is missing the footer link to the hub, or the mailing-list form with a tick-box for
    every newsletter (this site's own one ticked) and the script that shows them;
  - does not show this site's beta number (from VERSION) in its footer;
and if feed.xml (when there is one), robots.txt, CNAME or VERSION is missing or broken.

To publish an update, use release.py: it moves the beta number up, runs this check, then pushes.

The same file is used on every site; only the two settings below differ.
GitHub runs it on every push (see .github/workflows/publish.yml).
"""
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

# ---- settings for this site ----
SITE_TAG = "river"     # Buttondown tag this site's sign-up form must carry
IS_HUB = False            # the hub itself needs no link back to the hub
IGNORE = ()              # folders of old pages the check leaves alone, e.g. ("archive",)
# ---------------------------------

ROOT = Path(__file__).resolve().parent
LIST_ACTION = "https://buttondown.com/api/emails/embed-subscribe/yoso"
HUB = "https://hub.yoso.one"
# The newsletters readers can choose; each is a Buttondown tag. Same on every site.
NEWSLETTERS = ("one", "yosokuro", "shinsei", "river", "on")
CHOICE_SCRIPT = "assets/list-choice.js"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
# Elements the HTML standard lets you leave unclosed
OPTIONAL_END = {"p", "li", "dt", "dd", "option", "tr", "td", "th", "thead", "tbody",
                "tfoot", "colgroup", "rp", "rt", "optgroup", "html", "head", "body"}
SKIP_DIRS = {".git", ".github", "node_modules"} | set(IGNORE)

problems = []
warnings = []
VERSION = None   # the beta number, read from the VERSION file


def problem(where, what):
    problems.append(f"{where}: {what}")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.refs = []          # (line, url)
        self.scripts = []       # (line, code)
        self._script = None
        self.forms = []         # {"action": ..., "boxes": {tag: ticked}}
        self._form = None
        self.hub_link = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        for key in ("href", "src"):
            if a.get(key):
                self.refs.append((line, a[key]))
        if tag == "a" and (a.get("href") or "").rstrip("/") == HUB:
            self.hub_link = True
        if tag == "form":
            self._form = {"action": a.get("action", ""), "boxes": {}}
            self.forms.append(self._form)
        if tag == "input" and self._form is not None and a.get("name") == "tag":
            if a.get("type") == "checkbox":
                self._form["boxes"][a.get("value")] = "checked" in a
        if tag == "script" and not a.get("src") and a.get("type", "text/javascript") in (
                "text/javascript", "module", "application/javascript"):
            self._script = [line, ""]
        if tag not in VOID:
            self.stack.append((tag, line))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag in VOID:
            return
        if tag == "form":
            self._form = None
        if tag == "script" and self._script is not None:
            self.scripts.append(tuple(self._script))
            self._script = None
        if not any(t == tag for t, _ in self.stack):
            self.errors.append(f"line {line}: </{tag}> has no matching <{tag}>")
            return
        while self.stack and self.stack[-1][0] != tag:
            t, l = self.stack.pop()
            if t not in OPTIONAL_END:
                self.errors.append(f"line {l}: <{t}> is never closed (found </{tag}> on line {line})")
        self.stack.pop()

    def handle_data(self, data):
        if self._script is not None:
            self._script[1] += data


def local_target(page, url):
    """Return the file a relative link points to, or None for outside links."""
    u = urlparse(url)
    if u.scheme or url.startswith(("//", "#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    path = unquote(u.path)
    if not path:
        return None
    base = ROOT if path.startswith("/") else page.parent
    target = (base / path.lstrip("/")).resolve()
    if target.is_dir():
        target = target / "index.html"
    return target


def node_check(where, code=None, path=None):
    node = shutil.which("node")
    if not node:
        if "node" not in warnings:
            warnings.append("node")
        return
    if path is None:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
            path = f.name
    r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        msg = (r.stderr.strip().splitlines() or ["syntax error"])
        detail = next((l for l in msg if "Error" in l), msg[-1])
        problem(where, f"script error: {detail}")


def check_page(page):
    name = page.relative_to(ROOT).as_posix()
    p = Page()
    try:
        text = page.read_text(encoding="utf-8")
        p.feed(text)
        p.close()
    except Exception as e:  # noqa: BLE001
        problem(name, f"could not be read: {e}")
        return
    for e in p.errors:
        problem(name, e)
    for t, l in p.stack:
        if t not in OPTIONAL_END:
            problem(name, f"line {l}: <{t}> is never closed")
    for line, url in p.refs:
        target = local_target(page, url)
        if target is not None and not target.exists():
            problem(name, f"line {line}: links to {url}, which does not exist")
    for line, code in p.scripts:
        if code.strip():
            node_check(f"{name} (script starting line {line})", code=code)
    if not IS_HUB and not p.hub_link:
        problem(name, f"no link to {HUB} (the footer's 'Yoso' should link there)")
    forms = [f for f in p.forms if f["action"] == LIST_ACTION]
    if not forms:
        problem(name, "no mailing-list form")
    else:
        for f in forms:
            missing = [t for t in NEWSLETTERS if t not in f["boxes"]]
            if missing:
                problem(name, "mailing-list form has no tick-box for " + ", ".join(missing))
            if SITE_TAG in NEWSLETTERS and not f["boxes"].get(SITE_TAG):
                problem(name, f"mailing-list form does not tick this site's newsletter '{SITE_TAG}'")
        if not any(url == CHOICE_SCRIPT for _, url in p.refs):
            problem(name, f"mailing-list form needs <script src=\"{CHOICE_SCRIPT}\" defer></script>")
    if VERSION and f'<span class="version" data-version>Beta {VERSION}</span>' not in text:
        problem(name, f"footer does not show Beta {VERSION} (release.py sets it)")


def read_version():
    f = ROOT / "VERSION"
    if not f.exists():
        problem("VERSION", "is missing (it holds the beta number shown in every footer)")
        return None
    v = f.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+", v):
        problem("VERSION", f"should hold a number like 0.4, not '{v}'")
        return None
    return v


def main():
    global VERSION
    VERSION = read_version()
    pages = sorted(p for p in ROOT.rglob("*.html") if not SKIP_DIRS & set(p.relative_to(ROOT).parts))
    if not (ROOT / "index.html").exists():
        problem("site", "index.html is missing")
    for page in pages:
        check_page(page)
    for js in sorted(p for p in ROOT.rglob("*.js") if not SKIP_DIRS & set(p.relative_to(ROOT).parts)):
        node_check(js.relative_to(ROOT).as_posix(), path=js)
    feed = ROOT / "feed.xml"
    if feed.exists():
        try:
            items = ET.parse(feed).getroot().findall("./channel/item")
            if not items:
                problem("feed.xml", "has no items")
        except ET.ParseError as e:
            problem("feed.xml", f"is not valid XML: {e}")
    robots = ROOT / "robots.txt"
    if not robots.exists():
        problem("robots.txt", "is missing")
    elif not re.search(r"User-agent:\s*GPTBot[\s\S]*?Disallow:\s*/\s", robots.read_text(encoding="utf-8")):
        problem("robots.txt", "does not block AI training crawlers (see the shared site rules)")
    if not (ROOT / "CNAME").exists():
        problem("CNAME", "is missing, so the custom domain would stop working")

    if "node" in warnings:
        print("Note: Node is not installed here, so scripts were not checked.")
    if problems:
        print(f"{len(problems)} problem(s) found. Fix these before publishing:\n")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print(f"All good: {len(pages)} page(s) checked.")


if __name__ == "__main__":
    main()
