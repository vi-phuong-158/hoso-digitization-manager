$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$env:HOSO_APP_VERSION = "0.2.0"
$env:HOSO_BUILD_SHA = (& git -C $root rev-parse HEAD).Trim()
python -m PyInstaller --noconfirm --clean --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build") (Join-Path $root "HosoManager.spec")
Copy-Item -LiteralPath (Join-Path $root "docs/hoso-digitization-manager-handoff/example-config.json") -Destination (Join-Path $root "dist/HosoManager/config.example.json") -Force
Write-Output (Join-Path $root "dist/HosoManager/HosoManager.exe")
