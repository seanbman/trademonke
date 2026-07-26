## Desktop app (Ubuntu `.deb`)

For a one-click Ubuntu workstation install, see [docs/DESKTOP.md](docs/DESKTOP.md).

```bash
# Build locally, or download from GitHub Releases (v* tags)
make deb
sudo apt install ./dist/trademonke_*_amd64.deb
# Open TradeMonke from the app menu — first launch clones the repo, builds images, starts the GUI
```

Updates track `origin/main` via git inside `/opt/trademonke` (the `.deb` is a thin bootstrap).
