#!/usr/bin/env bash
# Build trademonke_*.deb into dist/.
# Usage: ./scripts/desktop/build-deb.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import json; print(json.load(open('desktop/package.json'))['version'])")"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
OUT_DIR="$ROOT/dist"
STAGING="$ROOT/packaging/deb/staging"
NFPM_VERSION="${NFPM_VERSION:-2.41.3}"

echo "==> Building TradeMonke .deb version=$VERSION arch=$ARCH"

echo "==> Installing Electron dependencies for packaging"
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to package the Electron shell" >&2
  exit 2
fi
(
  cd "$ROOT/desktop"
  npm install --omit=dev
)

echo "==> Staging package payload"
rm -rf "$STAGING"
mkdir -p "$STAGING/usr/lib/trademonke/desktop" \
  "$STAGING/usr/lib/trademonke/scripts/desktop"

# Electron shell (include node_modules/electron binary).
rsync -a --delete \
  --exclude '.gitignore' \
  "$ROOT/desktop/" "$STAGING/usr/lib/trademonke/desktop/"

# Bootstrap / launch scripts needed before /opt/trademonke exists.
for name in common.sh bootstrap.sh trademonke-launch.sh trademonke-start.sh \
  trademonke-stop.sh trademonke-update.sh trademonke-logs.sh check-update.sh \
  install-ubuntu.sh; do
  cp "$ROOT/scripts/desktop/$name" "$STAGING/usr/lib/trademonke/scripts/desktop/$name"
  chmod 0755 "$STAGING/usr/lib/trademonke/scripts/desktop/$name"
done

cp "$ROOT/packaging/deb/repo.url" "$STAGING/usr/lib/trademonke/repo.url"
chmod 0755 "$ROOT/packaging/deb/bin/trademonke"
chmod 0755 "$ROOT/packaging/deb/scripts/postinst" "$ROOT/packaging/deb/scripts/postrm"

mkdir -p "$OUT_DIR"

NFPM_BIN="${NFPM_BIN:-}"
if [[ -z "$NFPM_BIN" ]]; then
  if command -v nfpm >/dev/null 2>&1; then
    NFPM_BIN="$(command -v nfpm)"
  else
    echo "==> Downloading nfpm ${NFPM_VERSION}"
    NFPM_DIR="$ROOT/packaging/deb/.nfpm"
    mkdir -p "$NFPM_DIR"
    # Map dpkg arch → nfpm release asset arch.
    case "$ARCH" in
      amd64) NFPM_ARCH=x86_64 ;;
      arm64) NFPM_ARCH=arm64 ;;
      *) NFPM_ARCH=x86_64 ;;
    esac
    TARBALL="nfpm_${NFPM_VERSION}_Linux_${NFPM_ARCH}.tar.gz"
    URL="https://github.com/goreleaser/nfpm/releases/download/v${NFPM_VERSION}/${TARBALL}"
    curl -fsSL "$URL" -o "$NFPM_DIR/$TARBALL"
    tar -xzf "$NFPM_DIR/$TARBALL" -C "$NFPM_DIR" nfpm
    NFPM_BIN="$NFPM_DIR/nfpm"
  fi
fi

echo "==> Running nfpm"
export VERSION ARCH
# nfpm substitutes ${VERSION} / ${ARCH} from env when using envsubst-style — use sed.
TMP_CFG="$(mktemp)"
sed "s/\${VERSION}/$VERSION/g; s/\${ARCH}/$ARCH/g" "$ROOT/packaging/deb/nfpm.yaml" > "$TMP_CFG"
"$NFPM_BIN" package --config "$TMP_CFG" --target "$OUT_DIR" --packager deb
rm -f "$TMP_CFG"

DEB="$(ls -1t "$OUT_DIR"/trademonke_*.deb | head -1)"
echo "==> Built $DEB"
dpkg-deb -I "$DEB" | sed -n '1,40p'
echo "Install with: sudo apt install ./$(basename "$DEB")"
