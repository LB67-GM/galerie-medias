# Cree un raccourci Bureau -> ouvrir-galerie.bat (via cmd.exe).
param(
    [Parameter(Mandatory = $true)][string]$BatPath,
    [Parameter(Mandatory = $true)][string]$WorkDir
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $BatPath)) {
    throw "Introuvable: $BatPath"
}
$BatPath = (Resolve-Path -LiteralPath $BatPath).Path
$WorkDir = (Resolve-Path -LiteralPath $WorkDir).Path

$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desk "Galerie Médias.lnk"
$s = $ws.CreateShortcut($lnkPath)
$s.TargetPath = $env:ComSpec
# /k : fenetre reste ouverte (serveur galerie)
$s.Arguments = "/k cd /d `"$WorkDir`" && `"$BatPath`""
$s.WorkingDirectory = $WorkDir
$s.WindowStyle = 1
$s.Description = "Ouvrir la galerie photos"
$s.Save()
Write-Host "Raccourci cree : $lnkPath"
Write-Host "Cible          : $($s.TargetPath)"
Write-Host "Arguments      : $($s.Arguments)"
