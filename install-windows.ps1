# Install or update OpenTranscribe (transcript + speakers, pyannote.ai API, no GPU).
#
# Run from the folder holding this file:
#   powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
# Re-running is safe: secrets and the API key already in .env are kept, the
# containers are rebuilt from this folder's code and restarted.
#
# Needs Docker Desktop running. See INSTALL.md.

# Continue, not Stop: Windows PowerShell 5.1 turns a native command's stderr into a
# terminating error under Stop. Every step checks its own result instead.
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot

$EnvFile = Join-Path $PSScriptRoot '.env'
$Placeholder = 'CHANGE_ME_auto_generated_on_install'
$StartTimeoutSeconds = 900

# What this deployment is: everything else stays at the template's defaults.
$Settings = [ordered]@{
    'OT_IMAGE_TAG'               = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION') -TotalCount 1).Trim()
    'COMPOSE_FILE'               = @('docker-compose.yml', 'docker-compose.prod.yml', 'docker-compose.lite.yml', 'docker-compose.fork.yml') -join [IO.Path]::PathSeparator
    'BACKEND_BIND_HOST'          = '127.0.0.1'
    'ASR_PROVIDER'               = 'pyannote'
    'PYANNOTE_MODEL'             = 'whisper-large-v3-turbo'
    'DEFAULT_SOURCE_LANGUAGE'    = 'fr'
    'DEFAULT_AI_SUMMARY_ENABLED' = 'false'
    # Sized for one person on a 16 GB PC (template defaults target a shared server).
    # 1 GB heap is the size docker-compose.yml documents as verified for the default
    # search model.
    'OPENSEARCH_JAVA_OPTS'       = '"-Xms1g -Xmx1g"'
    'CLOUD_ASR_CONCURRENCY'      = '2'
    'CPU_WORKER_CONCURRENCY'     = '2'
    'NLP_CONCURRENCY'            = '1'
    'DOWNLOAD_CONCURRENCY'       = '1'
}

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Stop-WithError([string]$Text) { Write-Host "`nERREUR : $Text" -ForegroundColor Red; exit 1 }

function Get-RandomHex([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
function Get-RandomBase64([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

$Secrets = [ordered]@{
    'POSTGRES_PASSWORD'    = { Get-RandomHex 32 }
    'MINIO_ROOT_PASSWORD'  = { Get-RandomHex 32 }
    'JWT_SECRET_KEY'       = { Get-RandomHex 64 }
    'ENCRYPTION_KEY'       = { "opentranscribe_$(Get-RandomBase64 48)" }
    'REDIS_PASSWORD'       = { Get-RandomHex 32 }
    'OPENSEARCH_PASSWORD'  = { Get-RandomHex 32 }
    'FLOWER_PASSWORD'      = { Get-RandomHex 16 }
    'MINIO_KMS_SECRET_KEY' = { "opentranscribe-key:$(Get-RandomBase64 32)" }
}

# The leading comma stops PowerShell from unrolling the list into a fixed-size array.
function Read-EnvLines { return ,[System.Collections.Generic.List[string]]([System.IO.File]::ReadAllLines($EnvFile)) }
function Save-EnvLines($Lines) {
    [System.IO.File]::WriteAllLines($EnvFile, [string[]]$Lines, (New-Object System.Text.UTF8Encoding($false)))
}
function Get-EnvValue($Lines, [string]$Key) {
    foreach ($line in $Lines) { if ($line.StartsWith("$Key=")) { return $line.Substring($Key.Length + 1) } }
    return ''
}
function Set-EnvValue($Lines, [string]$Key, [string]$Value) {
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i].StartsWith("$Key=")) { $Lines[$i] = "$Key=$Value"; return }
    }
    $Lines.Add("$Key=$Value")
}

Write-Step 'Verification de Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithError 'Docker est introuvable. Installez Docker Desktop (voir INSTALL.md), redemarrez le PC, puis relancez ce script.'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Docker Desktop n'est pas demarre. Ouvrez Docker Desktop, attendez 'Engine running', puis relancez ce script."
}

Write-Step 'Configuration (.env)'
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination $EnvFile -ErrorAction Stop
}
$lines = Read-EnvLines
foreach ($key in $Secrets.Keys) {
    $current = Get-EnvValue $lines $key
    if ($current -eq '' -or $current -eq $Placeholder) { Set-EnvValue $lines $key (& $Secrets[$key]) }
}
foreach ($key in $Settings.Keys) { Set-EnvValue $lines $key $Settings[$key] }

if ((Get-EnvValue $lines 'INITIAL_ADMIN_PASSWORD') -eq '') {
    Set-EnvValue $lines 'INITIAL_ADMIN_PASSWORD' (Get-RandomHex 8)
}

while ((Get-EnvValue $lines 'PYANNOTE_API_KEY').Trim() -eq '') {
    Write-Host 'Collez votre cle API pyannote.ai (dashboard.pyannote.ai > API Keys), puis Entree :' -ForegroundColor Yellow
    $key = (Read-Host).Trim()
    if ($key -ne '') { Set-EnvValue $lines 'PYANNOTE_API_KEY' $key }
}
Save-EnvLines $lines

$modelsDir = Join-Path $PSScriptRoot 'models'
foreach ($sub in 'huggingface', 'torch', 'nltk_data', 'sentence-transformers', 'opensearch-ml', 'diar-native') {
    New-Item -ItemType Directory -Force -ErrorAction Stop -Path (Join-Path $modelsDir $sub) | Out-Null
}

# Same precedence as docker compose: process environment, then .env, then the default.
function Get-Port([string]$Key, [string]$Default) {
    $fromEnv = [Environment]::GetEnvironmentVariable($Key)
    if ($fromEnv) { return $fromEnv }
    $fromFile = Get-EnvValue (Read-EnvLines) $Key
    if ($fromFile) { return $fromFile }
    return $Default
}
$WebUrl = "http://localhost:$(Get-Port 'FRONTEND_PORT' '5173')"
$ReadyUrl = "http://localhost:$(Get-Port 'BACKEND_PORT' '5174')/health/ready"

Write-Step 'Construction et demarrage (premiere fois : 10 a 30 minutes selon la connexion)'
docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) { Stop-WithError 'docker compose a echoue (voir les messages ci-dessus).' }

Write-Step "Attente de la page $WebUrl"
$deadline = (Get-Date).AddSeconds($StartTimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $page = Invoke-WebRequest -Uri $WebUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        $api = Invoke-WebRequest -Uri $ReadyUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($page.StatusCode -eq 200 -and $api.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $ready) {
    Stop-WithError "La page ne repond pas apres $([int]($StartTimeoutSeconds / 60)) minutes. Envoyez la sortie de 'docker compose ps' et 'docker compose logs backend --tail 50'."
}

$lines = Read-EnvLines
Write-Host "`nOpenTranscribe est pret : $WebUrl" -ForegroundColor Green
Write-Host "  Identifiant : $(Get-EnvValue $lines 'INITIAL_ADMIN_EMAIL')"
Write-Host "  Mot de passe : $(Get-EnvValue $lines 'INITIAL_ADMIN_PASSWORD')"
Write-Host '  (ces deux valeurs restent dans le fichier .env de ce dossier)'
if ($IsWindows -or $env:OS -eq 'Windows_NT') { Start-Process $WebUrl }
