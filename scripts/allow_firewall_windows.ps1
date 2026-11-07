# Ouvre le port 8765 dans le pare-feu Windows (regles permanentes, survivent au reboot).
# netsh advfirewall ecrit dans la politique Windows, pas seulement la session.
# UAC seulement si la regle port manque. Si refuse : galerie OK sur cet ordinateur.
$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$Marker = Join-Path $Root ".firewall-ok"
$rulePort = "Galerie Médias 8765"
$ruleCast = "Galerie Médias TV 8766"
$rulePy = "Galerie Médias Python"

function Test-FwRule([string]$Name) {
    $out = (netsh advfirewall firewall show rule name="$Name" 2>&1 | Out-String)
    if ($out -match 'No rules match' -or $out -match 'Aucune r') { return $false }
    return ($out -match [regex]::Escape($Name))
}

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdmin) {
    if ((Test-FwRule $rulePort) -and (Test-FwRule $ruleCast)) {
        New-Item -ItemType File -Path $Marker -Force | Out-Null
        exit 0
    }
    $self = $MyInvocation.MyCommand.Path
    try {
        Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $self
        )
    } catch {
        New-Item -ItemType File -Path $Marker -Force | Out-Null
        exit 0
    }
    if ((Test-FwRule $rulePort) -and (Test-FwRule $ruleCast)) {
        New-Item -ItemType File -Path $Marker -Force | Out-Null
    }
    exit 0
}

netsh advfirewall firewall delete rule name="$rulePort" | Out-Null
netsh advfirewall firewall add rule name="$rulePort" dir=in action=allow protocol=TCP localport=8765 enable=yes profile=private,domain description="Galerie Médias (port 8765, permanent)"
netsh advfirewall firewall delete rule name="$ruleCast" | Out-Null
netsh advfirewall firewall add rule name="$ruleCast" dir=in action=allow protocol=TCP localport=8766 enable=yes profile=private,domain description="Galerie Médias TV DLNA (port 8766, permanent)"

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    netsh advfirewall firewall delete rule name="$rulePy" | Out-Null
    netsh advfirewall firewall add rule name="$rulePy" dir=in action=allow program="$py" enable=yes profile=private,domain
}

New-Item -ItemType File -Path $Marker -Force | Out-Null
exit 0
