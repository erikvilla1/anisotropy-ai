#!/usr/bin/env bash
# Installs Ubuntu packages on a CI runner from the .deb files GitHub's cache gave back, and only when it gave none (or they no
# longer install) from Ubuntu's archive, keeping what it downloads for the cache to save (ADR-0114 amendment 2). The archive's mirror
# on GitHub's runners now and then takes 5 to 27 minutes for what usually takes 20 seconds; the cache skips it.
#
#   scripts/ci-apt-install.sh <deb folder> <package> ...
#
# The cache's key names the runner's image (ImageOS, ImageVersion), so a new image downloads once and keeps its own set.
set -euo pipefail
debs="$1"
shift
mkdir -p "$debs/partial"
if compgen -G "$debs/*.deb" > /dev/null && sudo dpkg -i "$debs"/*.deb; then
  echo "installed $* from the cache ($(ls "$debs"/*.deb | wc -l) packages)"
else
  sudo apt-get update
  # Dir::Cache::Archives puts every package this install downloads, the ones the image lacks, in the folder the cache saves.
  # APT::Sandbox::User=root: apt's own download user cannot write into the runner's home folder.
  sudo apt-get install -y -o Dir::Cache::Archives="$debs" -o APT::Sandbox::User=root "$@"
  sudo chown -R "$(id -u):$(id -g)" "$debs"
  echo "installed $* from Ubuntu's archive ($(ls "$debs"/*.deb | wc -l) packages kept for the cache)"
fi
