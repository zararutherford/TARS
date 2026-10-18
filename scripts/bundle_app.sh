#!/usr/bin/env bash
# Build TARS.app from the SwiftPM package into dist/TARS.app.
# Usage: scripts/bundle_app.sh [debug|release]   (default: release)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
config="${1:-release}"
app="$root/dist/TARS.app"

(cd "$root/swift" && swift build -c "$config" --product TARSApp)
bin="$(cd "$root/swift" && swift build -c "$config" --show-bin-path)/TARSApp"

rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$bin" "$app/Contents/MacOS/TARSApp"
cp "$root/swift/Resources/Info.plist" "$app/Contents/Info.plist"
printf 'APPL????' > "$app/Contents/PkgInfo"
echo "bundled $app ($config)"
