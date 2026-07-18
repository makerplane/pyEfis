# Publishing the manual to the GitHub wiki

The pyEFIS manual is authored in this repo under **`docs/wiki/`** (the canonical
source) and **mirrored** to the GitHub wiki. This keeps the docs version-
controlled alongside the code and reviewable in PRs, while still presenting them
as a browsable wiki.

## Layout

```
docs/wiki/            one .md per wiki page (GitHub-wiki naming, hyphenated)
  Home.md             wiki landing page
  _Sidebar.md         wiki navigation
  Concepts.md, Widgets-*.md, Screens-*.md, Pilots-Guide.md, ...
docs/images/          shared images (referenced as ../images/NAME.png)
tools/sync_wiki.sh    the mirror script
```

**Authoring rules** (so the mirror is lossless):
- One page per file; the filename (minus `.md`) is the wiki page name.
- Link between pages **without** the extension: `[Concepts](Concepts)`.
  (These resolve in the wiki. In the repo file view they are not clickable,
  which is acceptable — the repo copy is the source, the wiki is the rendered
  product.)
- Reference images as `../images/NAME.png`. The mirror copies `docs/images/`
  into the wiki and rewrites the path to `images/NAME.png`.
- `Home.md`, `_Sidebar.md`, `_Footer.md` are GitHub-wiki special pages.

## Mirroring

The GitHub wiki is a separate git repo: `git@github.com:billmallard/pyEfis.wiki.git`
(HTTPS: `https://github.com/billmallard/pyEfis.wiki.git`). It must be created
once (open the repo's **Wiki** tab and add any page) before it can be cloned.

```bash
# from the pyEfis repo root
tools/sync_wiki.sh                       # clones/updates ../pyEfis.wiki, copies pages+images
cd ../pyEfis.wiki
git diff                                 # review
git add -A && git commit -m "Sync manual from docs/wiki" && git push
```

The script **does not push** — it stages the mirror in a local clone for you to
review and push. Publishing is an outward-facing action and is left to a human.
