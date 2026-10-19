# Builds dist\DuneMarket-Setup.zip: the program, an installer and a README, with a config.toml that already
# holds the shared database address and key, so friends only type their name when installing.
#   .\packaging\make-friend-zip.ps1 -Url "https://xxxx.supabase.co" -Key "<anon public key>"
param(
    [Parameter(Mandatory = $true)] [string] $Url,
    [Parameter(Mandatory = $true)] [string] $Key,
    [string] $World = "Andromeda"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist\DuneMarket"
if (-not (Test-Path (Join-Path $dist "DuneMarket.exe"))) { throw "Build first: see packaging\README.md" }

$staging = Join-Path $root "dist\stage"
$setup = Join-Path $staging "DuneMarket-Setup"
$app = Join-Path $setup "app"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force $setup | Out-Null
Copy-Item -Recurse $dist $app

$config = (Get-Content (Join-Path $PSScriptRoot "config.friends.toml") -Raw -Encoding UTF8).Replace("{{URL}}", $Url).Replace("{{KEY}}", $Key).Replace("{{WORLD}}", $World)
[System.IO.File]::WriteAllText((Join-Path $app "config.toml"), $config, (New-Object System.Text.UTF8Encoding($false)))
Set-Content -Path (Join-Path $app "start-solid.bat") -Value "@echo off`r`ncd /d %~dp0`r`nDuneMarket.exe run --solid`r`n" -Encoding ASCII
foreach ($file in "Install.bat", "install-helper.ps1", "Uninstall.bat") { Copy-Item (Join-Path $PSScriptRoot $file) $setup }
Copy-Item (Join-Path $PSScriptRoot "README-friends.txt") (Join-Path $setup "README.txt")

$zip = Join-Path $root "dist\DuneMarket-Setup.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $setup -DestinationPath $zip -CompressionLevel Optimal
Remove-Item -Recurse -Force $staging
"{0} ({1:N0} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)
