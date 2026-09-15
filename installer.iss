; SwarLekh installer — per-user install (no admin rights needed), Start Menu
; shortcut, optional Desktop shortcut, optional launch-at-login, proper
; uninstaller registered in Add/Remove Programs. Does NOT touch
; %LOCALAPPDATA%\SwarLekh (API keys live in Credential Manager, not here;
; HISTORY_DIR setting and any custom save-location files are the user's data)
; on install or uninstall.

#define MyAppName "SwarLekh"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Khushaldas Vasant Badhan"
#define MyAppExeName "SwarLekh.exe"

[Setup]
AppId={{B4E9F3A2-6C1D-4E8B-9A7F-2D3C4B5A6E7F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; SwarLekh.exe itself carries the icon (Nuitka's --windows-icon-from-ico,
; embedded at build time) — point Add/Remove Programs straight at the exe
; rather than a separate .ico file that was never part of [Files] below.
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputBaseFilename=SwarLekh-Setup
OutputDir=installer_output
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=assets\swarlekh_icon.ico
WizardStyle=modern
; Without this, installing/updating/uninstalling while SwarLekh.exe is
; running shows an interactive "Setup was unable to automatically close
; all applications" Abort/Retry/Ignore dialog that is NOT suppressed by
; /VERYSILENT — confirmed live: it blocked an automated silent install and
; needed a manual click. SwarLekh is a background tray app with no
; unsaved-document risk, so force-closing it via RestartManager is safe;
; this makes Setup do that instead of prompting.
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Launch {#MyAppName} automatically when I log in"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist_nuitka\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Only remove the app's own install folder — never %LOCALAPPDATA%\SwarLekh
; (Credential Manager entries, history/, config.json settings are user data).
Type: filesandordirs; Name: "{app}"
