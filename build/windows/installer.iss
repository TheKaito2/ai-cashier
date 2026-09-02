; Inno Setup 6 script for the AI Cashier Windows installer.
;   ISCC.exe build\windows\installer.iss     (APP_VERSION from the VERSION file, set by CI)
#define AppName "AI Cashier"
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2B8E-5C1E-4B7A-9A3B-AICASHIER001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Group 3, Assumption College Sriracha
AppPublisherURL=https://github.com/TheKaito2/ai-cashier
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; per-user install into the user's Programs folder: no UAC prompt, and the
; program folder stays writable-free anyway (data lives in %LOCALAPPDATA%)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=AI-Cashier-Setup-Windows
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\AI Cashier.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\AICashier\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\AI Cashier.exe"
Name: "{group}\{#AppName} (demo - no camera needed)"; Filename: "{app}\AI Cashier.exe"; Parameters: "--demo"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AI Cashier.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AI Cashier.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
