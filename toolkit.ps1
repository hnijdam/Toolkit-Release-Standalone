#===========================================================
# ICY Toolkit - PowerShell Menu (Release)
#===========================================================
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

# Modules laden (optioneel)
Import-Module Terminal-Icons -ErrorAction SilentlyContinue
Import-Module PSReadLine -ErrorAction SilentlyContinue

$script:ToolkitRoot = if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { (Get-Location).Path }
$script:SharedEnvPath = $null
try { Set-Location -Path $script:ToolkitRoot } catch {}

# SSH sleutel (default afkomstig uit historische toolkit backups)
$sshKey = if ($env:SSH_KEY_PATH) { $env:SSH_KEY_PATH } elseif ($env:SSH_KEY) { $env:SSH_KEY } else { "C:\Users\h.nijdam\OneDrive - I.C.Y. B.V\.ssh\ecdsa-key-20241004-openssh.pem" }

# Servers configuratie
$servers = @(
    @{ Name = "Ymir (Productie)"; HostName = "ymir.icy.nl"; User = "hnijdam" },
    @{ Name = "IcyCCCloud (Productie)"; HostName = "icycccloud.icy.nl"; User = "hnijdam" },
    @{ Name = "Dispatch (Productie)"; HostName = "dispatch.icy.nl"; User = "hnijdam" },
    @{ Name = "IcyCCAppAPI (Productie)"; HostName = "icyccappapi.icy.nl"; User = "hnijdam"; HideServices = $true },
    @{ Name = "IcyCCAppAPI (v2)"; HostName = "icyccappapiv2.icy.nl"; User = "hnijdam"; HideServices = $true; LogPath = "/var/log/wildfly/v2/production/" }
)

#====================== Helpers ==========================
function Get-FreePort {
    param (
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
            if ($listener) { try { $listener.Stop() } catch {} }
        }
    }
    throw "Geen vrije localhost-poort gevonden tussen $StartPort en $EndPort."
}

function Wait-ToolkitContinue {
    param(
        [string]$Prompt = "Druk op Enter om terug te gaan naar het menu"
    )
    Write-Host ""
    try { [Console]::CursorVisible = $true } catch {}
    Read-Host $Prompt | Out-Null
}

function Show-Menu {
    param (
        [string]$Title,
        [string[]]$Options,
        [switch]$Filter
    )
    $selection = 0
    $scrollOffset = 0
    try {
        $windowHeight = $Host.UI.RawUI.WindowSize.Height
        $windowWidth = $Host.UI.RawUI.WindowSize.Width
    } catch {
        $windowHeight = 25
        $windowWidth = 80
    }
    $listHeight = $windowHeight - 5
    if ($listHeight -lt 5) { $listHeight = 10 }
    try { [Console]::CursorVisible = $false } catch {}
    Clear-Host
    try {
        while ($true) {
            if ($selection -lt $scrollOffset) { $scrollOffset = $selection }
            elseif ($selection -ge $scrollOffset + $listHeight) { $scrollOffset = $selection - $listHeight + 1 }
            if ([Console]::IsOutputRedirected -eq $false) { try { [Console]::SetCursorPosition(0, 0) } catch { Clear-Host } } else { Clear-Host }
            Write-Host ($Title.PadRight($windowWidth - 1)) -ForegroundColor Cyan
            if ($Filter) {
                if (-not $script:__menu_filter) { $script:__menu_filter = "" }
                Write-Host ("Filter: " + $script:__menu_filter).PadRight($windowWidth - 1) -ForegroundColor Yellow
                Write-Host "Gebruik pijltjes om te navigeren, Enter om te selecteren. Typ om te filteren.".PadRight($windowWidth - 1) -ForegroundColor Gray
            } else {
                Write-Host "Gebruik pijltjes om te navigeren, Enter om te selecteren.".PadRight($windowWidth - 1) -ForegroundColor Gray
            }
            Write-Host ("-" * ($windowWidth - 1)) -ForegroundColor Gray
            if ($Filter -and $script:__menu_filter) { $display = $Options | Where-Object { $_ -match [regex]::Escape($script:__menu_filter) } } else { $display = $Options }
            for ($i = 0; $i -lt $listHeight; $i++) {
                $index = $scrollOffset + $i
                if ($index -lt $display.Count) {
                    $prefix = "   "
                    $color = "White"
                    if ($index -eq $selection) { $prefix = "-> "; $color = "Green" }
                    $text = "$prefix$($display[$index])"
                    if ($text.Length -ge $windowWidth) { $text = $text.Substring(0, $windowWidth - 1) } else { $text = $text.PadRight($windowWidth - 1) }
                    Write-Host $text -ForegroundColor $color
                } else { Write-Host "".PadRight($windowWidth - 1) }
            }
            $key = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            $vk = $key.VirtualKeyCode
            $ch = $key.Character
            if ($Filter) {
                if ($vk -eq 8) { if ($script:__menu_filter.Length -gt 0) { $script:__menu_filter = $script:__menu_filter.Substring(0, $script:__menu_filter.Length - 1) } $selection = 0; continue }
                if ($vk -eq 27) { return -1 }
                if ($vk -ne 38 -and $vk -ne 40 -and $vk -ne 13) { if ($ch -ne [char]0 -and $ch -ne "") { $script:__menu_filter += $ch; $selection = 0; continue } }
            }
            if ($vk -eq 38) { $selection--; if ($selection -lt 0) { $selection = $display.Count - 1 } }
            elseif ($vk -eq 40) { $selection++; if ($selection -ge $display.Count) { $selection = 0 } }
            elseif ($vk -eq 13) { if ($display.Count -eq 0) { return -1 } $sel = $display[$selection]; $orig = [Array]::IndexOf($Options, $sel); if ($orig -ge 0) { return $orig } else { return -1 } }
        }
    } finally { try { [Console]::CursorVisible = $true } catch {} }
}

function Invoke-Export {
    param(
        $server,
        [Alias('logFile')]
        [string[]]$logFiles,
        [string]$pattern = "",
        [string]$timeFilter = "",
        [switch]$json,
        [switch]$excel
    )
    $serverName = $server.Name
    # Maak export folder aan
    $exportFolder = Join-Path $env:USERPROFILE "Documents\ICY-Logs"
    if (-not (Test-Path $exportFolder)) { New-Item -Path $exportFolder -ItemType Directory | Out-Null }
    # Bepaal bestandsnaam
    if ($logFiles.Count -gt 1) { $mainLog = "Combined-7Days" } else { $mainLog = $logFiles[0] }
    # Bestandsnaam ISO stijl
    $timestamp = Get-Date -Format "yyyy-MM-ddTHH-mm"
    $patternSafe = if ($pattern) { "_$($pattern -replace '[^a-zA-Z0-9]', '_' )" } else { "" }
    $baseName = "$($mainLog)$patternSafe"
    $exportFile = Join-Path $exportFolder "$serverName-$baseName-$timestamp.log"
    # Bouw grep commando
    $grepCmd = ""
    if ($pattern) { $grepCmd = "grep -Eih '$pattern'" } else { $grepCmd = "cat" }
    # Tijdfilter commando
    $timeCmd = ""
    if ($timeFilter) { $timeCmd = "| grep '$timeFilter'" }
    # Ondersteun servers met een aangepast logpad via server.LogPath
    $remoteLogDir = if ($server.LogPath) { $server.LogPath } else { "/var/lib/wildfly/production/standalone/log/" }
    # Paden samenstellen
    $remotePaths = $logFiles | ForEach-Object { "$remoteLogDir$_" }
    $remotePathsStr = $remotePaths -join " "
    # Combineer commando (2>/dev/null om fouten over missende bestanden te negeren)
    $cmd = "$grepCmd $remotePathsStr 2>/dev/null $timeCmd"
    Write-Host "Export gestart naar $exportFile..." -ForegroundColor Cyan
    try {
        $remoteTemp = "/tmp/icy_export_$(Get-Random).log"
        Write-Host "Data verzamelen op server (voer sudo wachtwoord in indien nodig)..." -ForegroundColor Cyan
        ssh -t -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "sudo $cmd > $remoteTemp"
        scp -q -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName):$remoteTemp" $exportFile
        ssh -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "rm $remoteTemp"
        Write-Host "Export voltooid!" -ForegroundColor Green
        if ($json -or $excel) {
            if ((Get-Item $exportFile).Length -eq 0) { Write-Host "Waarschuwing: Het gedownloade bestand is leeg." -ForegroundColor Yellow }
            $lines = Get-Content $exportFile
            if ($lines -is [string]) { $lines = @($lines) }
            $maxRows = 1000000
            if ($excel) { if ($lines.Count -gt $maxRows) { Write-Host "Waarschuwing: Export gelimiteerd tot $maxRows rijen vanwege Excel limieten." -ForegroundColor Yellow } Write-Host "Excel bestand genereren (dit kan even duren)..." -ForegroundColor Cyan }
            Write-Host "Debug: $($lines.Count) regels ingelezen voor verwerking." -ForegroundColor DarkGray
            $parsedData = [System.Collections.Generic.List[PSCustomObject]]::new()
            $rowCount = 0
            $totalLines = $lines.Count
            for ($i = 0; $i -lt $totalLines; $i++) {
                $line = $lines[$i]
                if ($i % 5000 -eq 0) { Write-Progress -Activity "Logregels verwerken" -Status "$i / $totalLines" -PercentComplete (($i / $totalLines) * 100) }
                if ([string]::IsNullOrWhiteSpace($line)) { continue }
                if ($excel -and $rowCount -ge $maxRows) { break }
                if ($line -match '^(?<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+(?:(?<lvl>[A-Z]+)\s+)?(?<msg>.*)') {
                    $msg = $matches.msg
                    $level = if ($matches.lvl) { $matches.lvl } else { "" }
                    $account = ""
                    $req = ""
                    $tsString = $matches.ts -replace ',', '.'
                    $tsObj = $tsString
                    try { $tsObj = [DateTime]::Parse($tsString) } catch {}
                    if ($msg -match '\)\s+(?<acc>[^\s]+)\s+request\s+(?<req>.*)') { $account = $matches.acc; $req = $matches.req }
                    $parsedData.Add([PSCustomObject]@{ timestamp = $tsObj; level = $level; account = $account; request = $req; message = $msg })
                } else {
                    $parsedData.Add([PSCustomObject]@{ timestamp = ""; level = ""; account = ""; request = ""; message = $line })
                }
                $rowCount++
            }
            Write-Progress -Activity "Logregels verwerken" -Completed
        }
        if ($json) { $jsonFile = [System.IO.Path]::ChangeExtension($exportFile, ".json"); $parsedData | ConvertTo-Json -Depth 10 | Set-Content $jsonFile; Write-Host "JSON export voltooid: $jsonFile" -ForegroundColor Green; $open = Read-Host "JSON bestand openen? (J/N)"; if ($open -eq "J") { Invoke-Item $jsonFile } }
        if ($excel) {
            $excelFile = [System.IO.Path]::ChangeExtension($exportFile, ".xlsx")
            try {
                $excelApp = New-Object -ComObject Excel.Application
                $excelApp.Visible = $false
                $excelApp.DisplayAlerts = $false
                $workbook = $excelApp.Workbooks.Add()
                $sheet = $workbook.Worksheets.Item(1)
                $sheet.Cells.Item(1, 1) = "Timestamp"
                $sheet.Cells.Item(1, 2) = "Level"
                $sheet.Cells.Item(1, 3) = "Account"
                $sheet.Cells.Item(1, 4) = "Request"
                $sheet.Cells.Item(1, 5) = "Message"
                $headerRange = $sheet.Range("A1", "E1")
                $headerRange.Font.Bold = $true
                $headerRange.Font.Size = 12
                $headerRange.Borders.LineStyle = 0
                $headerRange.AutoFilter()
                $dataCount = $parsedData.Count
                if ($dataCount -gt 0) {
                    Write-Host "Debug: $dataCount rijen schrijven naar Excel..." -ForegroundColor DarkGray
                    $dataArray = [object[,]]::new($dataCount, 5)
                    for ($i = 0; $i -lt $dataCount; $i++) {
                        $item = $parsedData[$i]
                        $dataArray[$i, 0] = $item.timestamp
                        $dataArray[$i, 1] = $item.level
                        $dataArray[$i, 2] = $item.account
                        $dataArray[$i, 3] = $item.request
                        $msg = $item.message
                        if ($msg.Length -gt 32000) { $msg = $msg.Substring(0, 32000) + "..." }
                        $dataArray[$i, 4] = $msg
                    }
                    $range = $sheet.Range("A2").Resize($dataCount, 5)
                    $range.Value2 = $dataArray
                    $timeRange = $sheet.Range("A2").Resize($dataCount, 1)
                    $culture = Get-Culture
                    $decimalSep = $culture.NumberFormat.NumberDecimalSeparator
                    if ($culture.TwoLetterISOLanguageName -eq "nl") { try { $localFmt = "jjjj-mm-dd uu:mm:ss" + $decimalSep + "000"; $timeRange.NumberFormatLocal = $localFmt } catch { try { $timeRange.NumberFormatLocal = "jjjj-mm-dd uu:mm:ss.000" } catch { try { $timeRange.NumberFormatLocal = "jjjj-mm-dd uu:mm:ss" } catch {} } } } else { try { $timeRange.NumberFormat = "yyyy-mm-dd hh:mm:ss.000" } catch { try { $timeRange.NumberFormat = "yyyy-mm-dd hh:mm:ss" } catch {} } }
                    }
                $sheet.Columns.Item(1).AutoFit() | Out-Null
                $sheet.Columns.Item(2).AutoFit() | Out-Null
                $sheet.Columns.Item(3).AutoFit() | Out-Null
                $sheet.Columns.Item(4).AutoFit() | Out-Null
                $sheet.Columns.Item(5).ColumnWidth = 100
                $sheet.Columns.Item(5).WrapText = $true
                $excelApp.ActiveWindow.SplitRow = 1
                $excelApp.ActiveWindow.FreezePanes = $true | Out-Null
                $workbook.SaveAs($excelFile)
                $workbook.Close()
                $excelApp.Quit()
                [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excelApp) | Out-Null
                Write-Host "Excel export voltooid: $excelFile" -ForegroundColor Green
                $open = Read-Host "Excel bestand openen? (J/N)"
                if ($open -eq "J") { Invoke-Item $excelFile }
            } catch { Write-Host "Excel generatie mislukt: $_" -ForegroundColor Red; if ($excelApp) { $excelApp.Quit() } }
        }
        if (($json -or $excel) -and (Test-Path $exportFile)) { Remove-Item $exportFile } elseif (-not ($json -or $excel)) { $open = Read-Host "Log bestand openen? (J/N)"; if ($open -eq "J") { Invoke-Item $exportFile } }
    } catch { Write-Host "Export mislukt: $_" -ForegroundColor Red }
}

#====================== Dispatch MAC Search ==========================
function Show-DispatchSearch($server) {
    while ($true) {
        Clear-Host
        Write-Host "Dispatch Log Search - $($server.Name)" -ForegroundColor Green
        Write-Host "==================================" -ForegroundColor White
        $searchTerm = Read-Host "Voer zoekterm in (bv. laatste 4 MAC tekens '21:A4', of 'PEERED', of Regex)"
        if (-not $searchTerm) { return }
        if ($searchTerm -match '^[0-9A-Fa-f]{2}[:\\-]?[0-9A-Fa-f]{2}$') { $searchQuery = "2c971703" + ($searchTerm -replace "[:\\-]", ""); Write-Host "Gedetecteerd als MAC-fragment. Zoeken naar volledig MAC: $searchQuery" -ForegroundColor Yellow } else { $searchQuery = $searchTerm; Write-Host "Zoeken naar tekst/regex: $searchQuery" -ForegroundColor Yellow }
        $options = @("Eenmalig zoeken", "Live volgen (tail -f)", "Terug")
        $selection = Show-Menu -Title "Kies modus voor '$searchQuery'" -Options $options
        if ($selection -eq 2) { return }
        if ($selection -eq 0) { ssh -t -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "grep -Ei '$searchQuery' /var/log/dispatch/dispatch.log | tail -n 20"; Pause }
        elseif ($selection -eq 1) { Write-Host "Live volgen gestart, druk CTRL+C om te stoppen..." -ForegroundColor Cyan; ssh -t -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "tail -f /var/log/dispatch/dispatch.log | grep -Ei --line-buffered --color=always '$searchQuery'" }
    }
}

#====================== ICYCCAppAPI Log Browser ==========================
function Show-IcyCCAppAPILog($server) {
    while ($true) {
        Clear-Host
        Write-Host "ICYCCAppAPI Log Browser - $($server.Name)" -ForegroundColor Green
        Write-Host "==================================" -ForegroundColor White
        $remoteLogDir = if ($server.LogPath) { $server.LogPath } else { "/var/lib/wildfly/production/standalone/log/" }
        $files = ssh -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "ls -1 $remoteLogDir" 2>$null
        if (-not $files) { Write-Host "Geen logbestanden gevonden!" -ForegroundColor Red; Pause; return }
        $menuOptions = @()
        $menuOptions += $files
        $menuOptions += "Terug"
        $selection = Show-Menu -Title "Kies een logbestand" -Options $menuOptions -Filter
        if ($selection -eq $files.Count) { return }
        $selectedFile = $files[$selection]
        Write-Host "Geselecteerd: $selectedFile" -ForegroundColor Cyan
        while ($true) {
            $actionOptions = @("Live volgen (tail -f)", "Zoeken (multi-keyword regex)", "Export log", "Terug")
            $actionSelection = Show-Menu -Title "Acties voor $selectedFile" -Options $actionOptions
            if ($actionSelection -eq 3) { break }
            switch ($actionSelection) {
                0 {
                    $keyword = Read-Host "Optioneel zoekfilter voor live (spatie gescheiden)"
                    $pattern = if ($keyword) { ($keyword -split '\\s+') -join '|' } else { "" }
                    $tailCmd = "tail -f $remoteLogDir$selectedFile"
                    if ($pattern) { $tailCmd += " | grep -Ei --line-buffered --color=always '$pattern'" }
                    Write-Host "Live volgen gestart, CTRL+C om te stoppen..." -ForegroundColor Cyan
                    ssh -t -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" "sudo $tailCmd"
                }
                1 {
                    $keyword = Read-Host "Voer zoekwoorden in (spatie gescheiden)"
                    if (-not $keyword) { continue }
                    $pattern = ($keyword -split '\\s+') -join '|'
                    Write-Host "Zoeken naar '$pattern' in $selectedFile..." -ForegroundColor Yellow
                    $remoteFile = "$remoteLogDir$selectedFile"
                    $cmd = "sudo grep -Ei --color=always '$pattern' $remoteFile | tail -n 100"
                    ssh -t -o GSSAPIAuthentication=no -i $sshKey "$($server.User)@$($server.HostName)" $cmd
                    $exportChoice = Read-Host "Wil je deze zoekresultaten exporteren? (J/N)"
                    if ($exportChoice -eq "J") {
                        $formatOptions = @("Standaard (.log)", "JSON (.json)", "Excel (.xlsx) - Geformatteerd", "Terug")
                        $formatSelection = Show-Menu -Title "Kies export formaat" -Options $formatOptions
                        if ($formatSelection -eq 3) { continue }
                        $json = $false; $excel = $false
                        if ($formatSelection -eq 1) { $json = $true }
                        if ($formatSelection -eq 2) { $excel = $true }
                        Invoke-Export -server $server -logFiles @($selectedFile) -pattern $pattern -json:$json -excel:$excel
                    }
                    Pause
                }
                2 {
                    $timeOptions = @("Laatste 10 minuten", "Laatste 1 uur", "Vandaag", "Afgelopen 7 dagen", "Geen tijdsfilter (hele bestand)", "Terug")
                    $timeSelection = Show-Menu -Title "Kies tijdsfilter" -Options $timeOptions
                    if ($timeSelection -eq 5) { continue }
                    $logFilesToExport = @($selectedFile)
                    switch ($timeSelection) {
                        0 { $timeFilter = (Get-Date).AddMinutes(-10).ToString("yyyy-MM-dd") }
                        1 { $timeFilter = (Get-Date).AddHours(-1).ToString("yyyy-MM-dd") }
                        2 { $timeFilter = (Get-Date).ToString("yyyy-MM-dd") }
                        3 {
                            $timeFilter = ""
                            $baseName = $selectedFile -replace '\\.\d{4}-\\d{2}-\\d{2}$', ''
                            $logFilesToExport = @()
                            for ($d = 6; $d -ge 1; $d--) { $dateStr = (Get-Date).AddDays(-$d).ToString("yyyy-MM-dd"); $logFilesToExport += "$baseName.$dateStr" }
                            $logFilesToExport += $baseName
                        }
                        4 { $timeFilter = "" }
                        default { $timeFilter = "" }
                    }
                    $formatOptions = @("Standaard (.log)", "JSON (.json)", "Excel (.xlsx) - Geformatteerd", "Terug")
                    $formatSelection = Show-Menu -Title "Kies export formaat" -Options $formatOptions
                    if ($formatSelection -eq 3) { continue }
                    $json = $false; $excel = $false
                    if ($formatSelection -eq 1) { $json = $true }
                    if ($formatSelection -eq 2) { $excel = $true }
                    Invoke-Export -server $server -logFiles $logFilesToExport -timeFilter $timeFilter -json:$json -excel:$excel
                    Pause
                }
            }
        }
    }
}

# Minimal release footer: do not call external helpers from this trimmed release copy.
# If you need the full runtime, run the canonical toolkit which defines `Import-ToolkitEnv`.
if ($env:SSH_KEY_PATH) { $sshKey = $env:SSH_KEY_PATH } elseif ($env:SSH_KEY) { $sshKey = $env:SSH_KEY }
Write-Host "Toolkit-Release script restored." -ForegroundColor Green

# Try to locate the canonical toolkit (sibling 'Toolkit' folder) and run it so the full menu is available.
try {
    $parent = $null
    if ($script:ToolkitRoot) { $parent = Split-Path -Parent $script:ToolkitRoot -ErrorAction SilentlyContinue }
    if (-not $parent) { $parent = (Get-Location).Path }
    $canonical = Join-Path $parent "Toolkit\toolkit.ps1"
    if (Test-Path $canonical) {
        Write-Host "Found canonical toolkit at: $canonical — starting full menu..." -ForegroundColor Cyan
        . $canonical
        return
    } else {
        Write-Host "Canonical toolkit not found at: $canonical" -ForegroundColor Yellow
        Write-Host "To run the full interactive menu, run the canonical toolkit: Toolkit\toolkit.ps1" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Unable to start canonical toolkit: $_" -ForegroundColor Red
}
