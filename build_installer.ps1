$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
& (Join-Path $root "build_manager.ps1")
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    throw "Không tìm thấy Inno Setup Compiler (ISCC.exe). Cài Inno Setup rồi chạy lại build_installer.ps1."
}
& $iscc.Source (Join-Path $root "installer\HosoManager.iss")
Write-Output (Join-Path $root "dist\installer\HosoManager-Setup-v0.2.0.exe")
