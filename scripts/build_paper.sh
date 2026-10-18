#!/usr/bin/env bash
# Build docs/paper/main.pdf and supplement.pdf: numbers + figures from results, then LaTeX in the rescuemind:latex image.
#   FINAL=1 bash scripts/build_paper.sh      strict submission build (refuses any pending result)
#   SNAPSHOT=1 bash scripts/build_paper.sh   submission snapshot: pending studies read "registered, not yet run"; output in docs/snapshot/paper/
set -euo pipefail
cd "$(dirname "$0")/.."

# SNAPSHOT=1 (submission snapshot, `make snapshot`): the studies without results print "registered, not yet run at submission" instead of a
# pending/TBD marker.  Built in docs/snapshot/paper (not tracked); docs/paper/numbers.tex, main.pdf and supplement.pdf are not touched.
# FINAL=1 stays the strict mode below and excludes this one.
case "${SNAPSHOT:-}" in ''|0) ;; *)
  case "${FINAL:-}" in ''|0) ;; *) echo "SNAPSHOT=1 and FINAL=1 exclude each other (FINAL refuses a pending result)" >&2; exit 2;; esac
  D="${SNAPSHOT_DIR:-docs/snapshot}/paper"
  mkdir -p "$D"
  python3 scripts/paper_numbers.py --snapshot --out "$D"
  # sources and the committed figures; the tables that paper_numbers.py generated stay (cp -n), no figure is regenerated (no Gazebo, no GPU)
  cp docs/paper/main.tex docs/paper/supplement.tex docs/paper/sec_formal.tex docs/paper/references.bib "$D"/
  cp docs/paper/fig_*.pdf "$D"/
  cp -n docs/paper/tab_*.tex "$D"/ 2>/dev/null || true
  # one core, lowest priority: a measuring campaign may be running on this host
  for f in main supplement; do
    nice -n 19 docker run --rm --cpus=1 -u "$(id -u):$(id -g)" -v "$PWD/$D:/w" -w /w rescuemind:latex \
      latexmk -pdf -interaction=nonstopmode -halt-on-error $f.tex > "$D/build_$f.log" 2>&1 || { tail -40 "$D/build_$f.log"; exit 1; }
  done
  grep -hE "Warning.*(undefined|Citation)" "$D/main.log" "$D/supplement.log" | sort -u | head -20 || true
  for f in main supplement; do
    echo "built $D/$f.pdf: $(docker run --rm -v "$PWD/$D:/w" rescuemind:latex pdfinfo /w/$f.pdf | grep Pages)"
  done
  exit 0;;
esac
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
