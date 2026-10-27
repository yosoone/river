#!/usr/bin/env python3
"""Compile River 川 from the Scrivener drafts (River 川/Desk/Draft) into an
A5 PDF and an EPUB, following the book structure kept in Scrivener:

    _ Front Matters   epigraph, copyright, Thank you Japan, half title,
                      blank, dedication, blank, Thank You, golden mark
    _collection       _Best of + _refine, in Scrivener order
    _Back Matters     Thank you for reading, Donate, The End
    + author jacket   (07 Book Design)

Rules (from the Draft instruction notes):
  * files are ordered by their leading number; a title starting with '_'
    is a folder, and every file after it belongs to it until the next '_'
  * each text is its first version, up to the first '— Yoso'
  * '_Seeds' and '_Rework' never go in the book
  * 'Thank you for always being by my side' is in the front matter only
  * case is left exactly as written

    python3 book_drafts.py DRAFT_DIR --version 0.34 [--date 2026-10-22] [--out DIR]

Reuses the typeface, cover and page styles of book.py.
"""
import argparse
import re
import uuid
import zipfile
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

import book as B

HERE = Path(__file__).resolve().parent
SUBTITLE = "Awakening Mind"
PHOTO = HERE / "about.jpg"

COLLECTION = {"collection", "best of", "refine"}
FRONT = {"front matters"}
BACK = {"back matters"}
NEVER = {"seeds", "rework"}
FRONT_ONLY = {"thank you for always being by my side"}
FRONT_ONLY_IDS = {64}   # in the front matter of the book; on the site only

AUTHOR_NOTE = (
    "Yoso is a tattoo artist and multimedia practitioner living in Miyazaki, Japan. "
    "His work moves between tattooing, art installation, writing and meditation, "
    "rooted in Buddhist and Shinto practice."
)


# ---------------------------------------------------------------- source

def clean_title(stem):
    stem = stem.rstrip(".")          # Scrivener now exports "Title [id]..md"
    t = re.sub(r"^\d+\s+", "", stem)
    t = re.sub(r"\s*\[\d+\]$", "", t)
    t = re.sub(r"\s+_new$", "", t)
    return t.strip()


def undouble(raw):
    """Scrivener's newer export puts a blank line after every line. When no
    two text lines sit next to each other, the blank lines are just line
    breaks, so they are collapsed."""
    lines = raw.split("\n")
    adjacent = any(a.strip() and b.strip() for a, b in zip(lines, lines[1:]))
    return raw if adjacent else re.sub(r"\n[ \t]*\n", "\n", raw)


def first_version(raw):
    raw = undouble(raw.replace("\u2028", "\n").replace("\r\n", "\n"))
    lines = []
    for l in raw.split("\n"):
        if l.strip().startswith("— Yoso") or l.strip().startswith("― Yoso"):
            return "\n".join(x.rstrip() for x in lines).strip(), True
        lines.append(l)
    return "\n".join(x.rstrip() for x in lines).strip(), False


def read_drafts(folder):
    files = []
    for p in Path(folder).glob("*.md"):
        m = re.match(r"^(\d+)\s", p.name)
        if m:
            files.append((int(m.group(1)), p))
    files.sort()
    section, out = None, []
    for n, p in files:
        title = clean_title(p.stem)
        if title.startswith("_"):
            section = title.lstrip("_ ").strip().lower()
            continue
        out.append({"n": n, "title": title, "section": section,
                    "path": p, "raw": p.read_text(encoding="utf-8")})
    return out


def scriv_id(e):
    m = re.search(r"\[(\d+)\]\.*$", e["path"].stem)
    return int(m.group(1)) if m else None


def pick(entries, key):
    for e in entries:
        if e["title"].lower() == key.lower():
            return e
    raise SystemExit(f"Missing draft: {key}")


def collection(entries):
    texts = []
    for e in entries:
        if e["section"] in NEVER or e["section"] not in COLLECTION:
            continue
        if e["title"].lower() in FRONT_ONLY or scriv_id(e) in FRONT_ONLY_IDS:
            continue
        v, signed = first_version(e["raw"])
        if v:
            texts.append((e["n"], TITLE_FIX.get(e["title"], e["title"]), v))
    return texts


def copyright_lines(raw, version, d):
    """The copyright draft, with today's beta number and date put in."""
    stamp = f"Beta {version} · {B.long_date(d)}"
    out = []
    for l in raw.replace(" ", "\n").split("\n"):
        l = l.strip()
        if not l:
            continue
        l = re.sub(r"Beta\s+[\d.]+\s*·\s*\d{1,2}\s+\w+\s+\d{4}", stamp, l)
        l = re.sub(r"©\s*\d{4}", f"© {d.year}", l)
        out.append(l)
    return out


# ---------------------------------------------------------------- html parts
# Front and back matter follow the notes in Scrivener, in order. Each note
# becomes one page. Markers written in a note are replaced:
#   'insert photograph'                 -> the author photograph
#   'Claude Insert Signature with Seal' -> the signature with the red seal
#   'Golden mark'                       -> the golden mark
# A note titled 'Insert' is a blank page (kept in the EPUB too).
# 'Copyright' fills in 'Beta version', 'Date' and 'year'.

def paras(text):
    return "".join('<p class="stanza">' + "<br/>".join(escape(x) for x in st.split("\n")) + "</p>"
                   for st in re.split(r"\n\s*\n", text.strip()))


MARKERS = [
    (re.compile(r"^[‘'\"]?\s*insert photograph\s*[’'\"]?$", re.I), "photo"),
    (re.compile(r"^[‘'\"]?\s*Claude Insert Signature with Seal[^’'\"]*[’'\"]?$", re.I), "seal"),
    (re.compile(r"^[‘'\"]?\s*Golden mark\s*[’'\"]?$", re.I), "gold"),
]
SITE_RE = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?$", re.I)


INLINE_SITE = re.compile(r"(?<![\w@/.])((?:https?://)?(?:[a-z0-9-]+\.)+(?:one|com|org|net|jp|io)(?:/[^\s<]*)?)(?<![.,;:])", re.I)


def linkify(line):
    """Escape a line and turn any web address in it into a link."""
    out, last = [], 0
    for m in INLINE_SITE.finditer(line):
        u = m.group(1)
        out.append(escape(line[last:m.start(1)]))
        out.append(f'<a href="{escape(u if u.startswith("http") else "https://" + u)}">{escape(u.split("//")[-1])}</a>')
        last = m.end(1)
    out.append(escape(line[last:]))
    return "".join(out)


def blank_page():
    # A non-breaking space keeps e-readers from skipping an empty page.
    return ("Blank", '<div class="blank">&#160;</div>', "blank")


def marker_html(line, img):
    for rx, kind in MARKERS:
        if rx.match(line):
            if kind == "photo":
                return f'<p class="pic"><img class="portrait" src="{img("about.jpg")}" alt="Yoso"/></p>'
            if kind == "seal":
                return f'<p class="sign seal"><img src="{img("signature.png")}" alt="Signature and seal of Yoso"/></p>'
            return f'<p class="pic"><img class="gold" src="{img("yoso-mark.png")}" alt="Yoso"/></p>'
    return None


def block_html(block, img):
    """One paragraph of a note. Marker lines become images, web addresses links."""
    out, run = [], []
    def flush():
        if run:
            cls = ' class="stanza name"' if run == ["YOSO"] else ' class="stanza"'
            out.append(f"<p{cls}>" + "<br/>".join(run) + "</p>"); run.clear()
    for l in (x.strip() for x in block.split("\n") if x.strip()):
        m = marker_html(l, img)
        if m:
            flush(); out.append(m); continue
        if SITE_RE.match(l):
            url = l if l.startswith("http") else "https://" + l
            run.append(f'<a href="{escape(url)}">{escape(l.split("//")[-1])}</a>')
        else:
            run.append(linkify(l))
    flush()
    return "".join(out)


def matter_page(e, version, d, img):
    title, raw = e["title"], e["raw"].replace("\u2028", "\n").replace("\r\n", "\n").strip()
    if title.lower() == "insert":
        return blank_page()
    if title.lower() == "copyright":
        stamp = {"Beta version": f"Beta {version}", "Date": B.long_date(d), "year": str(d.year)}
        raw = re.sub(r"[‘']\s*(Beta version|Date|year)\s*[’']", lambda m: stamp[m.group(1)], raw)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        body = f'<p class="name">{escape(lines[0])}</p>' + "".join(
            (f'<p><a href="https://{escape(l)}">{escape(l)}</a></p>' if SITE_RE.match(l) else f'<p>{linkify(l)}</p>') for l in lines[1:])
        return (title, f'<div class="colophon">{body}</div>', "colo")
    if title.lower().startswith("half title"):
        return (title, f'<p class="half">{escape(raw or B.KANJI)}</p>', "centre")
    signed = bool(re.search(r"^\s*[—―]\s*Yoso\s*$", raw, re.M))
    if signed:      # texts in the front matter: first version, signed in type
        v, _ = first_version(raw)
        return (title, f'<div class="verse quiet">{paras(v)}</div><p class="byline">Yoso</p>', "centre")
    blocks = [b for b in re.split(r"\n\s*\n", raw) if b.strip()]
    if len(blocks) == 1 and "\n" not in blocks[0].strip() and len(blocks[0]) < 40 and not marker_html(blocks[0].strip(), img):
        return (title, f'<p class="lone">{escape(blocks[0].strip())}</p>', "centre")
    cls = "centre letter" + (" author" if any(MARKERS[0][0].match(l.strip()) for b in blocks for l in b.split("\n")) else "")
    return (title, '<div class="letter">' + "".join(block_html(b, img) for b in blocks) + "</div>", cls)


def matter(entries, section, version, d, img):
    return [matter_page(e, version, d, img) for e in entries if e["section"] == section]


def collection_pages(entries):
    """Texts and Insert pages of the collection, in Scrivener order."""
    out = []
    for e in entries:
        if e["section"] in NEVER or e["section"] not in COLLECTION:
            continue
        if e["title"].lower() == "insert":
            out.append(("blank", e["n"], None, None)); continue
        if e["title"].lower() in FRONT_ONLY or scriv_id(e) in FRONT_ONLY_IDS:
            continue
        v, _ = first_version(e["raw"])
        if v:
            out.append(("text", e["n"], TITLE_FIX.get(e["title"], e["title"]), v))
    return out


TITLE_FIX = {}


def piece(n, t, v, img):
    # Title above, the signature in type below (no seal image).
    return (f'<h3>{escape(t)}</h3><div class="verse {B.size_class(v)}">{B.verse_html(v)}</div>'
            '<p class="byline">Yoso</p>')


# ---------------------------------------------------------------- PDF

COVER_JPG = None   # set from --cover
COVER_PNG = None

PDF_EXTRA = """
.cover.designed { text-align: center; }
.cover.designed img { height: 210mm; width: auto; display: block; margin: 0 auto; }
.page { height: 164mm; display: flex; flex-direction: column; text-align: center; }
.centre { justify-content: center; }
.front { page: front; }
.colo { justify-content: flex-end; text-align: left; font-size: 8.5pt; line-height: 1.8; color: #3A3A36; }
.colo p { margin: 0 0 3mm; } .colo .name { font-size: 11pt; color: #1C1C1A; }
a { color: inherit; text-decoration: none; }
.epi .verse { font-size: 12pt; line-height: 1.85; color: #3A3A36; }
.ptitle { font-size: 13pt; margin: 0 0 9mm; }
.verse.small { font-size: 11pt; line-height: 1.8; color: #3A3A36; }
.verse.quiet { font-size: 12pt; line-height: 1.85; color: #3A3A36; }
.half { font-size: 48pt; margin: 0; color: #5A5A55; }
.ded .to { font-size: 10pt; letter-spacing: .14em; color: #5A5A55; margin: 0; }
.gold { width: 16mm; height: 16mm; margin: 0 auto 7mm; }
.url { font-size: 9pt; letter-spacing: .1em; color: #5A5A55; margin: 4mm 0 0; }
.letter { font-size: 10.5pt; line-height: 1.85; color: #3A3A36; }
.letter .stanza { margin: 0 0 1.1em; }
.seal img { height: 20mm; }
.stanza { margin: 0; }
.theend { font-size: 13pt; letter-spacing: .08em; color: #3A3A36; margin: 0; }
.author .portrait { width: 52mm; height: auto; margin: 0 auto 8mm; }
.aname { font-size: 10pt; letter-spacing: .3em; text-transform: uppercase; margin: 0 0 4mm; }
.anote { font-size: 9.5pt; line-height: 1.8; color: #3A3A36; margin: 0 8mm; }
.blank { height: 1px; }
.lone { font-size: 13pt; letter-spacing: .04em; color: #3A3A36; margin: 0; }
.byline { margin: 8mm 0 0; font-size: 9pt; letter-spacing: .12em; color: #5A5A55; }
.letter .pic { margin: 0 0 6mm; }
.letter .portrait { width: 34mm; height: auto; }
.letter .gold { width: 14mm; height: 14mm; margin: 0 auto; }
.letter .name { font-size: 9.5pt; letter-spacing: .3em; }
.letter .seal { margin: 2mm 0 5mm; line-height: 0; }
.letter .seal img { height: 18mm; }
.author.letter { font-size: 8.8pt; line-height: 1.6; }
.author .pic { margin: 0 0 4mm; }
.author .seal img { height: 14mm; }
.author .seal { margin: 1mm 0 3mm; }
.author .stanza { margin: 0 0 .7em; }
"""


def build_pdf(entries, texts, version, d, path):
    from weasyprint import HTML
    img = lambda n: str(HERE / ("images/" + n if n != "about.jpg" else n))
    if COVER_PNG:
        import base64
        uri = "data:image/png;base64," + base64.b64encode(COVER_PNG).decode()
        parts = [f'<section class="cover designed"><img src="{uri}" alt="{B.TITLE} {B.KANJI}"/></section>']
    else:
        parts = ['<section class="cover">'
             f'<div class="mark"><img src="images/yoso-mark.png" alt="Yoso"/></div>'
             f'<div class="title"><h1>{B.TITLE}<span>{B.KANJI}</span></h1><p class="sub">{B.SUBTITLE}</p></div>'
             f'<p class="author">{B.AUTHOR}</p>'
             f'<p class="edition">Beta {version} · {B.long_date(d)}</p></section>']
    pages = matter(entries, "front matters", version, d, img)
    for t, body, cls in pages:
        parts.append(f'<section class="front page {cls}">{body}</section>')
    for kind, n, t, v in collection_pages(entries):
        parts.append('<section class="front page blank"></section>' if kind == "blank" else
                     f'<section class="piece" id="t{n}">{piece(n, t, v, img)}</section>')
    for t, body, cls in matter(entries, "back matters", version, d, img):
        parts.append(f'<section class="front page {cls}">{body}</section>')
    doc = (f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"/>'
           f'<title>{B.TITLE} {B.KANJI} — Beta {version}</title><meta name="author" content="{B.AUTHOR}"/>'
           f'<style>{B.PDF_CSS}{PDF_EXTRA}</style></head><body>{"".join(parts)}</body></html>')
    HTML(string=doc, base_url=str(HERE)).write_pdf(path)


# ---------------------------------------------------------------- EPUB

EPUB_EXTRA = """
a { color: inherit; text-decoration: none; }
.page, .page p, .page div, .page h2 { text-align: center !important; text-indent: 0 !important; }
.page { margin-top: 25%; }
@supports (display: flex) {
  .page.centre { margin-top: 0; min-height: 88vh; display: flex; flex-direction: column; justify-content: center; } }
.colo, .colo p { text-align: left !important; }
.colo { margin-top: 40%; font-size: 0.8em; line-height: 1.8; }
.colo p { margin: 0 0 1em; } .colo .name { font-size: 1.2em; }
.epi .verse, .verse.quiet { font-size: 1.05em; line-height: 1.85; }
.ptitle { font-size: 1.15em; margin: 0 0 1.5em; }
.verse.small { font-size: 0.98em; line-height: 1.8; }
.half { font-size: 3.2em; margin: 0; opacity: 0.75; }
.ded .to { font-size: 0.9em; letter-spacing: 0.14em; opacity: 0.8; margin: 0; }
.gold { width: 4em; height: 4em; margin: 0 auto 1.5em; }
.url { font-size: 0.8em; letter-spacing: 0.1em; opacity: 0.8; margin: 1em 0 0; }
.letter .stanza { margin: 0 0 1.1em; }
.seal img { height: 5em; width: auto; }
.theend { font-size: 1.15em; letter-spacing: 0.08em; margin: 0; }
.author .portrait { width: 55%; max-width: 16em; height: auto; margin: 0 auto 1.5em; }
.aname { font-size: 0.85em; letter-spacing: 0.3em; text-transform: uppercase; margin: 0 0 1em; }
.anote { font-size: 0.9em; line-height: 1.8; margin: 0 6%; }
.blank { min-height: 80vh; }
.lone { font-size: 1.15em; letter-spacing: 0.04em; margin: 0; }
.byline { margin: 2em 0 0; font-size: 0.8em; letter-spacing: 0.12em; opacity: 0.8; }
.piece p.byline { text-align: center !important; text-indent: 0 !important; margin: 2.2em 0 0; }
.letter .pic { margin: 0 0 1.4em; }
.letter .portrait { width: 50%; max-width: 14em; height: auto; }
.letter .gold { width: 3.5em; height: 3.5em; margin: 0 auto; }
.letter .name { font-size: 0.85em; letter-spacing: 0.3em; }
.letter .seal { margin: 0.4em 0 1.2em; line-height: 0; }
.letter .stanza { margin: 0 0 1em; }
"""


def build_epub(entries, texts, version, d, path):
    img = lambda n: n
    book_id = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://{B.SITE}/book/beta-{version}-{d}"))
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = [("cover.xhtml", "Cover", B.xhtml("Cover", f'<img src="cover.jpg" alt="{B.TITLE} {B.KANJI}, '
                                                    f'{SUBTITLE} by {B.AUTHOR}"/>', "cover"), False)]
    start = None
    for i, (t, body, cls) in enumerate(matter(entries, "front matters", version, d, img)):
        f = f"front{i + 1:02d}.xhtml"
        et = ' epub:type="copyright-page"' if t.lower() == "copyright" else ' epub:type="halftitlepage"' if t.lower().startswith("half title") else ""
        if t.lower().startswith("half title"):
            start = f
        pages.append((f, t, B.xhtml(t, f'<section class="page {cls}"{et}>{body}</section>'), False))
    first = None
    for kind, n, t, v in collection_pages(entries):
        if kind == "blank":
            f = f"blank{n}.xhtml"
            pages.append((f, "Blank", B.xhtml("Blank page", '<section class="page blank"><div class="blank">&#160;</div></section>'), False))
            continue
        f = f"t{n}.xhtml"
        first = first or f
        pages.append((f, t, B.xhtml(t, f'<section class="piece" epub:type="chapter">{piece(n, t, v, img)}</section>'), True))
    for i, (t, body, cls) in enumerate(matter(entries, "back matters", version, d, img)):
        f = f"back{i + 1:02d}.xhtml"
        pages.append((f, t, B.xhtml(t, f'<section class="page {cls}">{body}</section>'), t.lower() not in ("insert", "blank")))
    start = start or first

    toc = "".join(f'<li><a href="{f}">{escape(t)}</a></li>' for f, t, _, inc in pages if inc)
    nav = B.xhtml("Contents", f'<nav epub:type="toc" id="toc" class="toc"><h2>Contents</h2><ol>{toc}</ol></nav>'
                  '<nav epub:type="landmarks" hidden="hidden"><ol>'
                  '<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>'
                  f'<li><a epub:type="bodymatter" href="{start}">Start</a></li></ol></nav>')
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        '<item id="signature" href="signature.png" media-type="image/png"/>',
        '<item id="mark-image" href="yoso-mark.png" media-type="image/png"/>',
        '<item id="portrait" href="about.jpg" media-type="image/jpeg"/>',
        '<item id="font-r" href="fonts/ShipporiMincho-Regular-Latin.ttf" media-type="font/ttf"/>',
        '<item id="font-b" href="fonts/ShipporiMincho-SemiBold-Latin.ttf" media-type="font/ttf"/>',
    ]
    spine = []
    for f, _, _, _ in pages:
        pid = f.rsplit(".", 1)[0]
        manifest.append(f'<item id="{pid}" href="{f}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{pid}"/>')
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en-GB">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
        f"<dc:title>{B.TITLE} {B.KANJI}: {SUBTITLE}</dc:title>\n<dc:creator>{B.AUTHOR}</dc:creator>\n"
        f"<dc:language>en-GB</dc:language>\n<dc:date>{d.isoformat()}</dc:date>\n"
        f"<dc:publisher>{B.AUTHOR}</dc:publisher>\n"
        f"<dc:rights>© {d.year} {B.AUTHOR}. All rights reserved.</dc:rights>\n"
        f"<dc:description>{SUBTITLE}, short texts by {B.AUTHOR}. Beta {version}, {B.long_date(d)}.</dc:description>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n<meta name="cover" content="cover-image"/>\n'
        "</metadata>\n<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
        "<spine>\n" + "\n".join(spine) + "\n</spine>\n</package>\n")
    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 "</rootfiles></container>\n")
    D = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=D)
        z.writestr("META-INF/com.apple.ibooks.display-options.xml",
                   '<?xml version="1.0" encoding="UTF-8"?>\n<display_options><platform name="*">'
                   '<option name="specified-fonts">true</option></platform></display_options>\n', compress_type=D)
        z.writestr("OEBPS/content.opf", opf, compress_type=D)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=D)
        z.writestr("OEBPS/style.css", B.EPUB_CSS + EPUB_EXTRA, compress_type=D)
        z.writestr("OEBPS/cover.jpg", COVER_JPG or B.make_cover(version, d))
        z.write(B.SIGNATURE, "OEBPS/signature.png")
        z.write(B.MARK, "OEBPS/yoso-mark.png")
        z.write(PHOTO, "OEBPS/about.jpg")
        for name in ("ShipporiMincho-Regular-Latin.ttf", "ShipporiMincho-SemiBold-Latin.ttf"):
            z.write(B.FONTS / name, f"OEBPS/fonts/{name}", compress_type=D)
        for f, _, x, _ in pages:
            z.writestr(f"OEBPS/{f}", x, compress_type=D)


# ---------------------------------------------------------------- designed cover

def render_svg(svg, w, h):
    """PNG of an SVG at w x h, drawn by Chromium through Playwright (Node)."""
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as t:
        src, out = Path(t) / "cover.svg", Path(t) / "cover.png"
        src.write_text(svg, encoding="utf-8")
        js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch("
              "{executablePath:process.env.CHROMIUM||undefined});const p=await b.newPage({viewport:{width:%d,height:%d}});"
              "await p.goto('file://'+process.argv[1]);await p.waitForTimeout(800);"
              "await p.screenshot({path:process.argv[2]});await b.close()})();" % (w, h))
        subprocess.run(["node", "-e", js, str(src), str(out)], check=True,
                       env={**__import__("os").environ, "CHROMIUM": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                            "NODE_PATH": "/home/claude/node_modules"})
        return out.read_bytes()


def cover_from_svg(svg_path, version, d):
    """Use Yoso's Illustrator cover (1600 x 2560 SVG). The Edition line is
    rewritten with this edition's beta number and date and kept centred on the
    same point. Returns (jpeg bytes 1600x2560, png bytes 2400x3840)."""
    from io import BytesIO
    from PIL import Image
    from fontTools.ttLib import TTFont
    svg = Path(svg_path).read_text(encoding="utf-8")
    # Illustrator names the font by its PostScript name; renderers want the family name.
    svg = re.sub(r"font-family:\s*'?ShipporiMincho-[A-Za-z]+'?", "font-family:'Shippori Mincho'", svg)
    m = re.search(r'(<text id="Edition" transform="matrix\(1 0 0 1 )([\d.]+)( [\d.]+\)" class="([^"]+)">)([^<]*)(</text>)', svg)
    if m:
        classes = m.group(4).split()
        style = dict(re.findall(r"\.(st\d+)\{([^}]*)\}", svg))
        css = ";".join(style.get(c, "") for c in classes)
        size = float(re.search(r"font-size:([\d.]+)px", css).group(1))
        sp = float((re.search(r"letter-spacing:([\d.]+)", css) or [0, 0])[1])
        ft = TTFont(str(B.FONTS / "ShipporiMincho-Regular-Latin.ttf"))
        cm, hm, upm = ft.getBestCmap(), ft["hmtx"], ft["head"].unitsPerEm
        wid = lambda t: sum(hm[cm[ord(c)]][0] * size / upm + sp for c in t)
        old, new = m.group(5), f"Beta {version} · {B.long_date(d)}"
        centre = float(m.group(2)) + wid(old) / 2
        svg = svg.replace(m.group(0), f"{m.group(1)}{centre - wid(new) / 2:.4f}{m.group(3)}{escape(new)}{m.group(6)}")
    # Illustrator writes letter-spacing without units, which browsers ignore.
    svg = re.sub(r"letter-spacing:\s*([\d.]+)\s*;", r"letter-spacing:\1px;", svg)
    big = render_svg(svg, 2400, 3840)
    im = Image.open(BytesIO(big)).convert("RGB")
    jpg = BytesIO()
    im.resize((1600, 2560), Image.LANCZOS).save(jpg, "JPEG", quality=92)
    png = BytesIO()
    im.save(png, "PNG")
    return jpg.getvalue(), png.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drafts")
    ap.add_argument("--cover", help="Illustrator cover SVG (1600 x 2560) to use instead of the drawn cover")
    ap.add_argument("--version", required=True)
    ap.add_argument("--date")
    ap.add_argument("--out", default=str(HERE / "editions"))
    a = ap.parse_args()
    d = date.fromisoformat(a.date) if a.date else datetime.now(B.JST).date()
    entries = read_drafts(a.drafts)
    texts = collection(entries)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"river-beta-{a.version}-{d.isoformat()}"
    global COVER_JPG, COVER_PNG
    if a.cover:
        COVER_JPG, COVER_PNG = cover_from_svg(a.cover, a.version, d)
    build_epub(entries, texts, a.version, d, out / f"{stem}.epub")
    build_pdf(entries, texts, a.version, d, out / f"{stem}.pdf")
    if a.cover:
        (out / f"{stem}-cover.jpg").write_bytes(COVER_JPG)
    print(f"River 川 · Beta {a.version} · {B.long_date(d)} · {len(texts)} texts")
    for n, t, v in texts:
        print(f"  {n:>3} {t}")


if __name__ == "__main__":
    main()
