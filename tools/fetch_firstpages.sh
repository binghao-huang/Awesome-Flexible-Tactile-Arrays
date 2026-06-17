#!/usr/bin/env bash
# Download each paper's PDF and render page 1 -> static/paper_firstpage/<slug>.jpg
# Used as the hero image on the per-paper detail pages. Skips papers with no PDF.
# Re-runnable: only fetches a slug that doesn't already have an image (pass -f to force).
set -u

cd "$(dirname "$0")/.." || exit 1
OUT="static/paper_firstpage"
mkdir -p "$OUT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

FORCE=0
[ "${1:-}" = "-f" ] && FORCE=1

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# slug|pdf_url   (papers with no public PDF are intentionally omitted)
MAP="
stag|https://www.nature.com/articles/s41586-019-1234-z.pdf
flexitac|https://arxiv.org/pdf/2604.28156
3d-vitac|https://arxiv.org/pdf/2410.24091
vt-refine|https://openreview.net/pdf?id=mV3W5givYb
touch-in-the-wild|https://arxiv.org/pdf/2507.15062
policy-consensus|https://arxiv.org/pdf/2509.23468
motif-hand|https://arxiv.org/pdf/2506.19201
reactive-gripper|https://www.nature.com/articles/s44182-026-00079-y.pdf
object-pose|https://arxiv.org/pdf/2509.13591
force-gripper|https://arxiv.org/pdf/2602.10013
tacvla|https://arxiv.org/pdf/2603.12665
quad-locomanip|https://arxiv.org/pdf/2604.27224
taccorl|https://arxiv.org/pdf/2606.11743
wt-umi|https://arxiv.org/pdf/2606.13232
hipi|https://arxiv.org/pdf/2606.11372
art-glove|https://arxiv.org/pdf/2606.16370
"

ok=0; fail=0; skip=0
for line in $MAP; do
  [ -z "$line" ] && continue
  slug="${line%%|*}"
  url="${line##*|}"
  dest="$OUT/$slug.jpg"

  if [ "$FORCE" -eq 0 ] && [ -f "$dest" ]; then
    echo "skip   $slug (exists)"; skip=$((skip+1)); continue
  fi

  pdf="$TMP/$slug.pdf"
  code=$(curl -sL -A "$UA" --max-time 90 -o "$pdf" -w "%{http_code}" "$url")
  if [ "$code" != "200" ] || [ ! -s "$pdf" ]; then
    echo "FAIL   $slug  HTTP $code  $url"; fail=$((fail+1)); continue
  fi
  # Verify it is actually a PDF (Nature/paywalls sometimes return HTML).
  if ! head -c 5 "$pdf" | grep -q '%PDF'; then
    echo "FAIL   $slug  (not a PDF — likely paywalled/HTML)  $url"; fail=$((fail+1)); continue
  fi

  # Render page 1 at 150 DPI, then cap width to 1200px and compress.
  if ! pdftoppm -jpeg -r 150 -f 1 -l 1 -singlefile "$pdf" "$TMP/$slug" 2>/dev/null; then
    echo "FAIL   $slug  (pdftoppm render failed)"; fail=$((fail+1)); continue
  fi
  convert "$TMP/$slug.jpg" -resize '1200x1200>' -quality 82 "$dest" 2>/dev/null \
    || cp "$TMP/$slug.jpg" "$dest"
  sz=$(wc -c < "$dest")
  echo "OK     $slug  ($((sz/1024)) KB)"
  ok=$((ok+1))
done

echo "----"
echo "rendered=$ok  failed=$fail  skipped=$skip"
