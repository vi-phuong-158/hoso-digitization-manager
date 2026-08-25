# Windows packaging

Build from the repository root:

```powershell
./build_manager.ps1
```

Artifact:

```text
dist/HosoManager/HosoManager.exe
```

The Phase 11 installer is built with `./build_installer.ps1` when Inno Setup's
`ISCC.exe` is installed. It creates
`dist/installer/HosoManager-Setup-v0.2.0.exe`, installs to the per-user
`%LOCALAPPDATA%\Programs\HosoManager` location, and deliberately excludes
`config.json`, SQLite databases, locks, and all external PDF data.

The onedir bundle includes the official `document_types.json`, Jinja templates,
and local CSS. On first launch it creates `config.json` and `data/manager.db`
next to the executable. Set `data_root` in `config.json` to the operator's
source folder. When running from source, use ignored `config.local.json` or
`HOSO_DATA_ROOT`; the environment variable takes precedence over the file.
The application binds to `127.0.0.1`, waits for `/health` before opening the
browser, and needs no development server command or Internet access at runtime.

Packaging is intentionally onedir for a transparent, repairable local pilot;
the source PDF tree is never copied into SQLite or rewritten by the Manager.
