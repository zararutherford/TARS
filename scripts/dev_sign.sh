#!/usr/bin/env bash
# Sign dist/TARS.app with a stable self-signed identity so TCC grants persist across builds.
# Never ad-hoc (`codesign -s -`): each ad-hoc build is a new app to TCC and re-prompts.
#
# Usage: scripts/dev_sign.sh [path/to/TARS.app]
# First run creates the "TARS Dev" identity in the login keychain. macOS may show one or two
# Keychain dialogs (import, trust); accept them once.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
app="${1:-$root/dist/TARS.app}"
identity="TARS Dev"
keychain="$HOME/Library/Keychains/login.keychain-db"

have_identity() {
  security find-identity -v -p codesigning "$keychain" 2>/dev/null | grep -q "\"$identity\""
}

if ! have_identity; then
  echo "creating self-signed identity \"$identity\" in the login keychain"
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
    -keyout "$work/key.pem" -out "$work/cert.pem" \
    -subj "/CN=$identity/O=TARS" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=critical,codeSigning" \
    -addext "basicConstraints=critical,CA:FALSE" >/dev/null 2>&1
  openssl pkcs12 -export -legacy -out "$work/tars-dev.p12" -inkey "$work/key.pem" -in "$work/cert.pem" \
    -name "$identity" -passout pass:tars-dev 2>/dev/null \
    || openssl pkcs12 -export -out "$work/tars-dev.p12" -inkey "$work/key.pem" -in "$work/cert.pem" \
      -name "$identity" -passout pass:tars-dev
  security import "$work/tars-dev.p12" -k "$keychain" -P tars-dev -f pkcs12 \
    -T /usr/bin/codesign -T /usr/bin/security >/dev/null
  # Trust the certificate for code signing (user trust settings; may prompt once).
  security add-trusted-cert -r trustRoot -p codeSign -k "$keychain" "$work/cert.pem"
  if ! have_identity; then
    echo "identity \"$identity\" was imported but is not valid for code signing" >&2
    exit 1
  fi
fi

[ -d "$app" ] || { echo "no app bundle at $app; run scripts/bundle_app.sh first" >&2; exit 1; }
codesign --force --sign "$identity" --timestamp=none --identifier com.zararutherford.tars "$app"
codesign --verify --strict --verbose=2 "$app"
echo "signed $app with \"$identity\""
