param(
  [string]$SuiteRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$python = (Get-Command python).Source

function Invoke-Checked {
  param(
    [string]$WorkingDirectory,
    [string[]]$Arguments
  )

  Push-Location $WorkingDirectory
  try {
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Validation failed in $WorkingDirectory`: $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

$claudeTests = @(
  "tests.test_inventory",
  "tests.test_parity_contract",
  "tests.test_validate_rooms",
  "tests.test_output_contract",
  "tests.test_documentation_truth",
  "tests.test_readonly_audit",
  "tests.test_trigger_routing"
)

$codexTests = @(
  "tests.test_self_check",
  "tests.test_validate_plugins",
  "tests.test_command_skills",
  "tests.test_validate_rooms",
  "tests.test_full_team_preflight",
  "tests.test_gate_contracts",
  "tests.test_site_doctor_helpers",
  "tests.test_parity"
)

foreach ($platform in @("claude", "antigravity")) {
  $root = Join-Path $SuiteRoot "platforms\$platform"
  Invoke-Checked $root @("plugins\solo\skills\suite-integrity\scripts\self_check.py", ".", "-")
  Invoke-Checked $root @("plugins\ai\skills\agent-room-templates\scripts\validate_rooms.py", "--suite", ".")
  Invoke-Checked $root (@("-m", "unittest") + $claudeTests)
}

$codexRoot = Join-Path $SuiteRoot "platforms\codex"
Invoke-Checked $codexRoot @("plugins\solo\skills\suite-integrity\scripts\self_check.py", ".", "-")
Invoke-Checked $codexRoot @("plugins\ai\skills\agent-room-templates\scripts\validate_rooms.py", "--suite", ".")
Invoke-Checked $codexRoot @("tools\validate_plugins.py", "--official-if-available")
Invoke-Checked $codexRoot (@("-m", "unittest") + $codexTests)

Write-Output "All bounded Solo Suite Enchance platform validations passed."
