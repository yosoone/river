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
