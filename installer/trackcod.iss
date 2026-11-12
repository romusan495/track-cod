; Track COD installer (Inno Setup 6). Built by `python -m tools.build`, which passes /DAppVersion and /DSourceDir.
; Per-user install, no admin rights. The player's data in %LOCALAPPDATA%\TrackCOD is never touched.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\TrackCOD"
#endif

[Setup]
AppId={{6F1C2D7A-3B54-4E8F-9A21-7C0D5E4B8F13}
AppName=Track COD
AppVersion={#AppVersion}
AppPublisher=Romusan
AppPublisherURL=https://github.com/romusan495/track-cod
AppSupportURL=https://github.com/romusan495/track-cod/issues
DefaultDirName={localappdata}\Programs\TrackCOD
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=TrackCOD-Setup-{#AppVersion}
OutputDir=..\dist
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\trackcod.ico
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\TrackCOD.exe
UninstallDisplayName=Track COD

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
; Mirror the app folder; files from an older version that are no longer shipped are removed below.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Only inside the install folder: the bundled runtime is replaced as a whole on update.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{userprograms}\Track COD"; Filename: "{app}\TrackCOD.exe"
Name: "{userdesktop}\Track COD"; Filename: "{app}\TrackCOD.exe"; Tasks: desktopicon

[Run]
; Interactive install: offer to launch at the end. Silent update: relaunch Track COD.
Filename: "{app}\TrackCOD.exe"; Description: "Lancer Track COD"; Flags: nowait postinstall skipifsilent
Filename: "{app}\TrackCOD.exe"; Flags: nowait; Check: WizardSilent
