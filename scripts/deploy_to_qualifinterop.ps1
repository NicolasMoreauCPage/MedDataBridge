<#
Deploy to qualifinterop.cpage.cloud

Usage: run this from the repository root. The script will locate the latest
`meddatabridge-deployment-*.zip` archive (or regenerate it), upload it to the
remote host and run the remote deploy script.

It will try to use `scp`/`ssh` (OpenSSH) if available. If not found, it will
fall back to PuTTY's `pscp.exe` and `plink.exe` if they are on PATH.

NOTE: This script will ask for the remote account password if needed. For
security and reusability prefer SSH key authentication.
#>

param(
    [string]$RemoteUser = "cpage",
    [string]$RemoteHost = "qualifinterop.cpage.cloud",
    [string]$RemotePath = "/home/cpage/meddatabridge-deploy",
    [string]$LocalArchive = "",
    [string]$Password = "cpage"  # optional plain-text password (internal env only)
)

Set-StrictMode -Version Latest

# Run from repository root (parent directory of the scripts folder)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Push-Location -Path $repoRoot.Path

function Find-LatestArchive {
    $zip = Get-ChildItem -Path . -Filter "meddatabridge-deployment-*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    return $zip
}


# Ensure we have an archive (generate if needed)
if (-not $LocalArchive -or -not (Test-Path $LocalArchive)) {
    Write-Host "Génération d'une nouvelle archive de déploiement..." -ForegroundColor Yellow
    python deploy_now.py
    $local = Find-LatestArchive
    if (-not $local) { throw "Impossible de créer l'archive de déploiement." }
    $LocalArchive = $local.FullName
} else {
    Write-Host "Utilisation de l'archive existante: $LocalArchive" -ForegroundColor Yellow
    $response = Read-Host "Voulez-vous générer une nouvelle archive à jour? (o/N)"
    if ($response -eq "o" -or $response -eq "O") {
        Write-Host "Génération d'une nouvelle archive..." -ForegroundColor Yellow
        python deploy_now.py
        $local = Find-LatestArchive
        if (-not $local) { throw "Impossible de créer l'archive de déploiement." }
        $LocalArchive = $local.FullName
    }
}

Write-Host "Archive à déployer: $LocalArchive"

# Prefer scp (OpenSSH) but allow pscp as fallback
$useScp = (Get-Command scp -ErrorAction SilentlyContinue) -ne $null
$usePscp = (Get-Command pscp.exe -ErrorAction SilentlyContinue) -ne $null

if (-not $useScp -and -not $usePscp) {
    Write-Warning "Ni 'scp' ni 'pscp' introuvable. Installez OpenSSH client ou PuTTY (pscp/plink)."
    Pop-Location
    exit 1
}

# Prompt for remote password (used for both scp/ssh and for sudo via stdin piping).
$plainPw = $null
if ($Password -and $Password.Length -gt 0) {
    $plainPw = $Password
} else {
    $securePw = Read-Host -Prompt "Mot de passe pour $RemoteUser@$RemoteHost (sera utilisé pour scp/ssh et sudo)" -AsSecureString
    $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($securePw)
    $plainPw = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($ptr)
}

$zipName = Split-Path -Leaf $LocalArchive

Write-Host "Upload du zip vers /tmp sur le serveur..."
if ($useScp) {
    scp "$LocalArchive" "${RemoteUser}@${RemoteHost}:/tmp/$zipName"
} else {
    & pscp.exe -pw $plainPw "$LocalArchive" "${RemoteUser}@${RemoteHost}:/tmp/$zipName"
}

Write-Host "Exécution distante: unzip vers /opt/meddata-bridge et redémarrage du service (sudo)."

# Remote command: unzip to /opt/meddata-bridge, restart service, then cleanup /tmp
# Note: Using echo with password for sudo (this is for internal test env only)
$remoteCmd = "echo '$plainPw' | sudo -S unzip -o /tmp/$zipName -d /opt/meddata-bridge/ && echo '$plainPw' | sudo -S systemctl restart meddata-bridge && rm -f /tmp/$zipName"

if ($useScp) {
    # Execute remote command via ssh
    Write-Host "Running remote command on ${RemoteUser}@${RemoteHost}"
    ssh "${RemoteUser}@${RemoteHost}" "$remoteCmd"
} else {
    # pscp/plink path: plink can accept -pw and run remote commands
    & plink.exe -pw $plainPw "${RemoteUser}@${RemoteHost}" "$remoteCmd"
}

Write-Host "Vérification du statut du service..."
if ($useScp) {
    ssh "${RemoteUser}@${RemoteHost}" "echo '$plainPw' | sudo -S systemctl status meddata-bridge --no-pager | head -n 5"
} else {
    & plink.exe -pw $plainPw "${RemoteUser}@${RemoteHost}" "echo '$plainPw' | sudo -S systemctl status meddata-bridge --no-pager | head -n 5"
}

Write-Host "Déploiement terminé." -ForegroundColor Green

Pop-Location
