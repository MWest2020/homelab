#!/usr/bin/env bash
# Installs the pinned external scanners for the weekly security report into
# ~/.local/share/security-report (no root, no containers: rootless podman does
# not work on agent-lxc). Every download is checked against a pinned sha256;
# a mismatch aborts. Idempotent: an installed version is left alone.
#
# Python dependencies (sslyze, httpx, zaproxy, maxminddb) are pinned in
# pyproject.toml / uv.lock and installed by `uv run`, not here.
set -euo pipefail

DEST="${SECREPORT_TOOLS:-$HOME/.local/share/security-report}"
mkdir -p "$DEST/bin" "$DEST/dl"

NUCLEI_VERSION=3.11.1
NUCLEI_SHA256=ea63d4ae232808cd7c6bc00d0142428e231fab59dae01042246097d195835ab6
TEMPLATES_VERSION=10.5.2
TEMPLATES_SHA256=016b7abbf931d4d1a851a5a568e44510dc61691dc8a5202e3b24e701515ec574
ZAP_VERSION=2.17.0
ZAP_SHA256=94c8f767b1c2e94f0db66b3ae56514d5e3f5a728ee1b6c798e0c8fe2d61fbff0

fetch() {  # url sha256 out
  local url=$1 sum=$2 out=$3
  if [[ -f $out ]] && echo "$sum  $out" | sha256sum -c --status; then return; fi
  curl -fsSL --retry 3 -o "$out.part" "$url"
  echo "$sum  $out.part" | sha256sum -c --status || { echo "sha256 mismatch: $url" >&2; rm -f "$out.part"; exit 1; }
  mv "$out.part" "$out"
}

# nuclei (static Go binary)
if [[ "$("$DEST/bin/nuclei" -version 2>&1 | grep -o "v$NUCLEI_VERSION" | head -1)" != "v$NUCLEI_VERSION" ]]; then
  fetch "https://github.com/projectdiscovery/nuclei/releases/download/v$NUCLEI_VERSION/nuclei_${NUCLEI_VERSION}_linux_amd64.zip" \
    "$NUCLEI_SHA256" "$DEST/dl/nuclei.zip"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extract('nuclei', sys.argv[2])" "$DEST/dl/nuclei.zip" "$DEST/bin"
  chmod +x "$DEST/bin/nuclei"
fi

# nuclei templates, a pinned release (no auto-update during a run)
if [[ ! -f "$DEST/nuclei-templates/.version-$TEMPLATES_VERSION" ]]; then
  fetch "https://github.com/projectdiscovery/nuclei-templates/archive/refs/tags/v$TEMPLATES_VERSION.tar.gz" \
    "$TEMPLATES_SHA256" "$DEST/dl/nuclei-templates.tgz"
  rm -rf "$DEST/nuclei-templates" && mkdir -p "$DEST/nuclei-templates"
  tar -xzf "$DEST/dl/nuclei-templates.tgz" -C "$DEST/nuclei-templates" --strip-components=1
  touch "$DEST/nuclei-templates/.version-$TEMPLATES_VERSION"
fi

# OWASP ZAP (Java; agent-lxc has OpenJDK 17)
if [[ ! -x "$DEST/zap/zap.sh" || ! -f "$DEST/zap/.version-$ZAP_VERSION" ]]; then
  fetch "https://github.com/zaproxy/zaproxy/releases/download/v$ZAP_VERSION/ZAP_${ZAP_VERSION}_Crossplatform.zip" \
    "$ZAP_SHA256" "$DEST/dl/zap.zip"
  rm -rf "$DEST/zap" "$DEST/dl/zap-unpack" && mkdir -p "$DEST/dl/zap-unpack"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$DEST/dl/zap.zip" "$DEST/dl/zap-unpack"
  mv "$DEST/dl/zap-unpack/ZAP_$ZAP_VERSION" "$DEST/zap" && rm -rf "$DEST/dl/zap-unpack"
  chmod +x "$DEST/zap/zap.sh"
  touch "$DEST/zap/.version-$ZAP_VERSION"
fi

# The downloads are no longer needed once unpacked.
rm -f "$DEST/dl/zap.zip" "$DEST/dl/nuclei-templates.tgz"

echo "nuclei $NUCLEI_VERSION, templates $TEMPLATES_VERSION, ZAP $ZAP_VERSION in $DEST"
