#!/usr/bin/env python3
"""Generate one paper-detail page per gallery card and wire the cards to them.

Single source of truth = the <article> cards in ../index.html. Run this after
adding/editing a card (or after refreshing tools/abstracts.json) to regenerate
papers/<slug>.html and re-link every card to its detail page.

    python3 tools/build_papers.py

No third-party dependencies (stdlib only) so it runs anywhere GitHub Pages does.
"""

from __future__ import annotations

import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
PAPERS_DIR = os.path.join(ROOT, "papers")
ABSTRACTS_JSON = os.path.join(ROOT, "tools", "abstracts.json")
# Rendered page-1 images of each paper PDF (see tools/fetch_firstpages.sh).
# When present, used as the detail-page hero instead of the gallery teaser.
FIRSTPAGE_DIR = os.path.join(ROOT, "static", "paper_firstpage")

# Slugs in the SAME order the <article> cards appear in index.html. The detail
# page for card N is papers/<SLUGS[N]>.html. Keep this in sync when reordering.
SLUGS = [
    "stag",
    "flexitac",
    "3d-vitac",
    "vt-refine",
    "touch-in-the-wild",
    None,  # Analog Devices industry feature — links out to analog.com, no detail page
    None,  # Analog Devices Signals+ feature (slip prevention) — external, no detail page
    "leflexitac",
    "policy-consensus",
    "reactive-gripper",
    "object-pose",
    "force-gripper",
    "tacvla",
    "vtap-gripper",
    "quad-locomanip",
    "taccorl",
    "wt-umi",
    "hipi",
    "art-glove",
    "actionsense",
    "phystouch",
    "intcarpet",
]

# Marker comments let us re-run idempotently: anything between them is regenerated.
LINK_OPEN = "<!-- detail-link:start -->"
LINK_CLOSE = "<!-- detail-link:end -->"

# Per-slug overrides for the detail page's resource links (the gallery card is
# left untouched). Each entry is a list of {label, href, icon} that REPLACES the
# card's parsed links on the detail page. Use when the public link is paywalled
# and we host a copy locally. Paths are relative to the papers/ directory.
LINK_OVERRIDES = {
    # STAG's Nature article is paywalled; link the locally-hosted PDF instead.
    "stag": [
        {"label": "Webpage", "href": "https://stag.csail.mit.edu/", "icon": "public"},
        {"label": "Paper (PDF)", "href": "pdf/stag-scalable-tactile-glove.pdf", "icon": "description"},
        {"label": "Code", "href": "https://github.com/Erkil1452/touch", "icon": "code"},
    ],
}


# --------------------------------------------------------------------------- #
# Parsing the gallery cards
# --------------------------------------------------------------------------- #
def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def extract_head(index_html: str) -> str:
    """Reuse index.html's <head> verbatim so detail pages share the exact
    Tailwind config / design tokens / fonts. Returns the inner head HTML."""
    m = re.search(r"<head>(.*?)</head>", index_html, re.S)
    if not m:
        raise SystemExit("Could not find <head> in index.html")
    return m.group(1)


def fix_paths(snippet: str) -> str:
    """Card media paths are relative to repo root (static/...). Detail pages
    live in papers/, so they need ../static/..."""
    snippet = snippet.replace('src="static/', 'src="../static/')
    snippet = snippet.replace('poster="static/', 'poster="../static/')
    return snippet


def parse_articles(index_html: str) -> list[dict]:
    articles = re.findall(r"<article\b.*?</article>", index_html, re.S)
    if len(articles) != len(SLUGS):
        raise SystemExit(
            f"Found {len(articles)} cards but SLUGS has {len(SLUGS)}. "
            "Update SLUGS in build_papers.py to match index.html."
        )

    parsed = []
    for slug, art in zip(SLUGS, articles):
        # A None slug marks an "external" card (e.g. an industry feature that
        # links straight to a third-party site). We don't generate a detail page
        # or rewrite its links — its card already carries its own outbound link.
        if slug is None:
            parsed.append({"slug": None, "external": True})
            continue
        # If index.html was already linked, strip the wrappers so the detail
        # page's own title/media never become self-links.
        art = _unwrap(art)
        category = re.search(r'data-category="([^"]*)"', art).group(1)

        # Media block: the first <div class="relative ..."> (the media frame),
        # up to the card body <div class="p-5 ...">. Tolerant of the frame's
        # exact height class (aspect-video, h-56, etc.) so card-style tweaks
        # don't silently break parsing.
        media_m = re.search(
            r'<div class="relative [^"]*">(.*?)</div>\s*<div class="p-5',
            art,
            re.S,
        )
        media_inner = media_m.group(1) if media_m else ""

        # The media element itself (video or img), without the absolute badges.
        media_el = ""
        vid = re.search(r"<video\b.*?</video>", media_inner, re.S)
        if vid:
            media_el = vid.group(0)
        else:
            img = re.search(r"<img\b[^>]*?/>", media_inner, re.S)
            if img:
                media_el = img.group(0)

        # Right-side badges (venue / FlexiTac). Grab the spans verbatim.
        badge_block = re.search(
            r'<div class="absolute top-4 right-4[^"]*">(.*?)</div>', media_inner, re.S
        )
        badges = []
        if badge_block:
            badges = re.findall(r"<span\b[^>]*>.*?</span>", badge_block.group(1), re.S)

        title = re.search(r"<h3\b[^>]*>(.*?)</h3>", art, re.S).group(1).strip()

        authors_m = re.search(r'<p class="authors[^"]*">(.*?)</p>', art, re.S)
        authors = authors_m.group(1).strip() if authors_m else ""

        # Optional award / media note lines (the small text-xs paragraphs).
        notes = re.findall(
            r'<p class="text-xs[^"]*">(.*?)</p>', art, re.S
        )

        # Link row: the flex-wrap div near the bottom of the card.
        linkrow_m = re.search(
            r'<div class="flex flex-wrap items-center gap-x-4[^"]*">(.*?)</div>\s*</div>\s*</article>',
            art,
            re.S,
        )
        linkrow = linkrow_m.group(1).strip() if linkrow_m else ""
        # Individual external links (label + href + icon). Note: each anchor
        # contains a nested <span> (the icon), so the body must allow '>' —
        # use .*? with DOTALL, not [^>]*.
        links = []
        for a in re.findall(r"<a\b.*?</a>", linkrow, re.S):
            href = re.search(r'href="([^"]*)"', a)
            icon = re.search(r"material-symbols-outlined[^>]*>([^<]*)</span>", a)
            # Label = visible text once the icon <span> is removed (otherwise
            # the icon glyph name, e.g. "public", leaks into the label).
            without_icon = re.sub(
                r"<span[^>]*material-symbols-outlined[^>]*>[^<]*</span>", "", a
            )
            label = re.sub(r"<[^>]+>", "", without_icon).strip()
            links.append(
                {
                    "href": href.group(1) if href else "#",
                    "icon": icon.group(1).strip() if icon else "link",
                    "label": label,
                }
            )
        # Per-slug override: replace the detail page's links (e.g. swap a
        # paywalled URL for a locally-hosted PDF). Gallery card is unaffected.
        if slug in LINK_OVERRIDES:
            links = [dict(l) for l in LINK_OVERRIDES[slug]]

        coming_soon = "coming soon" in linkrow.lower() and not links

        # Fail loudly rather than emit a blank page if a card can't be parsed.
        if not media_el:
            raise SystemExit(f"[{slug}] could not find media (video/img) in card.")
        if not title:
            raise SystemExit(f"[{slug}] could not find <h3> title in card.")

        parsed.append(
            {
                "slug": slug,
                "category": category,
                "media_el": fix_paths(media_el),
                "badges": badges,
                "title": title,
                "authors": fix_paths(authors),
                "notes": notes,
                "links": links,
                "coming_soon": coming_soon,
            }
        )
    return parsed


# --------------------------------------------------------------------------- #
# Rendering a detail page
# --------------------------------------------------------------------------- #
def plain(text: str) -> str:
    """Strip tags -> plain text (for <title>, meta description)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


# Icon per action button in the hero (falls back to the card's own icon).
PRIMARY_ICONS = {
    "public": "public",
    "description": "description",
    "movie": "movie",
    "code": "code",
}


def render_hero_media(p: dict) -> str:
    """Hero panel for the detail page. Prefer the paper's rendered first page
    (looks like an academic paper, not the home-page teaser). Fall back to the
    gallery teaser media for papers with no PDF (e.g. unreleased works)."""
    firstpage = os.path.join(FIRSTPAGE_DIR, f"{p['slug']}.jpg")
    if os.path.exists(firstpage):
        title = html.escape(plain(p["title"]))
        return (
            f'<img alt="First page of the {title} paper" loading="lazy" '
            f'class="w-full h-full object-contain bg-white" '
            f'src="../static/paper_firstpage/{p["slug"]}.jpg"/>'
        )
    # Fallback: reuse the gallery teaser, scaled to fill.
    el = p["media_el"]
    el = el.replace("group-hover:scale-105 transition-transform duration-700 ease-in-out", "")
    el = re.sub(r'\bclass="[^"]*"', lambda m: 'class="w-full h-full object-cover"', el, count=1)
    return el


def has_firstpage(p: dict) -> bool:
    return os.path.exists(os.path.join(FIRSTPAGE_DIR, f"{p['slug']}.jpg"))


def hero_container_class(p: dict) -> str:
    """Aspect ratio of the hero panel. A paper first page is portrait (US Letter
    ≈ 17:22), so give it a portrait frame; teasers stay landscape/square."""
    if has_firstpage(p):
        return "aspect-[17/22] max-w-md mx-auto lg:mx-0"
    return "aspect-video lg:aspect-square"


def render_buttons(p: dict) -> str:
    """Action buttons in the hero. First link -> filled primary, rest -> outline."""
    if p["coming_soon"] or not p["links"]:
        return (
            '<span class="inline-flex items-center gap-2 text-secondary/70 italic '
            'font-body-md">Links & paper coming soon</span>'
        )
    out = []
    for i, lk in enumerate(p["links"]):
        if i == 0:
            cls = (
                "bg-deep-space text-white font-body-md px-6 py-3 rounded-DEFAULT "
                "hover:bg-inverse-surface transition-colors inline-flex items-center "
                "gap-2 shadow-sm hover:shadow-md"
            )
        else:
            cls = (
                "bg-transparent border border-primary text-primary font-body-md px-6 "
                "py-3 rounded-DEFAULT hover:bg-surface-container-low transition-colors "
                "inline-flex items-center gap-2"
            )
        out.append(
            f'<a class="{cls}" href="{lk["href"]}" target="_blank" rel="noopener">'
            f'<span class="material-symbols-outlined">{lk["icon"]}</span>{lk["label"]}</a>'
        )
    return "\n".join(out)


def render_resource_links(p: dict) -> str:
    if p["coming_soon"] or not p["links"]:
        return (
            '<p class="text-secondary/70 italic font-body-md">'
            "Resources for this project will be released soon.</p>"
        )
    items = []
    for lk in p["links"]:
        items.append(
            '<a class="flex items-center gap-2 text-primary hover:text-primary-container '
            'transition-colors font-body-md py-1" '
            f'href="{lk["href"]}" target="_blank" rel="noopener">'
            f'<span class="material-symbols-outlined text-[18px]">{lk["icon"]}</span>'
            f'{lk["label"]}<span class="material-symbols-outlined text-[16px] '
            'text-secondary/60">open_in_new</span></a>'
        )
    return "\n".join(items)


def render_badges(p: dict) -> str:
    """Venue / FlexiTac chips shown next to the category label."""
    if not p["badges"]:
        return ""
    chips = []
    for b in p["badges"]:
        txt = plain(b)
        if not txt:
            continue
        flexitac = "FlexiTac" in txt
        cls = (
            "bg-primary text-white"
            if flexitac
            else "bg-deep-space text-white"
            if "Under Review" not in txt
            else "bg-surface-container-high text-on-surface-variant"
        )
        chips.append(
            f'<span class="font-label-caps text-label-caps px-3 py-1 rounded-full {cls}">{txt}</span>'
        )
    return '<div class="flex flex-wrap gap-2 mb-4">' + "".join(chips) + "</div>"


def render_notes(p: dict) -> str:
    """Award / media note lines from the card, shown under the authors."""
    if not p["notes"]:
        return ""
    out = []
    for n in p["notes"]:
        out.append(
            f'<p class="font-body-md text-sm text-safety-accent font-semibold mt-2">{n.strip()}</p>'
        )
    return "\n".join(out)


def render_abstract(p: dict, ab: dict | None) -> str:
    if ab and ab.get("verified") and ab.get("abstract"):
        body = html.escape(ab["abstract"])
        tag = ""
        if ab.get("isSummary"):
            tag = (
                '<p class="font-label-caps text-label-caps text-secondary/70 mb-3">'
                "SUMMARY (compiled from project sources)</p>"
            )
        # The paper/project link already lives in the Links & Resources section,
        # so we don't repeat a raw source URL here (sources were also sometimes
        # machine API endpoints used only for verification).
        return (
            tag
            + '<p class="font-body-md text-body-md text-on-surface-variant leading-relaxed">'
            + body
            + "</p>"
        )
    # No verified abstract yet.
    if ab and ab.get("tldr"):
        return (
            '<p class="font-body-md text-body-md text-on-surface-variant leading-relaxed">'
            + html.escape(ab["tldr"])
            + "</p>"
            '<p class="font-body-md text-sm text-secondary/70 italic mt-4">'
            "Full abstract will be added once the paper is publicly available.</p>"
        )
    return (
        '<p class="font-body-md text-body-md text-secondary/80 italic leading-relaxed">'
        "Abstract coming soon. Follow the resource links below for the latest details "
        "on this work.</p>"
    )


def crumb_category(category: str) -> str:
    return category.split(",")[0].strip()


def render_page(p: dict, head_inner: str, ab: dict | None) -> str:
    title_plain = plain(p["title"])
    tldr = (ab.get("tldr") if ab else "") or title_plain
    desc = html.escape(plain(tldr))[:300]
    cat = crumb_category(p["category"])

    affiliations = ""
    if ab and ab.get("affiliations"):
        affiliations = (
            '<p class="font-body-md text-sm text-secondary mt-1">'
            + html.escape(ab["affiliations"])
            + "</p>"
        )
    venue_full = ""
    if ab and ab.get("venueFull"):
        venue_full = (
            '<p class="font-label-caps text-label-caps text-secondary/80 mt-2">'
            + html.escape(ab["venueFull"])
            + "</p>"
        )

    # Detail pages live in papers/, so root paths get a ../ prefix.
    head = head_inner
    head = re.sub(r"<title>.*?</title>", f"<title>{title_plain} — Awesome FlexiTac</title>", head, flags=re.S)
    head = re.sub(r'<meta name="description"[^>]*/>', f'<meta name="description" content="{desc}"/>', head)

    return f"""<!DOCTYPE html>
<html class="light" lang="en">
<head>{head}</head>
<body class="bg-background text-on-background font-body-md antialiased min-h-screen flex flex-col">

<!-- TopNavBar -->
<header class="bg-surface-base text-primary font-body-md w-full top-0 border-b border-outline-variant sticky z-50">
<div class="flex justify-between items-center h-20 px-margin-mobile md:px-margin-desktop max-w-container-max mx-auto w-full">
<div class="flex items-baseline gap-6">
<a class="font-headline-lg text-[28px] md:text-[32px] font-bold text-deep-space tracking-tight" href="../index.html">Awesome FlexiTac</a>
<a href="https://flexitac.github.io/" target="_blank" rel="noopener" class="hidden md:inline-block text-[16px] text-secondary hover:text-primary font-label-caps transition-colors">FlexiTac Homepage</a>
</div>
<div class="hidden md:flex items-center gap-4">
<a href="https://discord.gg/6gw887Vxms" target="_blank" rel="noopener" class="bg-deep-space text-white px-4 py-2 rounded font-label-caps text-label-caps hover:bg-on-secondary-fixed transition-colors">Join Discord</a>
</div>
</div>
</header>

<main class="flex-grow w-full max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop py-12 md:py-16">

<!-- Breadcrumbs -->
<nav aria-label="Breadcrumb" class="flex text-sm text-secondary mb-8 font-body-md">
<ol class="inline-flex items-center space-x-1 md:space-x-3 flex-wrap">
<li class="inline-flex items-center"><a class="hover:text-primary transition-colors" href="../index.html">All</a></li>
<li><div class="flex items-center"><span class="material-symbols-outlined text-[16px] mx-1">chevron_right</span><a class="hover:text-primary transition-colors" href="../index.html">{html.escape(cat)}</a></div></li>
<li aria-current="page"><div class="flex items-center"><span class="material-symbols-outlined text-[16px] mx-1">chevron_right</span><span class="text-on-surface-variant font-medium">{html.escape(title_plain[:60])}{'…' if len(title_plain) > 60 else ''}</span></div></li>
</ol>
</nav>

<!-- Project Intro -->
<div class="grid grid-cols-1 lg:grid-cols-12 gap-gutter mb-16 lg:mb-24">
<div class="lg:col-span-7 flex flex-col justify-center">
<span class="font-label-caps text-label-caps text-safety-accent mb-4 block">{html.escape(p["category"])}</span>
{render_badges(p)}
<h1 class="font-display-lg text-headline-lg-mobile md:text-display-lg text-on-surface mb-6 leading-tight">{p["title"]}</h1>
<div class="mb-8">
<p class="authors font-body-md text-body-md text-on-surface-variant mb-1 font-medium">{p["authors"]}</p>
{affiliations}
{venue_full}
{render_notes(p)}
</div>
<div class="flex flex-wrap gap-4">
{render_buttons(p)}
</div>
</div>
<div class="lg:col-span-5 relative mt-8 lg:mt-0 rounded-xl overflow-hidden border border-outline-variant bg-surface-subtle {hero_container_class(p)}">
{render_hero_media(p)}
</div>
</div>

<!-- Abstract -->
<section class="mb-16 lg:mb-24">
<h2 class="font-headline-lg-mobile md:font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface mb-6 border-b border-outline-variant pb-2">Abstract</h2>
<div class="bg-surface-subtle border border-outline-variant rounded-xl p-6 md:p-8">
{render_abstract(p, ab)}
</div>
</section>

<!-- Links & Resources -->
<section class="mb-16 lg:mb-24">
<h2 class="font-headline-lg-mobile md:font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface mb-6 border-b border-outline-variant pb-2">Links &amp; Resources</h2>
<div class="bg-surface-base border border-outline-variant rounded-xl p-6 md:p-8 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2">
{render_resource_links(p)}
</div>
<div class="mt-8">
<a href="../index.html" class="inline-flex items-center gap-2 text-secondary hover:text-primary transition-colors font-body-md"><span class="material-symbols-outlined text-[18px]">arrow_back</span>Back to all works</a>
</div>
</section>
</main>

<!-- Footer -->
<footer class="bg-deep-space text-surface-bright font-body-md w-full mt-auto">
<div class="grid grid-cols-1 md:grid-cols-2 gap-gutter px-margin-mobile md:px-margin-desktop py-16 max-w-container-max mx-auto">
<div class="flex flex-col gap-4">
<a class="font-headline-lg text-headline-lg text-white hover:text-surface-variant transition-colors" href="https://flexitac.github.io/" target="_blank" rel="noopener">Maintained by the FlexiTac Team</a>
<p class="text-surface-variant text-sm mt-2">An open-source, scalable tactile solution for robotic systems.</p>
<p class="text-surface-variant/70 text-xs mt-1">© 2026 FlexiTac Research Community.</p>
</div>
<div class="flex flex-col gap-3">
<h4 class="font-label-caps text-label-caps text-surface-variant mb-2">Community</h4>
<a class="text-surface-variant hover:text-white transition-colors" href="../index.html">All Works</a>
<a class="text-surface-variant hover:text-white transition-colors" href="https://github.com/binghao-huang/Awesome-FlexiTac" target="_blank" rel="noopener">GitHub</a>
<a class="text-surface-variant hover:text-white transition-colors" href="https://discord.gg/6gw887Vxms" target="_blank" rel="noopener">Discord</a>
</div>
</div>
</footer>

<script>
  // Viewport-gated video playback (mirrors the gallery): only fetch + play
  // the hero video when it is near the viewport.
  (function () {{
    var videos = Array.from(document.querySelectorAll('video'));
    if (!('IntersectionObserver' in window)) {{ videos.forEach(function (v) {{ v.preload = 'auto'; }}); return; }}
    var io = new IntersectionObserver(function (entries) {{
      entries.forEach(function (entry) {{
        var v = entry.target;
        if (entry.isIntersecting) {{ if (v.preload !== 'auto') v.preload = 'auto'; var p = v.play(); if (p && p.catch) p.catch(function () {{}}); }}
        else {{ v.pause(); }}
      }});
    }}, {{ rootMargin: '200px 0px', threshold: 0.1 }});
    videos.forEach(function (v) {{ io.observe(v); }});
  }})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Wiring the gallery cards to their detail pages
# --------------------------------------------------------------------------- #
def _unwrap(text: str) -> str:
    """Remove any previously-applied detail-link wrappers, leaving inner HTML."""
    pat = rf"{re.escape(LINK_OPEN)}<a\b[^>]*>(.*?)</a>{re.escape(LINK_CLOSE)}"
    return re.sub(pat, r"\1", text, flags=re.S)


def link_cards(index_html: str, papers: list[dict]) -> str:
    """Make each card's media + title link to its detail page. Idempotent:
    strips any prior detail-link wrappers before re-applying."""
    articles = re.findall(r"<article\b.*?</article>", index_html, re.S)
    for art, p in zip(articles, papers):
        if p.get("external"):
            continue  # external card keeps its own outbound links
        href = f"papers/{p['slug']}.html"
        new_art = _unwrap(art)

        # 1. Title text -> link.
        def title_repl(m):
            open_tag, inner = m.group(1), m.group(2)
            return (
                f"{open_tag}{LINK_OPEN}"
                f'<a href="{href}" class="hover:text-primary transition-colors">{inner}</a>'
                f"{LINK_CLOSE}</h3>"
            )

        new_art = re.sub(
            r"(<h3\b[^>]*>)(.*?)</h3>", title_repl, new_art, count=1, flags=re.S
        )

        # 2. Media element (video or img) -> wrap in a link.
        def media_repl(m):
            return (
                f'{LINK_OPEN}<a href="{href}" class="block w-full h-full" '
                f'aria-label="View project details">{m.group(0)}</a>{LINK_CLOSE}'
            )

        if "<video" in new_art:
            new_art = re.sub(r"<video\b.*?</video>", media_repl, new_art, count=1, flags=re.S)
        else:
            new_art = re.sub(r"<img\b[^>]*?/>", media_repl, new_art, count=1, flags=re.S)

        index_html = index_html.replace(art, new_art, 1)
    return index_html


# --------------------------------------------------------------------------- #
def main() -> None:
    index_html = read(INDEX)
    head_inner = extract_head(index_html)
    papers = parse_articles(index_html)

    abstracts = {}
    if os.path.exists(ABSTRACTS_JSON):
        with open(ABSTRACTS_JSON, encoding="utf-8") as fh:
            for row in json.load(fh):
                abstracts[row["id"]] = row

    os.makedirs(PAPERS_DIR, exist_ok=True)
    generated = 0
    for p in papers:
        if p.get("external"):
            continue  # external cards link out; no detail page
        page = render_page(p, head_inner, abstracts.get(p["slug"]))
        out = os.path.join(PAPERS_DIR, f"{p['slug']}.html")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        print(f"  wrote papers/{p['slug']}.html")
        generated += 1

    linked = link_cards(index_html, papers)
    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(linked)
    print(f"Linked {generated} cards in index.html -> papers/<slug>.html "
          f"({len(papers) - generated} external card(s) left as-is)")


if __name__ == "__main__":
    main()
