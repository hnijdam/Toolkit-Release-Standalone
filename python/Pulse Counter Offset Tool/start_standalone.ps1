$ErrorActionPreference = 'Stop'

function Get-FreePort {
    param(
        [int]$StartPort = 8501,
        [int]$EndPort = 8520
    )

    for ($port = $StartPort; $port -le $EndPort; $port++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            $listener.Start()
            return $port
        }
        catch {
            continue
        }
        finally {
            if ($listener) {
                try { $listener.Stop() } catch {}
            }
        }
    }

    throw "Geen vrije poort gevonden tussen $StartPort en $EndPort."
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process -and $Process.HasExited) {
            return $false
        }

        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
        }

        Start-Sleep -Milliseconds 500
    }

    return $false
}

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $toolRoot

$venvDir = Join-Path $toolRoot '.venv'
$pythonExe = Join-Path $venvDir 'Scripts\python.exe'
$appPath = Join-Path $toolRoot 'pulse_counter_offset_tool.py'
$requirementsPath = Join-Path $toolRoot 'requirements.txt'
$envExamplePath = Join-Path $toolRoot '.env.example'
$envPath = Join-Path $toolRoot '.env'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.10+ is niet gevonden. Installeer eerst Python en start daarna dit script opnieuw.'
}

if (-not (Test-Path $venvDir)) {
    Write-Host 'Virtuele omgeving aanmaken...'
    python -m venv $venvDir
}

Write-Host 'Dependencies installeren of bijwerken...'
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r $requirementsPath

if (-not (Test-Path $envPath) -and (Test-Path $envExamplePath)) {
    Copy-Item $envExamplePath $envPath
    Write-Host ''
    Write-Host 'Er is een lokale .env aangemaakt op basis van .env.example.' -ForegroundColor Yellow
    Write-Host 'Vul daarin eventueel je databasegegevens in, of vul ze later in de app in.' -ForegroundColor Yellow
    Write-Host ''
}

$port = Get-FreePort
$toolUrl = "http://127.0.0.1:$port"
$streamlitArgs = "-m streamlit run `"$appPath`" --server.headless true --server.address 127.0.0.1 --server.port $port"

Write-Host "De ICY Offset Tool wordt gestart op $toolUrl" -ForegroundColor Green
Write-Host 'Browser wordt automatisch geopend zodra de app reageert...' -ForegroundColor Yellow

$streamlitProcess = Start-Process -FilePath $pythonExe -WorkingDirectory $toolRoot -ArgumentList $streamlitArgs -NoNewWindow -PassThru

if (-not (Wait-ForUrl -Url $toolUrl -Process $streamlitProcess -TimeoutSeconds 45)) {
    if (-not $streamlitProcess.HasExited) {
        try { Stop-Process -Id $streamlitProcess.Id -Force } catch {}
    }
    throw "De app startte niet correct op $toolUrl. Controleer de melding hierboven."
}

Start-Process $toolUrl | Out-Null
Write-Host "Browser geopend op $toolUrl" -ForegroundColor Green

Wait-Process -Id $streamlitProcess.Id
$streamlitProcess.Refresh()
exit $streamlitProcess.ExitCode
