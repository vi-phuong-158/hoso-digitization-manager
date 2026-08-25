#define MyAppName "Hồ sơ Digitization Manager"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Hồ sơ Digitization Manager"
#define MyAppExeName "HosoManager.exe"

[Setup]
AppId={{A0C2B7F0-6F65-4B31-9A22-2E8A5E9C2A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\HosoManager
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=HosoManager-Setup-v{#MyAppVersion}
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\HosoManager\*"; DestDir: "{app}"; Excludes: "config.json,*.db,*.sqlite,*.sqlite-wal,*.sqlite-shm,*.lock"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Tạo shortcut trên Desktop"; GroupDescription: "Shortcut bổ sung:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Mở {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\HosoManager.lock"
