#!/usr/bin/env bash
# Build docs/paper/main.pdf and supplement.pdf: numbers + figures from results, then LaTeX in the rescuemind:latex image.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/paper_numbers.py

# FINAL=1 (submission build): fail if any result macro is still \TBD or a red TBD would be printed
if [ "${FINAL:-0}" = 1 ]; then
  n=$(grep -c '{\\TBD}' docs/paper/numbers.tex || true)
  if [ "$n" -gt 0 ]; then
    echo "FINAL build refused: $n macros are still \\TBD:" >&2
    grep '{\\TBD}' docs/paper/numbers.tex | sed 's/\\newcommand{\\\([A-Za-z]*\)}.*/  \1/' >&2
    exit 3
  fi
  # a literal \TBD in the sources (not a result macro) also refuses; the LaTeX-level \PackageError in numbers.tex is the backstop
  lit=$(grep -n '\\TBD' docs/paper/main.tex docs/paper/supplement.tex docs/paper/sec_formal.tex | grep -v -E '\\(newcommand|providecommand)|^[^:]*:[0-9]+:[[:space:]]*%' || true)
  if [ -n "$lit" ]; then
    echo "FINAL build refused: literal \\TBD in the sources:" >&2
    echo "$lit" | cut -c1-140 >&2
    exit 3
  fi
fi
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_paper_figures.py
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/docs/paper:/w" -w /w rescuemind:latex \
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex > docs/paper/build.log 2>&1 || { tail -40 docs/paper/build.log; exit 1; }
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/docs/paper:/w" -w /w rescuemind:latex \
  latexmk -pdf -interaction=nonstopmode -halt-on-error supplement.tex > docs/paper/build_supplement.log 2>&1 || { tail -40 docs/paper/build_supplement.log; exit 1; }
grep -hE "Warning.*(undefined|Citation)" docs/paper/main.log docs/paper/supplement.log | sort -u | head -20 || true
for f in main supplement; do
  echo "built docs/paper/$f.pdf: $(docker run --rm -v "$PWD/docs/paper:/w" rescuemind:latex pdfinfo /w/$f.pdf | grep Pages)"
done
