[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
  [string]$SuiteRoot = "",
  [string]$UserProfileRoot = [Environment]::GetFolderPath("UserProfile"),
  [switch]$GraphifyOnly
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SuiteRoot)) {
  $SuiteRoot = Join-Path $PSScriptRoot ".."
}
$suite = (Resolve-Path -LiteralPath $SuiteRoot).Path
$userRoot = [IO.Path]::GetFullPath($UserProfileRoot).TrimEnd('\')
if (-not (Test-Path -LiteralPath $userRoot -PathType Container)) {
  throw "User profile root does not exist: $userRoot"
}

$requiredSources = @(
  (Join-Path $suite ".agents\skills"),
  (Join-Path $suite ".agents\workflows"),
  (Join-Path $suite ".claude\skills"),
  (Join-Path $suite ".claude\commands"),
  (Join-Path $suite "platforms\codex\plugins"),
  (Join-Path $suite "platforms\claude\plugins"),
  (Join-Path $suite "platforms\antigravity\plugins")
)
foreach ($source in $requiredSources) {
  if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Required audited source directory is missing: $source"
  }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $userRoot ".solo-suite-global-backups\$stamp"
$backedUp = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$installed = [ordered]@{
  codex_skills = 0
  codex_plugins = 0
  claude_skills = 0
  claude_commands = 0
  claude_plugins = 0
  antigravity_skills = 0
  antigravity_workflows = 0
  antigravity_plugins = 0
}

function Assert-UserTarget([string]$Path) {
  $full = [IO.Path]::GetFullPath($Path)
  $prefix = $userRoot + [IO.Path]::DirectorySeparatorChar
  if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing target outside the user profile: $full"
  }
  return $full
}

function Backup-Target([string]$Target) {
  $full = Assert-UserTarget $Target
  if (-not (Test-Path -LiteralPath $full) -or -not $backedUp.Add($full)) {
    return
  }
  $relative = $full.Substring($userRoot.Length).TrimStart('\')
  $backup = Join-Path $backupRoot $relative
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
  Copy-Item -LiteralPath $full -Destination $backup -Recurse -Force
}

function Install-Directory([string]$Source, [string]$Target) {
  $sourceFull = (Resolve-Path -LiteralPath $Source).Path
  $targetFull = Assert-UserTarget $Target
  if ($PSCmdlet.ShouldProcess($targetFull, "Install audited directory from $sourceFull")) {
    Backup-Target $targetFull
    if (Test-Path -LiteralPath $targetFull) {
      Remove-Item -LiteralPath $targetFull -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetFull) | Out-Null
    Copy-Item -LiteralPath $sourceFull -Destination $targetFull -Recurse -Force
  }
}

function Install-File([string]$Source, [string]$Target) {
  $sourceFull = (Resolve-Path -LiteralPath $Source).Path
  $targetFull = Assert-UserTarget $Target
  if ($PSCmdlet.ShouldProcess($targetFull, "Install audited file from $sourceFull")) {
    Backup-Target $targetFull
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetFull) | Out-Null
    Copy-Item -LiteralPath $sourceFull -Destination $targetFull -Force
  }
}

function Write-Utf8Json([string]$Path, [object]$Value) {
  $targetFull = Assert-UserTarget $Path
  Backup-Target $targetFull
  $json = $Value | ConvertTo-Json -Depth 30
  [IO.File]::WriteAllText($targetFull, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Add-Property([object]$Object, [string]$Name, [object]$Value) {
  $existing = $Object.PSObject.Properties[$Name]
  if ($null -eq $existing) {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
  } else {
    $existing.Value = $Value
  }
}

$codexRoot = Join-Path $userRoot ".codex"
$claudeRoot = Join-Path $userRoot ".claude"
$geminiConfig = Join-Path $userRoot ".gemini\config"

if ($GraphifyOnly) {
  $graphifySkill = Join-Path $suite ".agents\skills\graphify"
  $claudeGraphifySkill = Join-Path $suite ".claude\skills\graphify"
  $claudeGraphifyCommand = Join-Path $suite ".claude\commands\graphify.md"
  $antigravityGraphifyWorkflow = Join-Path $suite ".agents\workflows\graphify.md"
  foreach ($source in @($graphifySkill, $claudeGraphifySkill)) {
    if (-not (Test-Path -LiteralPath $source)) { throw "Graphify adapter is missing: $source" }
  }
  Install-Directory $graphifySkill (Join-Path $codexRoot "skills\graphify")
  Install-Directory $claudeGraphifySkill (Join-Path $claudeRoot "skills\graphify")
  Install-Directory $graphifySkill (Join-Path $geminiConfig "skills\graphify")
  Install-File $claudeGraphifyCommand (Join-Path $claudeRoot "commands\graphify.md")
  Install-File $antigravityGraphifyWorkflow (Join-Path $geminiConfig "global_workflows\graphify.md")
  Write-Output "Graphify host adapters installed globally for Codex, Claude, and Antigravity."
  if (Test-Path -LiteralPath $backupRoot) { Write-Output "Backups: $backupRoot" } else { Write-Output "Backups: none required" }
  Write-Output "Restart each host to load the Graphify skill/command/workflow."
  exit 0
}

# Portable skills: Codex and Claude use their user skill roots; Antigravity's
# documented global skill root is ~/.gemini/config/skills.
$canonicalSkills = Get-ChildItem -LiteralPath (Join-Path $suite ".agents\skills") -Directory | Sort-Object Name
foreach ($skill in $canonicalSkills) {
  Install-Directory $skill.FullName (Join-Path $codexRoot "skills\$($skill.Name)")
  Install-Directory (Join-Path $suite ".claude\skills\$($skill.Name)") (Join-Path $claudeRoot "skills\$($skill.Name)")
  Install-Directory $skill.FullName (Join-Path $geminiConfig "skills\$($skill.Name)")
  $installed.codex_skills++
  $installed.claude_skills++
  $installed.antigravity_skills++
}

# Claude standalone commands are user-global at ~/.claude/commands.
foreach ($command in Get-ChildItem -LiteralPath (Join-Path $suite ".claude\commands") -File -Filter "*.md" | Sort-Object Name) {
  Install-File $command.FullName (Join-Path $claudeRoot "commands\$($command.Name)")
  $installed.claude_commands++
}

# Codex native plugins: copy exact versioned trees and register the local
# marketplace plus enabled plugin IDs in ~/.codex/config.toml.
$codexMarketplace = "solo-suite-codex"
$codexPluginIds = @()
foreach ($plugin in Get-ChildItem -LiteralPath (Join-Path $suite "platforms\codex\plugins") -Directory | Sort-Object Name) {
  $manifestPath = Join-Path $plugin.FullName ".codex-plugin\plugin.json"
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if (-not $manifest.version) { throw "Codex plugin has no version: $($plugin.Name)" }
  Install-Directory $plugin.FullName (Join-Path $codexRoot "plugins\cache\$codexMarketplace\$($plugin.Name)\$($manifest.version)")
  $codexPluginIds += "$($plugin.Name)@$codexMarketplace"
  $installed.codex_plugins++
}

$codexConfigPath = Join-Path $codexRoot "config.toml"
if (-not (Test-Path -LiteralPath $codexConfigPath)) {
  New-Item -ItemType Directory -Force -Path $codexRoot | Out-Null
  [IO.File]::WriteAllText($codexConfigPath, "", [Text.UTF8Encoding]::new($false))
}
if ($PSCmdlet.ShouldProcess($codexConfigPath, "Register and enable the Solo Suite Codex marketplace")) {
  Backup-Target $codexConfigPath
  $codexConfig = Get-Content -LiteralPath $codexConfigPath -Raw
  $tableNames = @("marketplaces.$codexMarketplace") + @($codexPluginIds | ForEach-Object { 'plugins."' + $_ + '"' })
  foreach ($tableName in $tableNames) {
    $header = [Regex]::Escape("[$tableName]")
    $codexConfig = [Regex]::Replace($codexConfig, "(?ms)^$header\r?\n.*?(?=^\[|\z)", "")
  }
  $updated = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  $sourceLiteral = (Join-Path $suite "platforms\codex").Replace("'", "''")
  $blocks = @(
    "[marketplaces.$codexMarketplace]",
    "last_updated = `"$updated`"",
    'source_type = "local"',
    "source = '$sourceLiteral'",
    ""
  )
  foreach ($pluginId in $codexPluginIds) {
    $blocks += "[plugins.`"$pluginId`"]"
    $blocks += "enabled = true"
    $blocks += ""
  }
  $codexConfig = $codexConfig.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + ($blocks -join [Environment]::NewLine)
  [IO.File]::WriteAllText($codexConfigPath, $codexConfig, [Text.UTF8Encoding]::new($false))
}

# Claude native plugins: seed exact versioned cache trees, add user-scope
# install records, register the local marketplace, and enable every plugin.
$claudeMarketplace = "solo-suite"
$claudePluginRecords = @()
$now = (Get-Date).ToUniversalTime().ToString("o")
$repoCommit = (& git -C $suite rev-parse HEAD 2>$null)
foreach ($plugin in Get-ChildItem -LiteralPath (Join-Path $suite "platforms\claude\plugins") -Directory | Sort-Object Name) {
  $manifestPath = Join-Path $plugin.FullName ".claude-plugin\plugin.json"
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if (-not $manifest.version) { throw "Claude plugin has no version: $($plugin.Name)" }
  $installPath = Join-Path $claudeRoot "plugins\cache\$claudeMarketplace\$($plugin.Name)\$($manifest.version)"
  Install-Directory $plugin.FullName $installPath
  $claudePluginRecords += [PSCustomObject]@{
    id = "$($plugin.Name)@$claudeMarketplace"
    installPath = $installPath
    version = [string]$manifest.version
  }
  $installed.claude_plugins++
}

$installedPluginsPath = Join-Path $claudeRoot "plugins\installed_plugins.json"
$installedRegistry = if (Test-Path -LiteralPath $installedPluginsPath) {
  Get-Content -LiteralPath $installedPluginsPath -Raw | ConvertFrom-Json
} else {
  [PSCustomObject]@{ version = 2; plugins = [PSCustomObject]@{} }
}
if ($null -eq $installedRegistry.plugins) { Add-Property $installedRegistry "plugins" ([PSCustomObject]@{}) }
foreach ($record in $claudePluginRecords) {
  $entry = [ordered]@{
    scope = "user"
    installPath = $record.installPath
    version = $record.version
    installedAt = $now
    lastUpdated = $now
  }
  if ($repoCommit) { $entry.gitCommitSha = [string]$repoCommit }
  Add-Property $installedRegistry.plugins $record.id ([object[]]@([PSCustomObject]$entry))
}
if ($PSCmdlet.ShouldProcess($installedPluginsPath, "Register Claude plugins at user scope")) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $installedPluginsPath) | Out-Null
  Write-Utf8Json $installedPluginsPath $installedRegistry
}

$knownMarketplacesPath = Join-Path $claudeRoot "plugins\known_marketplaces.json"
$knownMarketplaces = if (Test-Path -LiteralPath $knownMarketplacesPath) {
  Get-Content -LiteralPath $knownMarketplacesPath -Raw | ConvertFrom-Json
} else { [PSCustomObject]@{} }
$claudeSource = Join-Path $suite "platforms\claude"
$marketRecord = [PSCustomObject]@{
  source = [PSCustomObject]@{ source = "directory"; path = $claudeSource }
  installLocation = $claudeSource
  lastUpdated = $now
}
Add-Property $knownMarketplaces $claudeMarketplace $marketRecord
if ($PSCmdlet.ShouldProcess($knownMarketplacesPath, "Register the Solo Suite Claude marketplace")) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $knownMarketplacesPath) | Out-Null
  Write-Utf8Json $knownMarketplacesPath $knownMarketplaces
}

$claudeSettingsPath = Join-Path $claudeRoot "settings.json"
$claudeSettings = if (Test-Path -LiteralPath $claudeSettingsPath) {
  Get-Content -LiteralPath $claudeSettingsPath -Raw | ConvertFrom-Json
} else { [PSCustomObject]@{} }
if ($null -eq $claudeSettings.enabledPlugins) { Add-Property $claudeSettings "enabledPlugins" ([PSCustomObject]@{}) }
if ($null -eq $claudeSettings.extraKnownMarketplaces) { Add-Property $claudeSettings "extraKnownMarketplaces" ([PSCustomObject]@{}) }
foreach ($record in $claudePluginRecords) { Add-Property $claudeSettings.enabledPlugins $record.id $true }
Add-Property $claudeSettings.extraKnownMarketplaces $claudeMarketplace ([PSCustomObject]@{
  source = [PSCustomObject]@{ source = "directory"; path = $claudeSource }
})
if ($PSCmdlet.ShouldProcess($claudeSettingsPath, "Enable Solo Suite Claude plugins globally")) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $claudeSettingsPath) | Out-Null
  Write-Utf8Json $claudeSettingsPath $claudeSettings
}

# Antigravity: install complete plugin trees, flatten their 80 unique skills
# into the documented global skill root, then overlay the canonical audited
# skills. Install workspace workflows as global saved workflows.
$antigravityPluginsRoot = Join-Path $geminiConfig "plugins"
$antigravitySkillsRoot = Join-Path $geminiConfig "skills"
foreach ($plugin in Get-ChildItem -LiteralPath (Join-Path $suite "platforms\antigravity\plugins") -Directory | Sort-Object Name) {
  Install-Directory $plugin.FullName (Join-Path $antigravityPluginsRoot $plugin.Name)
  $installed.antigravity_plugins++
  $pluginSkills = Join-Path $plugin.FullName "skills"
  if (Test-Path -LiteralPath $pluginSkills) {
    foreach ($skill in Get-ChildItem -LiteralPath $pluginSkills -Directory | Sort-Object Name) {
      Install-Directory $skill.FullName (Join-Path $antigravitySkillsRoot $skill.Name)
      $installed.antigravity_skills++
    }
  }
}
foreach ($skill in $canonicalSkills) {
  Install-Directory $skill.FullName (Join-Path $antigravitySkillsRoot $skill.Name)
}
foreach ($workflow in Get-ChildItem -LiteralPath (Join-Path $suite ".agents\workflows") -File -Filter "*.md" | Sort-Object Name) {
  Install-File $workflow.FullName (Join-Path $geminiConfig "global_workflows\$($workflow.Name)")
  $installed.antigravity_workflows++
}

Write-Output "Solo Suite global installation complete."
Write-Output ($installed | ConvertTo-Json -Compress)
if (Test-Path -LiteralPath $backupRoot) {
  Write-Output "Backups: $backupRoot"
} else {
  Write-Output "Backups: none required"
}
Write-Output "Restart Codex, Claude, and Antigravity to reload global extensions."
