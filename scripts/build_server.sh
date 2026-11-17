#!/bin/sh
# Builds bunker-server, Bunker's Lunar Tear server as one program, for every
# desktop platform: build_server.sh <output directory> [version].
# Run scripts/prepare.py and `make -C server proto` first. The server holds no
# C code (its SQLite is Go), so each target cross-compiles from any host.
set -eu
out=$(mkdir -p "$1" && cd "$1" && pwd)
root=$(cd "$(dirname "$0")/.." && pwd)
version=${2:-$(cat "$root/VERSION")}
cd "$root/server"
for target in windows:amd64:windows-x86_64.exe windows:arm64:windows-arm64.exe \
              linux:amd64:linux-x86_64 linux:arm64:linux-arm64 \
              darwin:amd64:macos-x86_64 darwin:arm64:macos-arm64; do
  os=${target%%:*}; rest=${target#*:}
  CGO_ENABLED=0 GOOS=$os GOARCH=${rest%%:*} go build -trimpath \
    -ldflags "-s -w -X lunar-tear/server/internal/bunkerversion.Version=$version" \
    -o "$out/bunker-server-$version-${rest#*:}" ./cmd/bunker-server
done
