$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$download = Join-Path $root 'build/innosetup-6.7.3.exe'
$destination = Join-Path $root 'build/inno'
New-Item -ItemType Directory -Force (Split-Path $download) | Out-Null
Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $download
if ((Get-FileHash $download -Algorithm SHA256).Hash -ne '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732') {
    throw 'Inno Setup SHA256 mismatch'
}
$signature = Get-AuthenticodeSignature $download
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|, )O=Pyrsys B\.V\.(,|$)') {
    throw 'Inno Setup publisher signature is invalid'
}
$process = Start-Process -FilePath $download -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', '/NOICONS', '/TASKS=', "/DIR=`"$destination`"") -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0 -or -not (Test-Path (Join-Path $destination 'ISCC.exe'))) {
    throw "Inno Setup installation failed: $($process.ExitCode)"
}
