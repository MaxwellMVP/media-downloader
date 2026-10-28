param([Parameter(Mandatory = $true)][string]$Path)
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -LiteralPath $Path
if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or -not $signature.TimeStamperCertificate) {
    throw "Expected a trusted timestamped Authenticode signature: $Path ($($signature.Status))"
}
if ($signature.SignerCertificate.Subject -notmatch 'SignPath Foundation') {
    throw "Unexpected signing identity: $($signature.SignerCertificate.Subject)"
}
Write-Output "Verified: $Path; publisher: $($signature.SignerCertificate.Subject)"
