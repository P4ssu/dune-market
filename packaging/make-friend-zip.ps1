# Builds dist\DuneMarket-friends.zip: the program folder plus a config.toml that already holds
# the shared database address and key, so friends only type their own name.
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

$stage = Join-Path $root "dist\stage\DuneMarket"
if (Test-Path (Split-Path $stage)) { Remove-Item -Recurse -Force (Split-Path $stage) }
Copy-Item -Recurse $dist $stage

$config = (Get-Content (Join-Path $PSScriptRoot "config.friends.toml") -Raw -Encoding UTF8).Replace("{{URL}}", $Url).Replace("{{KEY}}", $Key).Replace("{{WORLD}}", $World)
[System.IO.File]::WriteAllText((Join-Path $stage "config.toml"), $config, (New-Object System.Text.UTF8Encoding($false)))
Copy-Item (Join-Path $PSScriptRoot "README-friends.txt") (Join-Path $stage "README.txt")
Set-Content -Path (Join-Path $stage "start-solid.bat") -Value "@echo off`r`ncd /d %~dp0`r`nDuneMarket.exe run --solid`r`n" -Encoding ASCII

$zip = Join-Path $root "dist\DuneMarket-friends.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $stage -DestinationPath $zip -CompressionLevel Optimal
Remove-Item -Recurse -Force (Split-Path $stage)
"{0} ({1:N0} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)
