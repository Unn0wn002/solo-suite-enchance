[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ApprovedCommitOid,
    [switch]$AllowLocalTestRemote,
    [string]$TagName = "v1.0.26",
    [string]$GitUserName = "Solo Suite release tagger",
    [string]$GitUserEmail = "solo-suite-release@users.noreply.github.com"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "publish-common.ps1")

$ApprovedCommitOid = $ApprovedCommitOid.ToLowerInvariant()
if ($TagName -cne "v1.0.26") {
    throw "This reviewed helper may create only v1.0.26."
}
Assert-SafeRemoteUrl -RemoteUrl $RemoteUrl -AllowLocalPath:$AllowLocalTestRemote
$reviewBranch = "release/v1.0.26"
$reviewBranchOid = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/heads/$reviewBranch" -AllowLocalPath:$AllowLocalTestRemote
if ($reviewBranchOid -cne $ApprovedCommitOid) {
    throw "Remote review branch must exist and equal the exact approved commit OID."
}
if ($null -ne (Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/tags/$TagName" -AllowLocalPath:$AllowLocalTestRemote)) {
    throw "Remote tag $TagName already exists."
}
if ($null -ne (Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/tags/$TagName^{}" -AllowLocalPath:$AllowLocalTestRemote)) {
    throw "Remote peeled tag $TagName already exists."
}

$tempRoot = New-SafeTempRoot -Purpose "tag"
try {
    $cloneDir = Assert-SafeChildPath -Path (Join-Path $tempRoot "repository") -SafeRoot $tempRoot
    $null = Invoke-CheckedGitGlobal -GitArgs @("clone", "--no-tags", "--no-checkout", $RemoteUrl, $cloneDir)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("cat-file", "-e", "$ApprovedCommitOid^{commit}")
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("checkout", "--detach", $ApprovedCommitOid)
    $checkedOutOid = (Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("rev-parse", "HEAD")).Trim().ToLowerInvariant()
    if ($checkedOutOid -cne $ApprovedCommitOid) {
        throw "Fresh clone did not check out the exact approved commit."
    }

    $marketplacePath = Join-Path $cloneDir ".claude-plugin/marketplace.json"
    if (-not (Test-Path -LiteralPath $marketplacePath -PathType Leaf)) {
        throw "Approved commit has no marketplace manifest."
    }
    $marketplace = Get-Content -Raw -LiteralPath $marketplacePath | ConvertFrom-Json
    if ([string]$marketplace.metadata.version -cne $TagName.Substring(1)) {
        throw "Approved commit marketplace version does not match $TagName."
    }

    $containing = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "branch", "--remotes", "--contains", $ApprovedCommitOid)
    if ([string]::IsNullOrWhiteSpace($containing)) {
        throw "Approved commit is not reachable from any freshly cloned remote branch."
    }

    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "user.name", $GitUserName)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "user.email", $GitUserEmail)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "tag", "--annotate", "--message", "Solo Suite $TagName", $TagName, $ApprovedCommitOid)
    $localTarget = (Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "rev-parse", "$TagName^{}")).Trim().ToLowerInvariant()
    if ($localTarget -cne $ApprovedCommitOid) {
        throw "Local tag does not resolve to the exact approved commit."
    }

    if ($null -ne (Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/tags/$TagName" -AllowLocalPath:$AllowLocalTestRemote)) {
        throw "Remote tag appeared before push; refusing to overwrite it."
    }
    $reviewBranchOid = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/heads/$reviewBranch" -AllowLocalPath:$AllowLocalTestRemote
    if ($reviewBranchOid -cne $ApprovedCommitOid) {
        throw "Remote review branch moved before tag push; refusing publication."
    }
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "push", "origin", "refs/tags/${TagName}:refs/tags/${TagName}")
    $remoteTarget = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/tags/$TagName^{}" -AllowLocalPath:$AllowLocalTestRemote
    if ($remoteTarget -cne $ApprovedCommitOid) {
        throw "Remote tag verification failed: expected $ApprovedCommitOid, found $remoteTarget."
    }
}
finally {
    Remove-SafeTempRoot -SafeRoot $tempRoot
}

Write-Output "TAG_PUSHED=$TagName"
Write-Output "TAG_COMMIT_OID=$ApprovedCommitOid"
