# River 川

Short texts that move like a quiet river: on breath, love, spring and surrendering to the flow.

Short texts by Yoso, Miyazaki. The site is a single `index.html`, published with GitHub Pages.

## RSS feed

The feed is `feed.xml` (<https://river.yoso.one/feed.xml>), one item per text. After adding or editing texts in the `TEXTS` list in `index.html`, run this in the river folder, then commit `feed.xml` with the change:

```
python3 build_feed.py
```

Each text keeps the date it first appeared in the feed, so readers only see new texts.

© Yoso

## Book editions (PDF and EPUB)

When there has been enough change for a new edition, run this in the river folder:

```
python3 book.py
```

It reads the texts from `TEXTS` in `index.html` (English only for now), the About text and the beta number in `VERSION`, and makes two files in `editions/`, named with the beta number and today's date:

- `river-beta-0.4-2026-10-21.pdf`: an A5 book (cover, colophon, About, contents, one text per page)
- `river-beta-0.4-2026-10-21.epub`: the same book for phones and e-readers

Use `--date 2026-11-03` to put a different date on it. The book is set in Shippori Mincho, the site's own typeface, kept small in `book/fonts` (see `book/make_fonts.py`). It needs WeasyPrint and Pillow: `pip3 install weasyprint pillow`.

`editions/` is not committed, so the books are not public on the site. Keep the copies you want on the backup drive.

## Publishing an update (beta number)

The footer of every page shows the site's beta number, for example 'Beta 0.4'. It goes up by one with each update. To publish, in this folder:

```
python3 release.py "What changed"
```

That moves the number up (kept in `VERSION`), writes it into every footer, runs the check below, and commits and pushes. If the check fails, nothing is changed and the number stays where it was. Edits made straight on GitHub's website do not move the number; the next `release.py` run catches up.

## Safety: check, publish, undo

**Before publishing**, run the check in this folder:

```
python3 check.py
```

It looks for broken HTML, links to missing files, script errors, a missing hub link or mailing-list form, and a broken `feed.xml` or `robots.txt`. GitHub runs the same check on every push ('Check and publish' under the Actions tab). Once Settings → Pages → Source is set to **GitHub Actions**, a version that fails the check is never published: the live site keeps its last good version, and GitHub emails you what went wrong.

**To undo the last change**, in this folder:

```
git revert HEAD
git push
```

**To go back to a known-good version** (kept as branches named `good-YYYY-MM-DD`):

```
git fetch origin
git checkout origin/good-2026-10-20 -- .
git commit -m "Back to the good version of 20 October 2026"
git push
```

A full copy of this site, with its history, is also backed up to the external drive (`BLACK_PUNK_/00 Yoso_one Websites Back up`).

## Mailing list

The sign-up form asks for an email address first; pressing **Continue** shows a list of Yoso's newsletters (The Vault, Yosokuro, Shinsei, River, On), with this site's own one already ticked. Each ticked box reaches Buttondown as a tag (`one`, `yosokuro`, `shinsei`, `river`, `on`), so to write to one newsletter's readers, send to that tag. The step is run by `assets/list-choice.js`, which is the same file on every site; without it the boxes simply show under the email field and the form still works. To add or rename a newsletter, change the boxes in every form, `NEWSLETTERS` in `check.py`, and this list, on every site.
