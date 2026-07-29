[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$DryRun
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptRoot "sync-agent-skills.py"
$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $python) {
    Write-Error "Python is required. No installation was attempted."
    exit 2
}

$arguments = @($pythonScript)
if ($Check) { $arguments += "--check" }
if ($DryRun) { $arguments += "--dry-run" }

& $python.Source @arguments
exit $LASTEXITCODE
