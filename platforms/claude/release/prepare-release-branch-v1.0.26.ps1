[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedRemoteHead,
    [Parameter(Mandatory = $true)]
    [string]$ReleaseZip,
    [Parameter(Mandatory = $true)]
    [string]$Sha256Sums,
    [Parameter(Mandatory = $true)]
    [string]$Provenance,
    [switch]$AllowLocalTestRemote,
    [string]$ReleaseBranch = "release/v1.0.26",
    [string]$GitUserName = "Solo Suite release candidate",
    [string]$GitUserEmail = "solo-suite-release@users.noreply.github.com"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "publish-common.ps1")

$version = "1.0.26"
$ExpectedRemoteHead = $ExpectedRemoteHead.ToLowerInvariant()
if ($ReleaseBranch -cne "release/v$version") {
    throw "This reviewed helper may create only release/v$version."
}
Assert-SafeRemoteUrl -RemoteUrl $RemoteUrl -AllowLocalPath:$AllowLocalTestRemote
$initialRemoteHead = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "HEAD" -AllowLocalPath:$AllowLocalTestRemote
if ($initialRemoteHead -cne $ExpectedRemoteHead) {
    throw "Remote HEAD mismatch before clone: expected $ExpectedRemoteHead, found $initialRemoteHead."
}

$tempRoot = New-SafeTempRoot -Purpose "branch"
$commitOid = $null
try {
    $cloneDir = Assert-SafeChildPath -Path (Join-Path $tempRoot "repository") -SafeRoot $tempRoot
    $extractDir = Assert-SafeChildPath -Path (Join-Path $tempRoot "extracted") -SafeRoot $tempRoot
    $null = Invoke-CheckedGitGlobal -GitArgs @("clone", "--no-tags", "--no-checkout", $RemoteUrl, $cloneDir)

    # The reviewed package is byte-addressed. Never inherit a user's global
    # checkout/commit newline conversion policy into the candidate commit.
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "core.autocrlf", "false")
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "core.safecrlf", "true")

    $postCloneHead = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "HEAD" -AllowLocalPath:$AllowLocalTestRemote
    if ($postCloneHead -cne $ExpectedRemoteHead) {
        throw "Remote HEAD changed during clone; no branch was created."
    }
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("checkout", "--detach", $ExpectedRemoteHead)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("checkout", "-b", $ReleaseBranch)

    $package = Expand-AndVerifyReleasePackage `
        -ReleaseZip $ReleaseZip `
        -Sha256Sums $Sha256Sums `
        -ProvenanceFile $Provenance `
        -Destination $extractDir `
        -Version $version

    foreach ($item in (Get-ChildItem -LiteralPath $cloneDir -Force)) {
        if ($item.Name -ceq ".git") { continue }
        $safeItem = Assert-SafeChildPath -Path $item.FullName -SafeRoot $tempRoot
        Remove-Item -LiteralPath $safeItem -Recurse -Force
    }
    foreach ($item in (Get-ChildItem -LiteralPath $package.Root -Force)) {
        Copy-Item -LiteralPath $item.FullName -Destination $cloneDir -Recurse -Force
    }

    Assert-ExactFileInventory -Root $cloneDir `
        -ExpectedRelativePaths $package.RelativePaths `
        -ExcludedTopLevelName ".git"
    $candidateDigest = Get-StagedTreeDigest -Root $cloneDir -RelativePaths $package.RelativePaths
    if ($candidateDigest -cne $package.TreeDigest) {
        throw "Candidate checkout tree does not match the reviewed package provenance."
    }

    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "user.name", $GitUserName)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("config", "user.email", $GitUserEmail)
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("add", "--all")
    $changedPaths = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("diff", "--cached", "--name-only")
    if ([string]::IsNullOrWhiteSpace($changedPaths)) {
        throw "The reviewed package creates no change relative to remote HEAD."
    }
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("commit", "-m", "Prepare Solo Suite v$version release candidate")
    $commitOid = (Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @("rev-parse", "HEAD")).Trim().ToLowerInvariant()
    if ($commitOid -notmatch '^[0-9a-f]{40}$') {
        throw "Git did not return a valid candidate commit OID."
    }

    # Verify committed blobs, not only working-tree bytes. This catches Git
    # filters/newline conversion that could otherwise change the reviewed
    # package during `git add`.
    $commitArchive = Assert-SafeChildPath -Path (Join-Path $tempRoot "committed-tree.zip") -SafeRoot $tempRoot
    $commitExtract = Assert-SafeChildPath -Path (Join-Path $tempRoot "committed-tree") -SafeRoot $tempRoot
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "archive", "--format=zip", "--output=$commitArchive", $commitOid)
    $null = New-Item -ItemType Directory -Path $commitExtract
    [IO.Compression.ZipFile]::ExtractToDirectory($commitArchive, $commitExtract)
    Assert-ExactFileInventory -Root $commitExtract -ExpectedRelativePaths $package.RelativePaths
    $committedDigest = Get-StagedTreeDigest -Root $commitExtract -RelativePaths $package.RelativePaths
    if ($committedDigest -cne $package.TreeDigest) {
        throw "Committed Git blobs do not match the reviewed package provenance."
    }

    $finalRemoteHead = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "HEAD" -AllowLocalPath:$AllowLocalTestRemote
    if ($finalRemoteHead -cne $ExpectedRemoteHead) {
        throw "Remote HEAD changed before push; refusing to publish the review branch."
    }
    $existingBranch = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/heads/$ReleaseBranch" -AllowLocalPath:$AllowLocalTestRemote
    if ($null -ne $existingBranch) {
        throw "Remote review branch already exists; refusing to overwrite it."
    }
    # The empty expected value on this lease makes absence atomic: if another
    # actor creates the branch after the check above, Git rejects this push.
    $null = Invoke-CheckedGit -WorkingDirectory $cloneDir -GitArgs @(
        "push", "--set-upstream", "--force-with-lease=refs/heads/${ReleaseBranch}:",
        "origin", "HEAD:refs/heads/$ReleaseBranch")
    $remoteBranchOid = Get-LsRemoteOid -RemoteUrl $RemoteUrl -RefName "refs/heads/$ReleaseBranch" -AllowLocalPath:$AllowLocalTestRemote
    if ($remoteBranchOid -cne $commitOid) {
        throw "Remote review branch verification failed: expected $commitOid, found $remoteBranchOid."
    }
}
finally {
    Remove-SafeTempRoot -SafeRoot $tempRoot
}

Write-Output "RELEASE_BRANCH_PUSHED=$ReleaseBranch"
Write-Output "APPROVED_COMMIT_OID=$commitOid"
