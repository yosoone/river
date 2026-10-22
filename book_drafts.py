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
PHOTO = HERE / "about.jpg"

COLLECTION = {"collection", "best of", "refine"}
FRONT = {"front matters"}
BACK = {"back matters"}
NEVER = {"seeds", "rework"}
FRONT_ONLY = {"thank you for always being by my side"}

AUTHOR_NOTE = (
    "Yoso is a tattoo artist and multimedia practitioner living in Miyazaki, Japan. "
    "His work moves between tattooing, art installation, writing and meditation, "
    "rooted in Buddhist and Shinto practice."
)


# ---------------------------------------------------------------- source

def clean_title(stem):
    t = re.sub(r"^\d+\s+", "", stem)
    t = re.sub(r"\s*\[\d+\]$", "", t)
    t = re.sub(r"\s+_new$", "", t)
    return t.strip()


def first_version(raw):
    raw = raw.replace(" ", "\n").replace("\r\n", "\n")
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
        if e["title"].lower() in FRONT_ONLY:
            continue
        v, signed = first_version(e["raw"])
        if v:
            texts.append((e["n"], e["title"], v))
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

def paras(text):
    return "".join('<p class="stanza">' + "<br/>".join(escape(x) for x in st.split("\n")) + "</p>"
                   for st in re.split(r"\n\s*\n", text.strip()))


def front_back(entries, version, d, img):
    """(id, title, body-html, classes, pdf_only) for every page outside the collection.
    img(name) gives the image path to use (differs between PDF and EPUB)."""
    sig = f'<p class="sign"><img src="{img("signature.png")}" alt="— Yoso"/></p>'
    pages = {}

    epi, _ = first_version(pick(entries, "Awakening Mind")["raw"])
    pages["epigraph"] = ("Awakening mind", f'<div class="verse">{B.verse_html(epi)}</div>{sig}', "centre epi")

    cl = copyright_lines(pick(entries, "Copyright")["raw"], version, d)
    body = f'<p class="name">{escape(cl[0])}</p>' + "".join(
        f"<p>{escape(l)}</p>" if not l.startswith(B.SITE) else
        f'<p><a href="https://{B.SITE}">{escape(l)}</a></p>' for l in cl[1:])
    pages["copyright"] = ("Copyright", f'<div class="colophon">{body}</div>', "colo")

    ty, _ = first_version(pick(entries, "Thank you Japan")["raw"])
    head, rest = ty.split("\n", 1)
    pages["japan"] = (head.strip(), f'<h2 class="ptitle">{escape(head.strip())}</h2>'
                      f'<div class="verse small">{paras(rest)}</div>{sig}', "centre")

    half = pick(entries, "Half Title Page")["raw"].strip() or B.KANJI
    pages["half"] = ("Half title", f'<p class="half">{escape(half)}</p>', "centre")

    ded = pick(entries, "Dedication")["raw"].strip()
    pages["dedication"] = ("Dedication", f'<p class="to">{escape(ded)}</p>', "centre ded")

    tq, _ = first_version(pick(entries, "Thank You")["raw"])
    pages["thanks"] = ("Thank you", f'<div class="verse quiet">{B.verse_html(tq)}</div>', "centre")

    pages["mark"] = ("River", f'<img class="gold" src="{img("yoso-mark.png")}" alt="Yoso"/>'
                     f'<p class="url"><a href="https://{B.SITE}">{B.SITE}</a></p>', "centre")

    # back matter
    tr = pick(entries, "Thank You for reading")["raw"].replace(" ", "\n").strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n", tr) if b.strip()]
    html = []
    for b in blocks:
        if "Signature" in b and "Claude" in b:
            html.append(f'<p class="sign seal"><img src="{img("signature.png")}" alt="Signature and seal of Yoso"/></p>')
        else:
            html.append('<p class="stanza">' + "<br/>".join(escape(x.strip()) for x in b.split("\n")) + "</p>")
    pages["reading"] = ("Thank you for reading", f'<div class="letter">{"".join(html)}</div>', "centre")

    dn = [l.strip() for l in pick(entries, "Donate")["raw"].split("\n") if l.strip()]
    link = next((l for l in dn if l.startswith("http")), "https://donate.yoso.one")
    words = " ".join(l for l in dn if not l.startswith("http"))
    pages["donate"] = ("Donate", f'<p class="stanza">{escape(words)}</p>'
                       f'<p class="url"><a href="{escape(link)}">{escape(link.split("//")[-1])}</a></p>', "centre")

    end = pick(entries, "End")["raw"].strip()
    pages["end"] = ("The End", f'<p class="theend">{escape(end)}</p>', "centre")

    pages["author"] = ("About the author",
                       f'<img class="portrait" src="{img("about.jpg")}" alt="Yoso"/>'
                       f'<p class="aname">{B.AUTHOR}</p><p class="anote">{escape(AUTHOR_NOTE)}</p>'
                       f'<p class="url"><a href="https://{B.SITE}">{B.SITE}</a></p>', "centre author")
    return pages


FRONT_ORDER = ["epigraph", "copyright", "japan", "half", "blank", "dedication", "blank", "thanks", "mark"]
BACK_ORDER = ["reading", "donate", "end", "author"]


def piece(n, t, v, img):
    return (f'<h3>{escape(t)}</h3><div class="verse {B.size_class(v)}">{B.verse_html(v)}</div>'
            f'<p class="sign"><img src="{img("signature.png")}" alt="— Yoso"/></p>')


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
"""


def build_pdf(entries, texts, version, d, path):
    from weasyprint import HTML
    img = lambda n: str(HERE / ("images/" + n if n != "about.jpg" else n))
    fb = front_back(entries, version, d, img)
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
    for k in FRONT_ORDER:
        if k == "blank":
            parts.append('<section class="front page"></section>')
            continue
        _, body, cls = fb[k]
        parts.append(f'<section class="front page {cls}">{body}</section>')
    for n, t, v in texts:
        parts.append(f'<section class="piece" id="t{n}">{piece(n, t, v, img)}</section>')
    for k in BACK_ORDER:
        _, body, cls = fb[k]
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
"""


def build_epub(entries, texts, version, d, path):
    img = lambda n: n
    fb = front_back(entries, version, d, img)
    book_id = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://{B.SITE}/book/beta-{version}-{d}"))
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = [("cover.xhtml", "Cover", B.xhtml("Cover", f'<img src="cover.jpg" alt="{B.TITLE} {B.KANJI}, '
                                                    f'{B.SUBTITLE.lower()} by {B.AUTHOR}"/>', "cover"), False)]
    types = {"epigraph": "epigraph", "copyright": "copyright-page", "dedication": "dedication",
             "half": "halftitlepage", "author": "contributors"}
    for k in FRONT_ORDER:
        if k == "blank":
            continue
        t, body, cls = fb[k]
        et = f' epub:type="{types[k]}"' if k in types else ""
        pages.append((f"{k}.xhtml", t, B.xhtml(t, f'<section class="page {cls}"{et}>{body}</section>'), False))
    first = None
    for n, t, v in texts:
        f = f"t{n}.xhtml"
        first = first or f
        pages.append((f, t, B.xhtml(t, f'<section class="piece" epub:type="chapter">{piece(n, t, v, img)}</section>'), True))
    for k in BACK_ORDER:
        t, body, cls = fb[k]
        et = f' epub:type="{types[k]}"' if k in types else ""
        pages.append((f"{k}.xhtml", t, B.xhtml(t, f'<section class="page {cls}"{et}>{body}</section>'), k != "end"))

    toc = "".join(f'<li><a href="{f}">{escape(t)}</a></li>' for f, t, _, inc in pages if inc)
    nav = B.xhtml("Contents", f'<nav epub:type="toc" id="toc" class="toc"><h2>Contents</h2><ol>{toc}</ol></nav>'
                  '<nav epub:type="landmarks" hidden="hidden"><ol>'
                  '<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>'
                  f'<li><a epub:type="bodymatter" href="{first}">Texts</a></li></ol></nav>')
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
        f"<dc:title>{B.TITLE} {B.KANJI}</dc:title>\n<dc:creator>{B.AUTHOR}</dc:creator>\n"
        f"<dc:language>en-GB</dc:language>\n<dc:date>{d.isoformat()}</dc:date>\n"
        f"<dc:publisher>{B.AUTHOR}</dc:publisher>\n"
        f"<dc:rights>© {d.year} {B.AUTHOR}. All rights reserved.</dc:rights>\n"
        f"<dc:description>{B.SUBTITLE} by {B.AUTHOR}. Beta {version}, {B.long_date(d)}.</dc:description>\n"
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

def cover_from_svg(svg_path, version, d):
    """Use Yoso's Illustrator cover (1600 x 2560 SVG). The Edition line is
    rewritten with this edition's beta number and date and kept centred on the
    same point. Returns (jpeg bytes 1600x2560, png bytes 2400x3840)."""
    import cairosvg
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
    big = cairosvg.svg2png(bytestring=svg.encode(), output_width=2400, output_height=3840)
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
