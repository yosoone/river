#!/usr/bin/env python3
"""Compile River 川 into a dated, beta-numbered book: an A5 PDF and an EPUB.

Run from the river folder whenever there has been enough change for a new
edition:

    python3 book.py                    # today's date, beta number from VERSION
    python3 book.py --date 2026-11-03  # a different date on the title page

The texts come straight from the TEXTS list in index.html (English only), the
about text from the site's English About page, and the beta number from
VERSION, so the book always matches the published site. Files land in
editions/ as river-beta-<n>-<yyyy-mm-dd>.pdf and .epub. editions/ is not
committed: the books are not public until they are offered on the site.

Needs WeasyPrint for the PDF (pip install weasyprint) and Pillow for the EPUB
cover. The typeface is Shippori Mincho (SIL Open Font License), the site's
own display face, in book/fonts.
"""
import argparse
import json
import re
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "book" / "fonts"
MARK = HERE / "images" / "yoso-mark.png"
OUT = HERE / "editions"
PUBLIC = HERE / "books"            # the edition offered on the home page
BOOK_JS = HERE / "assets" / "book.js"
JST = timezone(timedelta(hours=9))

TITLE = "River"
KANJI = "川"
AUTHOR = "Yoso"
SUBTITLE = "Short texts"
SIGN = "— Yoso"
SITE = "river.yoso.one"
# The book opens with this text as its dedication (it is left out of the
# sequence of texts). Set DEDICATION_TEXT = None for no dedication page.
DEDICATION_TEXT = 38          # 'A quiet river'
DEDICATION_TO = "For Yuko"
HUB = "hub.yoso.one"

STRING = r'"((?:[^"\\]|\\.)*)"'
ITEM = re.compile(r"\{n:(\d+),\s*t:" + STRING + r",\s*v:" + STRING)


# ---------------------------------------------------------------- source

def js_string(s):
    return json.loads('"' + s + '"')


def read_site():
    html = (HERE / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const TEXTS = ["):]
    block = block[: block.index("\n];")]
    texts = [(int(n), js_string(t), js_string(v)) for n, t, v in ITEM.findall(block)]
    if not texts:
        raise SystemExit("No texts found in index.html")
    m = re.search(r'aboutText:' + STRING, html)
    about = js_string(m.group(1)) if m else ""
    version = (HERE / "VERSION").read_text(encoding="utf-8").strip()
    return texts, about, version


def long_date(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def stanzas(v):
    return [s.split("\n") for s in re.split(r"\n\s*\n", v.strip())]


def verse_html(v):
    out = []
    for st in stanzas(v):
        out.append('<p class="stanza">' + "<br/>".join(escape(l) for l in st) + "</p>")
    return "".join(out)


def size_class(v):
    lines = v.count("\n") + 1
    longest = max(len(l) for l in v.split("\n"))
    if lines > 8 or longest > 60:
        return "longer"
    if lines > 5 or longest > 42:
        return "long"
    return ""


# ---------------------------------------------------------------- PDF

PDF_CSS = """
@font-face { font-family: 'Shippori Mincho'; font-weight: 400;
  src: url('book/fonts/ShipporiMincho-Regular-Latin.ttf'); }
@font-face { font-family: 'Shippori Mincho'; font-weight: 600;
  src: url('book/fonts/ShipporiMincho-SemiBold-Latin.ttf'); }
@page { size: A5; margin: 22mm 20mm 24mm;
  @bottom-center { content: counter(page); font: 8pt 'Shippori Mincho'; color: #8A8984; } }
@page cover { margin: 0; background: #EEEDE8; @bottom-center { content: none; } }
@page front { @bottom-center { content: none; } }
html { font-family: 'Shippori Mincho', serif; color: #1C1C1A; font-size: 10.5pt; line-height: 1.7;
  hyphens: none; }
body { margin: 0; }
section { page-break-after: always; }
section:last-child { page-break-after: auto; }

.cover { page: cover; height: 210mm; position: relative; text-align: center; }
.cover .mark { position: absolute; top: 24mm; left: 0; right: 0; }
.cover .mark img { width: 13mm; height: 13mm; }
.cover .title { position: absolute; top: 70mm; left: 0; right: 0; }
.cover h1 { margin: 0; font-weight: 400; font-size: 52pt; letter-spacing: .02em; line-height: 1; }
.cover h1 span { color: #5A5A55; margin-left: .12em; }
.cover .sub { margin: 7mm 0 0; font-size: 11pt; letter-spacing: .12em; color: #3A3A36; }
.cover .author { position: absolute; bottom: 38mm; left: 0; right: 0; margin: 0;
  font-size: 10pt; letter-spacing: .3em; text-transform: uppercase; color: #3A3A36; }
.cover .edition { position: absolute; bottom: 26mm; left: 0; right: 0; margin: 0;
  font-size: 8.5pt; letter-spacing: .12em; color: #5A5A55; }

.front { page: front; }
.colophon { height: 164mm; display: flex; flex-direction: column; justify-content: flex-end;
  font-size: 8.5pt; line-height: 1.8; color: #3A3A36; }
.colophon p { margin: 0 0 3mm; }
.colophon .name { font-size: 11pt; color: #1C1C1A; }

h2 { margin: 0 0 9mm; font-weight: 400; font-size: 15pt; letter-spacing: .02em; }
.about p { margin: 0; font-size: 10.5pt; line-height: 1.95; color: #3A3A36; text-align: left; }

.toc ol { list-style: none; margin: 0; padding: 0; }
.toc li { margin: 0 0 2.2mm; font-size: 10pt; }
.toc a { color: inherit; text-decoration: none; }
.toc a::after { content: leader('. ') target-counter(attr(href), page); color: #8A8984; }

.piece { height: 164mm; display: flex; flex-direction: column; justify-content: center;
  text-align: center; }
.piece h3 { margin: 0 0 10mm; font-weight: 400; font-size: 8pt; letter-spacing: .18em;
  text-transform: uppercase; color: #8A8984; }
.verse { font-size: 15pt; line-height: 1.75; }
.verse.long { font-size: 13pt; }
.verse.longer { font-size: 11.5pt; }
.verse .stanza { margin: 0; }
.verse .stanza + .stanza { margin-top: 1.4em; }
.sign { margin: 11mm 0 0; font-size: 8.5pt; letter-spacing: .12em; color: #5A5A55; }

.dedication { page: front; height: 164mm; display: flex; flex-direction: column;
  justify-content: center; text-align: center; }
.dedication .verse { font-size: 12pt; line-height: 1.85; color: #3A3A36; }
.dedication .to { margin: 10mm 0 0; font-size: 8.5pt; letter-spacing: .14em; color: #5A5A55; }
.end { height: 164mm; display: flex; flex-direction: column; justify-content: center;
  text-align: center; font-size: 9pt; letter-spacing: .1em; color: #5A5A55; }
.end img { width: 9mm; height: 9mm; margin: 0 auto 6mm; }
"""


def colophon_lines(version, d):
    return [
        f'<p class="name">{TITLE} {KANJI}</p>',
        f"<p>{SUBTITLE} by {AUTHOR}<br/>Beta {version} · {long_date(d)}</p>",
        f"<p>© {d.year} {AUTHOR}. All rights reserved.<br/>No part of this book may be reproduced "
        "without the author’s permission, except for short quotations with credit.</p>",
        f"<p>{SITE} · {HUB}</p>",
        "<p>Set in Shippori Mincho.<br/>Miyazaki, Japan.</p>",
    ]


def build_pdf(texts, ded, about, version, d, path):
    from weasyprint import HTML

    parts = [
        '<section class="cover">'
        f'<div class="mark"><img src="images/yoso-mark.png" alt="Yoso"/></div>'
        f'<div class="title"><h1>{TITLE}<span>{KANJI}</span></h1><p class="sub">{SUBTITLE}</p></div>'
        f'<p class="author">{AUTHOR}</p>'
        f'<p class="edition">Beta {version} · {long_date(d)}</p></section>',
        '<section class="front"><div class="colophon">' + "".join(colophon_lines(version, d)) + "</div></section>",
    ]
    if ded:
        parts.append(f'<section class="dedication"><div class="verse">{verse_html(ded)}</div>'
                     f'<p class="to">{escape(DEDICATION_TO)}</p></section>')
    if about:
        parts.append(f'<section class="about"><h2>About River</h2><p>{escape(about)}</p></section>')
    toc = "".join(f'<li><a href="#t{n}">{escape(t)}</a></li>' for n, t, _ in texts)
    parts.append(f'<section class="toc"><h2>Contents</h2><ol>{toc}</ol></section>')
    for n, t, v in texts:
        parts.append(
            f'<section class="piece" id="t{n}"><h3>{escape(t)}</h3>'
            f'<div class="verse {size_class(v)}">{verse_html(v)}</div>'
            f'<p class="sign">{escape(SIGN)}</p></section>'
        )
    parts.append(f'<section class="end"><img src="images/yoso-mark.png" alt=""/>'
                 f'<p>{SITE}</p></section>')
    doc = (f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"/>'
           f'<title>{TITLE} {KANJI} — Beta {version}</title>'
           f'<meta name="author" content="{AUTHOR}"/>'
           f'<meta name="description" content="{SUBTITLE} by {AUTHOR}. Beta {version}, {long_date(d)}."/>'
           f'<style>{PDF_CSS}</style></head><body>{"".join(parts)}</body></html>')
    HTML(string=doc, base_url=str(HERE)).write_pdf(path)


# ---------------------------------------------------------------- EPUB

EPUB_CSS = """
@font-face { font-family: 'Shippori Mincho'; font-weight: normal; src: url(fonts/ShipporiMincho-Regular-Latin.ttf); }
@font-face { font-family: 'Shippori Mincho'; font-weight: bold; src: url(fonts/ShipporiMincho-SemiBold-Latin.ttf); }
body { font-family: 'Shippori Mincho', serif; line-height: 1.7; margin: 0 5%; }
h1, h2, h3 { font-weight: normal; }
.cover { margin: 0; padding: 0; text-align: center; }
.cover img { max-width: 100%; max-height: 100vh; }
.colophon { margin-top: 30%; font-size: 0.8em; line-height: 1.8; }
.colophon p { margin: 0 0 1em; text-indent: 0; }
.colophon .name { font-size: 1.2em; }
h2 { font-size: 1.3em; margin: 2em 0 1.5em; }
.about p { line-height: 1.95; text-indent: 0; }
.toc ol { list-style: none; padding: 0; }
.toc li { margin: 0 0 0.6em; }
.toc a { text-decoration: none; color: inherit; }
/* Readers often force their own alignment on paragraphs, so every part of a
   text page is centred explicitly, not just the section around it. */
.piece, .piece h3, .piece .verse, .piece p.stanza, .piece p.sign {
  text-align: center !important; text-indent: 0 !important; hyphens: none; -webkit-hyphens: none; }
.piece { margin-top: 22%; }
/* Where the reader supports it (Apple Books, most newer apps), centre the
   text on the page vertically too; elsewhere it sits a little below the top. */
@supports (display: flex) {
  .piece { margin-top: 0; min-height: 88vh; display: flex; flex-direction: column; justify-content: center; } }
.piece h3 { font-size: 0.7em; letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.6; margin: 0 0 2.5em; }
.verse { font-size: 1.3em; line-height: 1.75; }
.verse.long { font-size: 1.15em; }
.verse.longer { font-size: 1.02em; }
.stanza { margin: 0; }
.stanza + .stanza { margin-top: 1.4em; }
.dedication, .dedication .verse, .dedication p { text-align: center !important; text-indent: 0 !important; }
.dedication { margin-top: 30%; }
@supports (display: flex) {
  .dedication { margin-top: 0; min-height: 88vh; display: flex; flex-direction: column; justify-content: center; } }
.dedication .verse { font-size: 1.05em; line-height: 1.85; }
.dedication .to { margin: 2.5em 0 0; font-size: 0.75em; letter-spacing: 0.14em; opacity: 0.75; }
.sign { margin: 2.5em 0 0; font-size: 0.75em; letter-spacing: 0.12em; opacity: 0.75; }
"""


def xhtml(title, body, cls=""):
    attr = f' class="{cls}"' if cls else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
        'lang="en-GB" xml:lang="en-GB">\n<head><meta charset="utf-8"/>'
        f"<title>{escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body{attr}>{body}</body>\n</html>\n"
    )


def make_cover(version, d):
    """1600 x 2560 cover image, drawn with the book's own typeface."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1600, 2560
    img = Image.new("RGB", (W, H), "#EEEDE8")
    dr = ImageDraw.Draw(img)
    reg = str(FONTS / "ShipporiMincho-Regular-Latin.ttf")

    def centred(text, y, size, fill, spacing=0):
        f = ImageFont.truetype(reg, size)
        if spacing:  # letter-spaced line, drawn one character at a time
            widths = [dr.textlength(c, font=f) for c in text]
            x = (W - (sum(widths) + spacing * (len(text) - 1))) / 2
            for c, w in zip(text, widths):
                dr.text((x, y), c, font=f, fill=fill)
                x += w + spacing
        else:
            dr.text(((W - dr.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)

    mark = Image.open(MARK).convert("RGBA").resize((200, 200), Image.LANCZOS)
    img.paste(mark, ((W - 200) // 2, 290), mark)

    big = ImageFont.truetype(reg, 330)
    w1 = dr.textlength(TITLE, font=big)
    w2 = dr.textlength(KANJI, font=big)
    gap = 40
    x = (W - (w1 + gap + w2)) / 2
    dr.text((x, 840), TITLE, font=big, fill="#1C1C1A")
    dr.text((x + w1 + gap, 840), KANJI, font=big, fill="#5A5A55")
    centred(SUBTITLE, 1400, 72, "#3A3A36", spacing=10)
    centred(AUTHOR.upper(), 2060, 64, "#3A3A36", spacing=26)
    centred(f"Beta {version} · {long_date(d)}", 2200, 52, "#5A5A55", spacing=5)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def build_epub(texts, ded, about, version, d, path):
    book_id = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://{SITE}/book/beta-{version}"))
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pages = []  # (file, title, xhtml, in_toc)
    pages.append(("cover.xhtml", "Cover",
                  xhtml("Cover", f'<img src="cover.jpg" alt="{TITLE} {KANJI}, {SUBTITLE.lower()} by {AUTHOR}"/>', "cover"),
                  False))
    pages.append(("colophon.xhtml", "Colophon",
                  xhtml("Colophon", '<div class="colophon">' + "".join(colophon_lines(version, d)) + "</div>"),
                  False))
    if ded:
        pages.append(("dedication.xhtml", "Dedication",
                      xhtml("Dedication", f'<section class="dedication" epub:type="dedication">'
                            f'<div class="verse">{verse_html(ded)}</div>'
                            f'<p class="to">{escape(DEDICATION_TO)}</p></section>'),
                      False))
    if about:
        pages.append(("about.xhtml", "About River",
                      xhtml("About River", f'<section class="about"><h2>About River</h2><p>{escape(about)}</p></section>'),
                      True))
    for n, t, v in texts:
        body = (f'<section class="piece" epub:type="chapter"><h3>{escape(t)}</h3>'
                f'<div class="verse {size_class(v)}">{verse_html(v)}</div>'
                f'<p class="sign">{escape(SIGN)}</p></section>')
        pages.append((f"t{n}.xhtml", t, xhtml(t, body), True))

    toc_items = "".join(f'<li><a href="{f}">{escape(t)}</a></li>' for f, t, _, in_toc in pages if in_toc)
    nav = xhtml("Contents",
                f'<nav epub:type="toc" id="toc" class="toc"><h2>Contents</h2><ol>{toc_items}</ol></nav>'
                '<nav epub:type="landmarks" hidden="hidden"><ol>'
                '<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>'
                '<li><a epub:type="toc" href="nav.xhtml">Contents</a></li>'
                f'<li><a epub:type="bodymatter" href="t{texts[0][0]}.xhtml">Texts</a></li>'
                "</ol></nav>")

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        '<item id="font-r" href="fonts/ShipporiMincho-Regular-Latin.ttf" media-type="font/ttf"/>',
        '<item id="font-b" href="fonts/ShipporiMincho-SemiBold-Latin.ttf" media-type="font/ttf"/>',
    ]
    spine = []
    for f, _, _, _ in pages:
        pid = f.rsplit(".", 1)[0]
        manifest.append(f'<item id="{pid}" href="{f}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{pid}"/>')
        if f == ("dedication.xhtml" if ded else "colophon.xhtml"):
            spine.append('<itemref idref="nav"/>')

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en-GB">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
        f"<dc:title>{TITLE} {KANJI}</dc:title>\n"
        f"<dc:creator>{AUTHOR}</dc:creator>\n"
        "<dc:language>en-GB</dc:language>\n"
        f"<dc:date>{d.isoformat()}</dc:date>\n"
        f"<dc:publisher>{AUTHOR}</dc:publisher>\n"
        f"<dc:rights>© {d.year} {AUTHOR}. All rights reserved.</dc:rights>\n"
        f"<dc:description>{SUBTITLE} by {AUTHOR}. Beta {version}, {long_date(d)}.</dc:description>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        '<meta name="cover" content="cover-image"/>\n'
        "</metadata>\n<manifest>\n" + "\n".join(manifest) + "\n</manifest>\n"
        "<spine>\n" + "\n".join(spine) + "\n</spine>\n</package>\n"
    )
    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>\n"
    )

    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        # Apple Books: keep the book's own typeface and layout.
        z.writestr("META-INF/com.apple.ibooks.display-options.xml",
                   '<?xml version="1.0" encoding="UTF-8"?>\n<display_options><platform name="*">'
                   '<option name="specified-fonts">true</option></platform></display_options>\n',
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", EPUB_CSS, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.jpg", make_cover(version, d), compress_type=zipfile.ZIP_STORED)
        for name in ("ShipporiMincho-Regular-Latin.ttf", "ShipporiMincho-SemiBold-Latin.ttf"):
            z.write(FONTS / name, f"OEBPS/fonts/{name}", compress_type=zipfile.ZIP_DEFLATED)
        for f, _, x, _ in pages:
            z.writestr(f"OEBPS/{f}", x, compress_type=zipfile.ZIP_DEFLATED)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Compile River into a PDF and EPUB edition.")
    ap.add_argument("--date", help="date on the edition, YYYY-MM-DD (default: today in Japan)")
    ap.add_argument("--only", choices=["pdf", "epub"], help="build just one format")
    ap.add_argument("--publish", action="store_true",
                    help="also put this edition on the home page (books/ and assets/book.js)")
    a = ap.parse_args()

    d = date.fromisoformat(a.date) if a.date else datetime.now(JST).date()
    texts, about, version = read_site()
    ded = None
    if DEDICATION_TEXT is not None:
        match = [v for n, _, v in texts if n == DEDICATION_TEXT]
        if not match:
            raise SystemExit(f"Dedication text {DEDICATION_TEXT} not found in index.html")
        ded = match[0]
        texts = [x for x in texts if x[0] != DEDICATION_TEXT]
    OUT.mkdir(exist_ok=True)
    stem = f"river-beta-{version}-{d.isoformat()}"
    made = []
    if a.only != "epub":
        build_pdf(texts, ded, about, version, d, OUT / f"{stem}.pdf")
        made.append(f"{stem}.pdf")
    if a.only != "pdf":
        build_epub(texts, ded, about, version, d, OUT / f"{stem}.epub")
        made.append(f"{stem}.epub")
    print(f"River 川 · Beta {version} · {long_date(d)} · {len(texts)} texts" + (f" · {DEDICATION_TO}" if ded else ""))
    for m in made:
        print(f"  editions/{m}")
    if a.publish:
        if a.only:
            raise SystemExit("--publish needs both formats; leave out --only")
        publish(stem, version, d, len(texts))


def publish(stem, version, d, count):
    """Offer this edition on the home page: copy it into books/ (replacing the
    previous edition there) and write assets/book.js, which the page reads."""
    import shutil
    PUBLIC.mkdir(exist_ok=True)
    for old in PUBLIC.glob("river-beta-*"):
        old.unlink()
    info = {"version": version, "date": d.isoformat(), "texts": count}
    # The cover, smaller, for the home page's book section.
    from io import BytesIO
    from PIL import Image
    cover = Image.open(BytesIO(make_cover(version, d))).resize((640, 1024), Image.LANCZOS)
    cover_name = f"{stem}-cover.jpg"
    cover.save(PUBLIC / cover_name, "JPEG", quality=86, optimize=True, progressive=True)
    info["cover"] = f"books/{cover_name}"
    for ext in ("pdf", "epub"):
        shutil.copy2(OUT / f"{stem}.{ext}", PUBLIC / f"{stem}.{ext}")
        size = (PUBLIC / f"{stem}.{ext}").stat().st_size
        info[ext] = {"href": f"books/{stem}.{ext}", "kb": round(size / 1024)}
    BOOK_JS.write_text(
        "// The book edition offered on the home page. Written by `python3 book.py --publish`;\n"
        "// do not edit by hand.\n"
        "window.RIVER_BOOK = " + json.dumps(info, indent=2) + ";\n", encoding="utf-8")
    print(f"  published to books/ and assets/book.js")


if __name__ == "__main__":
    main()
