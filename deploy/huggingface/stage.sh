#!/usr/bin/env bash
# Stage the smallest complete offline demo tree for a Hugging Face Space upload.
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 TARGET_DIRECTORY" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
target="$1"

if [[ ! -d "$target" ]]; then
  echo "target directory does not exist: $target" >&2
  exit 2
fi

mkdir -p \
  "$target/src" \
  "$target/artifacts/tuesday" \
  "$target/artifacts/wednesday" \
  "$target/artifacts/ui" \
  "$target/corpus/frozen" \
  "$target/corpus/media"

cp "$repo_root/deploy/huggingface/app.py" "$target/app.py"
cp "$repo_root/pyproject.toml" "$target/pyproject.toml"
cp "$repo_root/deploy/huggingface/README.space.md" "$target/README.md"
cp "$repo_root/deploy/huggingface/requirements.txt" "$target/requirements.txt"
cp -R "$repo_root/src/adjacency" "$target/src/adjacency"
cp "$repo_root/artifacts/tuesday/policy_spec.json" "$target/artifacts/tuesday/"
cp "$repo_root/artifacts/tuesday/baseline_blocklist.json" "$target/artifacts/tuesday/"
cp "$repo_root/artifacts/wednesday/judge_traces.json" "$target/artifacts/wednesday/"
cp "$repo_root/artifacts/ui/economics_assumption.json" "$target/artifacts/ui/"
cp "$repo_root/corpus/frozen/manifest.json" "$target/corpus/frozen/"
cp "$repo_root/corpus/media/"*.jpg "$target/corpus/media/"

find "$target" -type d -name __pycache__ -prune -exec rm -r {} +
find "$target" -type f -name '*.pyc' -delete

echo "staged offline demo in $target"
