#ifndef AppVersion
  #define AppVersion "0.3"
#endif
#define RootDir AddBackslash(SourcePath) + "..\.."
#ifndef ReleaseDir
  #define ReleaseDir RootDir + "\Release\v" + AppVersion
#endif

[Setup]
AppId={{F40C76F9-779C-4536-A803-6DD0BD2AC8DF}
AppName=Media Downloader
AppVersion={#AppVersion}
VersionInfoProductName=Media Downloader
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
AppMutex=Local\MediaDownloader
AppVerName=Media Downloader v{#AppVersion}
DefaultDirName={localappdata}\Programs\Media Downloader
DefaultGroupName=Media Downloader
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=MediaDownloader-v{#AppVersion}-Setup
SetupIconFile={#RootDir}\assets\app.ico
UninstallDisplayIcon={app}\MediaDownloader.exe
LicenseFile={#RootDir}\LICENSE
WizardStyle=modern dark
Compression=none
SolidCompression=no
CloseApplications=yes
RestartApplications=no
CreateUninstallRegKey=not IsTestMode

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RootDir}\Portable\MediaDownloader.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\third_party\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Media Downloader"; Filename: "{app}\MediaDownloader.exe"; Check: not IsTestMode
Name: "{group}\{cm:UninstallProgram,Media Downloader}"; Filename: "{uninstallexe}"; Check: not IsTestMode
Name: "{autodesktop}\Media Downloader"; Filename: "{app}\MediaDownloader.exe"; Tasks: desktopicon; Check: not IsTestMode

[Run]
Filename: "{app}\MediaDownloader.exe"; Description: "{cm:LaunchProgram,Media Downloader}"; Flags: nowait postinstall skipifsilent; Check: not IsTestMode

[Code]
function IsTestMode: Boolean;
begin
  Result := ExpandConstant('{param:TestMode|0}') = '1';
end;
