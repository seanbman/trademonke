# TradeMonke Debian package

Thin bootstrap `.deb` for Ubuntu amd64. The package installs:

- Electron shell under `/usr/lib/trademonke/desktop`
- First-run bootstrap scripts under `/usr/lib/trademonke/scripts/desktop`
- `/usr/bin/trademonke` launcher and a system desktop entry
- Default GitHub clone URL at `/usr/lib/trademonke/repo.url` (copied to `/etc/trademonke/repo.url` on install)

The application tree lives at `/opt/trademonke` as a **git clone**. Day-to-day updates use `origin/main`, not a new `.deb`.

## Build

```bash
make deb
# or: bash scripts/desktop/build-deb.sh
```

Output: `dist/trademonke_<version>_amd64.deb`

## CI

Canonical workflow: [`ci/desktop-deb.yml`](ci/desktop-deb.yml).

Install into `.github/workflows/` (requires write access / sudo if that directory is root-owned):

```bash
SYNC_WITH_SUDO=1 bash scripts/desktop/sync-ci-workflow.sh
```

On `v*` tags the workflow builds the `.deb` and attaches it to the GitHub Release.

## Install

```bash
sudo apt install ./dist/trademonke_*_amd64.deb
# then open TradeMonke from the app menu
```

See [docs/DESKTOP.md](../../docs/DESKTOP.md) for the full user flow.
