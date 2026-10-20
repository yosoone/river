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

**To go back to a known-good version** (tags named `good-YYYY-MM-DD`):

```
git checkout good-2026-10-20 -- .
git commit -m "Back to the good version of 20 October 2026"
git push
```

A full copy of this site, with its history, is also backed up to the external drive (`BLACK_PUNK_/00 Yoso_one Websites Back up`).
