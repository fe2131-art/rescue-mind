#!/usr/bin/env bash
# Build docs/paper/main.pdf and supplement.pdf: numbers + figures from results, then LaTeX in the rescuemind:latex image.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/paper_numbers.py
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_paper_figures.py
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/docs/paper:/w" -w /w rescuemind:latex \
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex > docs/paper/build.log 2>&1 || { tail -40 docs/paper/build.log; exit 1; }
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/docs/paper:/w" -w /w rescuemind:latex \
  latexmk -pdf -interaction=nonstopmode -halt-on-error supplement.tex > docs/paper/build_supplement.log 2>&1 || { tail -40 docs/paper/build_supplement.log; exit 1; }
grep -hE "Warning.*(undefined|Citation)" docs/paper/main.log docs/paper/supplement.log | sort -u | head -20 || true
for f in main supplement; do
  echo "built docs/paper/$f.pdf: $(docker run --rm -v "$PWD/docs/paper:/w" rescuemind:latex pdfinfo /w/$f.pdf | grep Pages)"
done
