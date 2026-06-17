# Awesome Flexible Tactile Arrays [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

A curated list of research on **dense, flexible piezoresistive tactile arrays** for robot manipulation — spanning sensor hardware, simulation, and policy learning.

🔗 **Live site:** https://binghao-huang.github.io/Awesome-Flexible-Tactile-Arrays/

Maintained by the [FlexiTac](https://flexitac.github.io/) team. Inclusion does **not** imply use of the FlexiTac sensor — works built on it are marked with a `FlexiTac` badge on the site.

## Scope

Works in robot manipulation that use dense, flexible, low-cost tactile sensing (piezoresistive arrays and close cousins), regardless of whether they use FlexiTac specifically. Optical (e.g. GelSight) and magnetic (e.g. ReSkin) tactile sensors are out of scope.

## Categories

- **Hardware Design** — sensor and gripper/hand hardware
- **Glove/Hand** — tactile gloves and multi-fingered hands
- **Simulation** — tactile simulation and sim-to-real
- **Multi-Modal Learning** — visuo-tactile / multi-modal policy learning
- **Locomanipulation/Humanoid** — whole-body and legged tactile manipulation

## Contributing

Have a relevant work? **[Open a PR or issue](https://github.com/binghao-huang/Awesome-Flexible-Tactile-Arrays/issues)** to add it.

To add an entry, edit [`index.html`](index.html) — copy an existing `<article class="gallery-card" ...>` block, update the teaser media (`static/`), title, authors, links, and `data-category` (comma-separated for multiple categories).

### Per-paper detail pages

Each gallery card links to a detail page under [`papers/`](papers/) (e.g. `papers/vt-refine.html`). These pages reuse the same design system as the gallery and are **generated** from the cards by [`tools/build_papers.py`](tools/build_papers.py), so the gallery stays the single source of truth.

Each detail page shows the **paper's first page** as the hero image (rendered from the PDF — more professional than reusing the gallery teaser). Papers without a public PDF fall back to their gallery teaser.

After adding or editing a card:

1. Add the new paper's slug to the `SLUGS` list in [`tools/build_papers.py`](tools/build_papers.py) (same order as the cards in `index.html`).
2. *(Optional)* Add its abstract/affiliations to [`tools/abstracts.json`](tools/abstracts.json), keyed by slug. Without an entry, the page renders with an "Abstract coming soon" placeholder.
3. *(Optional)* Add the PDF URL to [`tools/fetch_firstpages.sh`](tools/fetch_firstpages.sh) and render the first-page image:

   ```bash
   bash tools/fetch_firstpages.sh        # downloads PDFs, renders page 1 -> static/paper_firstpage/<slug>.jpg
   ```

   Requires `pdftoppm` (poppler) and `convert` (ImageMagick). Existing images are skipped; pass `-f` to re-render. To add an image by hand instead, drop a `static/paper_firstpage/<slug>.jpg` file.
4. Regenerate the pages:

   ```bash
   python3 tools/build_papers.py
   ```

   This (re)writes `papers/<slug>.html` for every card and re-links each card's image and title to its detail page. It uses `static/paper_firstpage/<slug>.jpg` as the hero when present. The script is idempotent and has no third-party dependencies.

## License

Content is shared for research reference. Website template adapted from the FlexiTac project.
