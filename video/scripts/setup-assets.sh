#!/usr/bin/env bash
# Recreate the public/ asset symlinks (gitignored, so needed after a fresh clone).
# Remotion's staticFile() resolves paths under public/, so we link the bot's
# per-day image + audio folders into it instead of duplicating ~260MB.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p public
ln -sfn ../../images_v2 public/images_v2
ln -sfn ../../audio_male public/audio_male

echo "Linked:"
echo "  public/images_v2  -> ../../images_v2"
echo "  public/audio_male -> ../../audio_male"
