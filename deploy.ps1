<#
.SYNOPSIS
    Full auto-deploy of the VulnShop stack to a VPS (Windows equivalent of deploy.sh).

.DESCRIPTION
    Orchestrates EVERYTHING from your Windows machine:
      1. Checks SSH connectivity
      2. Provisions the VPS (installs Docker + Compose and configures the ufw firewall)
      3. Uploads the code (tar over ssh; uses the native tar on Windows 10+)
      4. Brings the stack up with docker compose (build included)
      5. Runs end-to-end sanity checks (containers, HTTPS, cert, API, ports)

    Idempotent: re-running it re-deploys without wiping data or re-issuing the
    certificate (persisted in caddy_data, avoiding ACME rate limits).

    Requires ssh.exe and tar.exe (bundled with Windows 10 1809+ / Windows 11).

.EXAMPLE
    ./deploy.ps1
    ./deploy.ps1 -VpsHost 1.2.3.4 -Domain mydomain.xyz
#>
[CmdletBinding()]
param(
    [string]$VpsHost   = $(if ($env:VPS_HOST)   { $env:VPS_HOST }   else { "163.172.157.93" }),
    [string]$VpsUser   = $(if ($env:VPS_USER)   { $env:VPS_USER }   else { "root" }),
    [string]$Domain    = $(if ($env:DOMAIN)     { $env:DOMAIN }     else { "damnvulnerableapp.xyz" }),
    [string]$RemoteDir = $(if ($env:REMOTE_DIR) { $env:REMOTE_DIR } else { "/opt/vulnshop" })
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SshOpts   = @("-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new")
$Target    = "$VpsUser@$VpsHost"

function Log  ($m) { Write-Host "`n==> $m"  -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 1 }

function Remote([string]$Cmd) {
    # Runs a command on the VPS over SSH; exit code lands in $LASTEXITCODE.
    & ssh @SshOpts $Target $Cmd
}

# --- 0. Local preflight ---
Log "Local preflight (host=$VpsHost domain=$Domain dir=$RemoteDir)"
foreach ($bin in @("ssh", "tar", "curl")) {
    if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) { Die "$bin not available (requires Windows 10 1809+ / Windows 11)" }
}
if (-not (Test-Path "$ScriptDir/docker-compose.yml")) { Die "docker-compose.yml not found next to this script" }
if (-not (Test-Path "$ScriptDir/.env")) { Warn ".env not found in $ScriptDir (the lab needs its secrets)" }

Log "Checking SSH connection"
& ssh @SshOpts $Target "echo ok" | Out-Null
if ($LASTEXITCODE -ne 0) { Die "cannot connect over SSH to $Target" }
Ok "SSH connects to $Target"

# --- 1. Remote provisioning: Docker + firewall ---
Log "Provisioning VPS (Docker + firewall)"
$provision = @'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker via get.docker.com..."
  curl -fsSL https://get.docker.com | sh >/dev/null 2>&1
else
  echo "Docker already present: $(docker --version)"
fi
systemctl enable --now docker >/dev/null 2>&1 || true
if ! command -v rsync >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq rsync >/dev/null 2>&1 || true
fi
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
  echo "ufw firewall active (22/80/443)."
else
  echo "NOTE: ufw not available; skipping host firewall."
fi
docker --version; docker compose version
'@
$provision | & ssh @SshOpts $Target "bash -s"
if ($LASTEXITCODE -ne 0) { Die "remote provisioning failed" }
Ok "VPS provisioned"

# --- 2. Upload code (tar over ssh) ---
Log "Uploading code to ${Target}:${RemoteDir}"
$excludes = @(
    "--exclude=.git", "--exclude=node_modules", "--exclude=frontend/dist",
    "--exclude=__pycache__", "--exclude=*.pyc", "--exclude=.DS_Store"
)
# Local tar writes to stdout; ssh unpacks it on the VPS.
# --no-xattrs keeps bsdtar from emitting xattrs that GNU tar on the VPS would warn about.
& tar czf - --no-xattrs @excludes -C $ScriptDir . | & ssh @SshOpts $Target "bash -c 'mkdir -p $RemoteDir && tar xzf - -C $RemoteDir'"
if ($LASTEXITCODE -ne 0) { Die "code upload failed" }
Ok "Code synced"

# --- 3. Bring the stack up ---
Log "Building and starting the stack (docker compose up -d --build)"
Remote "bash -c 'cd $RemoteDir && docker compose up -d --build'"
if ($LASTEXITCODE -ne 0) { Die "docker compose up failed" }
Ok "Stack up"

# --- 4. Sanity checks ---
Log "Sanity checks"

# 4a. Containers running.
Write-Host -NoNewline "Waiting for containers to become healthy"
$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    # grep -c exits 1 when the count is 0; `|| true` keeps the remote cmd from failing then.
    $notUp = Remote "bash -c 'cd $RemoteDir && docker compose ps --format `"{{.State}}`" | grep -cv running || true'"
    if ("$notUp".Trim() -eq "0") { $healthy = $true; break }
    Write-Host -NoNewline "."; Start-Sleep 3
}
Write-Host ""
if ($healthy) { Ok "All containers are running" } else { Warn "Some container did not reach running" }
Remote "bash -c 'cd $RemoteDir && docker compose ps --format `"table {{.Name}}\t{{.Status}}\t{{.Ports}}`"'"

# 4b. Backend health directly.
Remote "bash -c 'curl -fsS --max-time 10 http://localhost:8000/health >/dev/null'"
if ($LASTEXITCODE -eq 0) { Ok "Backend /health responds (localhost:8000 on the VPS)" } else { Warn "Backend /health did not respond" }

# 4c. External HTTPS (with retries).
Write-Host -NoNewline "Checking external HTTPS (https://$Domain)"
$httpsOk = $false
for ($i = 0; $i -lt 20; $i++) {
    $code = (& curl -sS -o NUL -w "%{http_code}" --max-time 15 "https://$Domain/") 2>$null
    if ("$code" -eq "200") { $httpsOk = $true; break }
    Write-Host -NoNewline "."; Start-Sleep 6
}
Write-Host ""
if ($httpsOk) { Ok "https://$Domain/ -> HTTP 200" } else { Warn "https://$Domain/ did not return 200 (DNS/cert propagating?)" }

# 4d. End-to-end API.
$products = (& curl -sS --max-time 15 "https://$Domain/api/products") 2>$null
if ("$products" -match '"products"') { Ok "API /api/products returns data (backend + DB OK)" } else { Warn "/api/products did not return the expected data" }

# 4e. HTTP -> HTTPS redirect.
$rcode = (& curl -sS -o NUL -w "%{http_code}" --max-time 15 "http://$Domain/") 2>$null
if ("$rcode" -in @("308", "301", "302")) { Ok "HTTP redirects to HTTPS ($rcode)" } else { Warn "HTTP does not redirect (code $rcode)" }

# 4f. Infrastructure ports closed to the internet (best-effort via Test-NetConnection).
foreach ($p in @(5432, 6379, 8000)) {
    $open = Test-NetConnection -ComputerName $VpsHost -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($open) { Warn "Port $p OPEN to the internet (should be closed)" } else { Ok "Port $p closed to the internet" }
}

Log "Deployment complete"
Write-Host "  URL:      https://$Domain"
Write-Host "  Swagger:  https://$Domain/api/docs"
Write-Host "  VPS dir:  $RemoteDir"
