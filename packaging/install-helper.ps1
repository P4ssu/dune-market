# Used by Install.bat: asks for the in-game name, writes it into config.toml and makes the desktop shortcut.
param(
    [Parameter(Mandatory = $true)] [string] $Target,
    [string] $Name = $env:DUNEMARKET_NAME,                    # set only by tests: skips the question
    [string] $DesktopDir = $(if ($env:DUNEMARKET_DESKTOP) { $env:DUNEMARKET_DESKTOP } else { [Environment]::GetFolderPath("Desktop") })
)
$ErrorActionPreference = "Stop"
$placeholder = "WRITE-YOUR-NAME-HERE"
$configPath = Join-Path $Target "config.toml"
$text = Get-Content $configPath -Raw -Encoding UTF8

if ($text.Contains($placeholder)) {
    $chosen = $Name
    while (-not $chosen) {
        $chosen = (Read-Host "Your in-game name (friends see it next to the prices you scan)").Trim()
        $chosen = $chosen -replace '["\\]', ''
    }
    $text = $text.Replace($placeholder, $chosen)
    [System.IO.File]::WriteAllText($configPath, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Name saved: $chosen"
}

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $DesktopDir "Dune Market.lnk"))
$link.TargetPath = Join-Path $Target "DuneMarket.exe"
$link.WorkingDirectory = $Target
$link.IconLocation = (Join-Path $Target "DuneMarket.exe") + ",0"
$link.Description = "Dune Market price overlay"
$link.Save()
Write-Host "Desktop shortcut created."
