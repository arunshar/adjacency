#!/usr/bin/env bash
# Build an ICML LaTeX paper: pdflatex -> bibtex -> pdflatex -> pdflatex.
# Usage: bash build.sh [stem]        (default stem: main)
# Run from the directory holding <stem>.tex, icml2025.sty, icml2025.bst,
# macros_kit.tex, and refs.bib.
set -euo pipefail
STEM="${1:-main}"

if ! command -v pdflatex >/dev/null 2>&1; then
  echo "pdflatex not found. Install TeX Live / MacTeX first." >&2
  exit 127
fi

pdflatex -interaction=nonstopmode -halt-on-error "$STEM" >/dev/null
bibtex "$STEM" || true    # tolerate 'no \citation' on an early stub; a real paper must be clean
pdflatex -interaction=nonstopmode -halt-on-error "$STEM" >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error "$STEM"

echo "Built ${STEM}.pdf"
# One-shot alternative: latexmk -pdf -interaction=nonstopmode "$STEM"
