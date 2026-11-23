#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
asset='@ASSET@'
digest='@SHA256@'
version='@VERSION@'
if [[ $(uname -sm) != 'Linux x86_64' ]]; then
    echo 'This build requires x86-64 Linux.' >&2
    exit 1
fi
mkdir -p .reincomp
exec 9>.reincomp/play.lock
flock -n 9 || { echo 'This installation is already running.' >&2; exit 1; }
runtime="$PWD/.reincomp/$digest"
if [[ ! -d "$runtime" ]]; then
    temp=$(mktemp -d "$PWD/.reincomp/install.XXXXXXXX")
    trap 'rm -rf -- "$temp"' EXIT
    if [[ -f "$asset" ]]; then
        archive="$PWD/$asset"
    else
        archive="$temp/$asset"
        echo "Downloading the native Linux runtime $version…"
        curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
            "https://github.com/veritr1x/reincomp/releases/download/v$version/$asset" --output "$archive"
    fi
    printf '%s  %s\n' "$digest" "$asset" | (cd -- "$(dirname -- "$archive")" && sha256sum --check --status) || {
        echo 'The Linux runtime failed its SHA-256 check.' >&2; exit 1;
    }
    mkdir "$temp/runtime"
    tar --no-same-owner -xzf "$archive" -C "$temp/runtime"
    mv -- "$temp/runtime" "$runtime"
    rm -rf -- "$temp"
    trap - EXIT
fi
export PATH="$runtime/python/bin:$PATH" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME PYTHONPATH
exec "$runtime/python/bin/python3" "$runtime/tools/web_launch.py" "$@"
