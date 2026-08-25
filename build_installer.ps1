$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
& (Join-Path $root "build_manager.ps1")
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    if (Test-Path "D:\Inno Setup 6\ISCC.exe") {
        $iscc = Get-Item "D:\Inno Setup 6\ISCC.exe"
    } elseif (Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") {
        $iscc = Get-Item "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    } else {
        throw "Inno Setup Compiler (ISCC.exe) was not found. Install Inno Setup and retry build_installer.ps1."
    }
}
$isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
& $isccPath (Join-Path $root "installer\HosoManager.iss")
Write-Output (Join-Path $root "dist\installer\HosoManager-Setup-v0.2.0.exe")
