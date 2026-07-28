param(
  [string]$SuiteRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path (Join-Path $SuiteRoot "platforms\antigravity")).Path
$config = Join-Path $HOME ".gemini\config"
$pluginsTarget = Join-Path $config "plugins"
$skillsTarget = Join-Path $config "skills"

New-Item -ItemType Directory -Force -Path $pluginsTarget, $skillsTarget | Out-Null
Copy-Item (Join-Path $source "plugins\*") $pluginsTarget -Recurse -Force

Get-ChildItem (Join-Path $source "plugins") -Directory | ForEach-Object {
  $skills = Join-Path $_.FullName "skills"
  if (Test-Path $skills) {
    Copy-Item (Join-Path $skills "*") $skillsTarget -Recurse -Force
  }
}

Write-Output "Installed Solo Suite Enchance Antigravity adapter from $source"
Write-Output "Restart Antigravity to reload plugins and skills."
