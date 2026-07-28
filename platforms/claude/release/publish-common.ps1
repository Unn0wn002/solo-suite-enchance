Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-CheckedGit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$GitArgs,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [int[]]$AllowedExitCodes = @(0)
    )

    $previousErrorAction = $ErrorActionPreference
    $nativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $previousNativePreference = if ($null -ne $nativePreference) { $nativePreference.Value } else { $null }
    try {
        # Git writes ordinary progress to stderr. Capture it without allowing
        # PowerShell 5.1/7 to turn successful native stderr into an exception;
        # the checked native exit code remains authoritative.
        $ErrorActionPreference = "Continue"
        if ($null -ne $nativePreference) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $false
        }
        $output = & git -C $WorkingDirectory @GitArgs 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
        if ($null -ne $nativePreference) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $previousNativePreference
        }
    }
    $text = (($output | ForEach-Object { "$_" }) -join [Environment]::NewLine).Trim()
    if ($AllowedExitCodes -notcontains $exitCode) {
        throw "git failed with exit code $exitCode. Output: $text"
    }
    return $text
}

function Invoke-CheckedGitGlobal {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$GitArgs,
        [int[]]$AllowedExitCodes = @(0)
    )

    $previousErrorAction = $ErrorActionPreference
    $nativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $previousNativePreference = if ($null -ne $nativePreference) { $nativePreference.Value } else { $null }
    try {
        $ErrorActionPreference = "Continue"
        if ($null -ne $nativePreference) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $false
        }
        $output = & git @GitArgs 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
        if ($null -ne $nativePreference) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $previousNativePreference
        }
    }
    $text = (($output | ForEach-Object { "$_" }) -join [Environment]::NewLine).Trim()
    if ($AllowedExitCodes -notcontains $exitCode) {
        throw "git failed with exit code $exitCode. Output: $text"
    }
    return $text
}

function Assert-SafeRemoteUrl {
    param(
        [Parameter(Mandatory = $true)][string]$RemoteUrl,
        [switch]$AllowLocalPath
    )
    if ([string]::IsNullOrWhiteSpace($RemoteUrl) -or $RemoteUrl.StartsWith("-")) {
        throw "RemoteUrl must be non-empty and cannot begin with '-'."
    }
    if ($RemoteUrl -match '\s' -or $RemoteUrl.Contains("::")) {
        throw "RemoteUrl contains whitespace or a Git remote-helper/ext transport, which is not allowed."
    }

    $uri = $null
    if ([Uri]::TryCreate($RemoteUrl, [UriKind]::Absolute, [ref]$uri) -and
        ($uri.Scheme -ceq "https" -or $uri.Scheme -ceq "ssh")) {
        if ($uri.Scheme -ceq "https" -and -not [string]::IsNullOrEmpty($uri.UserInfo)) {
            throw "HTTPS RemoteUrl must not embed credentials."
        }
        return
    }
    if ($RemoteUrl -match '^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[^\s]+$') {
        return
    }
    if ($AllowLocalPath -and [IO.Path]::IsPathRooted($RemoteUrl)) {
        return
    }
    throw "RemoteUrl must use HTTPS, SSH, or SCP-style SSH. Local paths require -AllowLocalTestRemote."
}

function Get-LsRemoteOid {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RemoteUrl,
        [Parameter(Mandatory = $true)][string]$RefName,
        [switch]$AllowLocalPath
    )

    Assert-SafeRemoteUrl -RemoteUrl $RemoteUrl -AllowLocalPath:$AllowLocalPath
    $text = Invoke-CheckedGitGlobal -GitArgs @("ls-remote", $RemoteUrl, $RefName)
    $foundOids = @()
    foreach ($line in ($text -split "`r?`n")) {
        if ($line -match '^([0-9a-f]{40})\s+(.+)$') {
            $oid = $Matches[1]
            $returnedRef = $Matches[2]
            if ($returnedRef -ceq $RefName) {
                $foundOids += $oid
            }
        }
    }
    if ($foundOids.Count -gt 1) {
        throw "Remote returned more than one exact match for $RefName."
    }
    if ($foundOids.Count -eq 0) {
        return $null
    }
    return $foundOids[0]
}

function New-SafeTempRoot {
    [CmdletBinding()]
    param([string]$Purpose = "publish")

    if ($Purpose -notmatch '^[a-z0-9-]+$') {
        throw "Unsafe temporary-directory purpose."
    }
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $leaf = "solo-suite-$Purpose-$([Guid]::NewGuid().ToString('N'))"
    $path = Join-Path $parent $leaf
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to reuse an existing temporary path: $path"
    }
    $null = New-Item -ItemType Directory -Path $path
    $marker = Join-Path $path ".solo-suite-safe-temp-root"
    [IO.File]::WriteAllText($marker, $leaf, (New-Object Text.UTF8Encoding($false)))
    return [IO.Path]::GetFullPath($path)
}

function Assert-SafeChildPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$SafeRoot
    )

    $root = [IO.Path]::GetFullPath($SafeRoot).TrimEnd(
        [IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $candidate = [IO.Path]::GetFullPath($Path)
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing filesystem mutation outside the verified temporary root: $candidate"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root ".solo-suite-safe-temp-root") -PathType Leaf)) {
        throw "Temporary-root safety marker is missing: $root"
    }
    return $candidate
}

function Remove-SafeTempRoot {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$SafeRoot)

    if (-not (Test-Path -LiteralPath $SafeRoot)) {
        return
    }
    $root = [IO.Path]::GetFullPath($SafeRoot)
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
        [IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $expectedPrefix = $parent + [IO.Path]::DirectorySeparatorChar + "solo-suite-"
    if (-not $root.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete a directory outside the Solo Suite temp namespace: $root"
    }
    $item = Get-Item -Force -LiteralPath $root
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to delete a reparse-point temporary root: $root"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root ".solo-suite-safe-temp-root") -PathType Leaf)) {
        throw "Refusing to delete an unmarked temporary root: $root"
    }
    Remove-Item -LiteralPath $root -Recurse -Force
}

function Get-RelativeUnixPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $rootUri = New-Object Uri(([IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar))
    $pathUri = New-Object Uri([IO.Path]::GetFullPath($Path))
    return [Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
}

function Assert-PortableArchivePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Kind
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.Contains('\') -or
        $Path.StartsWith('/') -or $Path -match '(^|/)\.\.(/|$)' -or
        $Path.Contains(':') -or $Path.IndexOf([char]0) -ge 0 -or
        $Path -match '[\x01-\x1f\x7f]' -or $Path -match '[<>"|?*]') {
        throw "Unsafe or non-portable $Kind path: $Path"
    }
    foreach ($segment in $Path.Split('/')) {
        if ([string]::IsNullOrEmpty($segment) -or $segment -ceq '.' -or
            $segment.EndsWith('.') -or $segment.EndsWith(' ') -or
            $segment -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)') {
            throw "Unsafe or non-portable $Kind path segment: $Path"
        }
    }
}

function Get-StagedTreeDigest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$RelativePaths
    )

    $ordered = [string[]]$RelativePaths.Clone()
    [Array]::Sort($ordered, [StringComparer]::Ordinal)
    $memory = New-Object IO.MemoryStream
    $utf8 = New-Object Text.UTF8Encoding($false)
    $ascii = [Text.Encoding]::ASCII
    try {
        foreach ($rel in $ordered) {
            $full = Join-Path $Root ($rel.Replace('/', [IO.Path]::DirectorySeparatorChar))
            if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
                throw "Tree-digest input is missing: $rel"
            }
            $digest = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
            $relBytes = $utf8.GetBytes($rel)
            $memory.Write($relBytes, 0, $relBytes.Length)
            $memory.WriteByte(0)
            $hashBytes = $ascii.GetBytes($digest)
            $memory.Write($hashBytes, 0, $hashBytes.Length)
            $memory.WriteByte(10)
        }
        $memory.Position = 0
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash($memory)
        }
        finally {
            $sha.Dispose()
        }
        return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $memory.Dispose()
    }
}

function Assert-ExactFileInventory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$ExpectedRelativePaths,
        [string]$ExcludedTopLevelName
    )

    $expected = New-Object 'System.Collections.Generic.Dictionary[string,bool]'
    foreach ($rel in $ExpectedRelativePaths) {
        if ($expected.ContainsKey($rel)) {
            throw "Duplicate expected path: $rel"
        }
        $expected.Add($rel, $true)
    }
    $actual = New-Object 'System.Collections.Generic.Dictionary[string,bool]'
    foreach ($file in (Get-ChildItem -LiteralPath $Root -Recurse -Force -File)) {
        $rel = Get-RelativeUnixPath -Root $Root -Path $file.FullName
        if ($ExcludedTopLevelName -and $rel.Split('/')[0] -ceq $ExcludedTopLevelName) {
            continue
        }
        if ($actual.ContainsKey($rel)) {
            throw "Duplicate actual path: $rel"
        }
        $actual.Add($rel, $true)
    }
    if ($expected.Count -ne $actual.Count) {
        throw "File inventory count mismatch: expected $($expected.Count), found $($actual.Count)."
    }
    foreach ($rel in $expected.Keys) {
        if (-not $actual.ContainsKey($rel)) {
            throw "File inventory is missing: $rel"
        }
    }
    foreach ($rel in $actual.Keys) {
        if (-not $expected.ContainsKey($rel)) {
            throw "File inventory has an unexpected path: $rel"
        }
    }
}

function Expand-AndVerifyReleasePackage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$ReleaseZip,
        [Parameter(Mandatory = $true)][string]$Sha256Sums,
        [Parameter(Mandatory = $true)][string]$ProvenanceFile,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Version,
        [ValidateRange(1, 100000)][int]$MaxArchiveEntries = 5000,
        [ValidateRange(1, 1099511627776)][long]$MaxExpandedBytes = 268435456,
        [ValidateRange(1.0, 100000.0)][double]$MaxCompressionRatio = 200.0,
        [ValidateRange(1, 256)][int]$MaxPathDepth = 32
    )

    $zipPath = [IO.Path]::GetFullPath($ReleaseZip)
    $sumsPath = [IO.Path]::GetFullPath($Sha256Sums)
    $provenancePath = [IO.Path]::GetFullPath($ProvenanceFile)
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "Release ZIP not found: $zipPath"
    }
    if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) {
        throw "SHA256SUMS not found: $sumsPath"
    }
    if (-not (Test-Path -LiteralPath $provenancePath -PathType Leaf)) {
        throw "provenance.json not found: $provenancePath"
    }
    if ($Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Version must be semantic x.y.z without a leading v."
    }
    $zipName = "solo-suite-plugin-v$Version.zip"
    if ([IO.Path]::GetFileName($zipPath) -cne $zipName) {
        throw "Expected release ZIP name $zipName."
    }

    $checksums = New-Object 'System.Collections.Generic.Dictionary[string,string]'
    $checksumPortableKeys = New-Object 'System.Collections.Generic.Dictionary[string,string]'
    foreach ($line in [IO.File]::ReadAllLines($sumsPath)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
            throw "Malformed SHA256SUMS line."
        }
        $digest = $Matches[1].ToLowerInvariant()
        $name = $Matches[2]
        Assert-PortableArchivePath -Path $name -Kind "SHA256SUMS"
        if ($checksums.ContainsKey($name)) {
            throw "Duplicate SHA256SUMS path: $name"
        }
        $portableKey = $name.Normalize([Text.NormalizationForm]::FormC).ToLowerInvariant()
        if ($checksumPortableKeys.ContainsKey($portableKey)) {
            throw "Case- or Unicode-colliding SHA256SUMS paths: $name and $($checksumPortableKeys[$portableKey])"
        }
        $checksumPortableKeys.Add($portableKey, $name)
        $checksums.Add($name, $digest)
    }
    if (-not $checksums.ContainsKey($zipName)) {
        throw "SHA256SUMS does not cover $zipName."
    }
    $actualZipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualZipHash -cne $checksums[$zipName]) {
        throw "Release ZIP checksum mismatch."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
    $entryNames = New-Object 'System.Collections.Generic.Dictionary[string,bool]'
    $entryPortableKeys = New-Object 'System.Collections.Generic.Dictionary[string,string]'
    [long]$expandedBytes = 0
    try {
        if ($archive.Entries.Count -gt $MaxArchiveEntries) {
            throw "ZIP entry-count budget exceeded: $($archive.Entries.Count) > $MaxArchiveEntries"
        }
        foreach ($entry in $archive.Entries) {
            $rawName = $entry.FullName
            if ([string]::IsNullOrEmpty($entry.Name)) {
                throw "Directory-only ZIP entries are not accepted: $rawName"
            }
            Assert-PortableArchivePath -Path $rawName -Kind "ZIP entry"
            if (($rawName -split '/').Count -gt $MaxPathDepth) {
                throw "ZIP path-depth budget exceeded: $rawName"
            }
            if ($entry.Length -gt ($MaxExpandedBytes - $expandedBytes)) {
                throw "ZIP expanded-byte budget exceeded at: $rawName"
            }
            $expandedBytes += $entry.Length
            if ($entry.Length -gt 0) {
                $denominator = [Math]::Max([long]1, [long]$entry.CompressedLength)
                $ratio = [double]$entry.Length / [double]$denominator
                if ($ratio -gt $MaxCompressionRatio) {
                    throw "ZIP compression-ratio budget exceeded at: $rawName"
                }
            }
            $name = $rawName
            if ($entryNames.ContainsKey($name)) {
                throw "Duplicate ZIP entry: $name"
            }
            $portableKey = $name.Normalize([Text.NormalizationForm]::FormC).ToLowerInvariant()
            if ($entryPortableKeys.ContainsKey($portableKey)) {
                throw "Case- or Unicode-colliding ZIP entries: $name and $($entryPortableKeys[$portableKey])"
            }
            $unsignedAttributes = [BitConverter]::ToUInt32(
                [BitConverter]::GetBytes([int32]$entry.ExternalAttributes), 0)
            $mode = (($unsignedAttributes -shr 16) -band 0xF000)
            if ($mode -eq 0xA000) {
                throw "Symlink entries are not accepted: $name"
            }
            $entryPortableKeys.Add($portableKey, $name)
            $entryNames.Add($name, $true)
        }
    }
    finally {
        $archive.Dispose()
    }

    $top = "solo-suite-plugin-v$Version"
    foreach ($name in $entryNames.Keys) {
        if ($name.Split('/')[0] -cne $top) {
            throw "ZIP entry is outside the one expected top-level directory: $name"
        }
    }
    $expectedEntries = @($checksums.Keys | Where-Object { $_ -cne $zipName })
    if ($entryNames.Count -ne $expectedEntries.Count) {
        throw "ZIP/checksum inventory count mismatch."
    }
    foreach ($name in $expectedEntries) {
        if (-not $entryNames.ContainsKey($name)) {
            throw "SHA256SUMS path is absent from ZIP: $name"
        }
    }

    if (Test-Path -LiteralPath $Destination) {
        throw "Extraction destination must not already exist: $Destination"
    }
    $null = New-Item -ItemType Directory -Path $Destination
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $Destination)
    Assert-ExactFileInventory -Root $Destination -ExpectedRelativePaths $expectedEntries

    foreach ($name in $expectedEntries) {
        $full = Join-Path $Destination ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
        $actual = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -cne $checksums[$name]) {
            throw "Extracted-file checksum mismatch: $name"
        }
    }

    $root = Join-Path $Destination $top
    $relativePaths = @($expectedEntries | ForEach-Object { $_.Substring($top.Length + 1) })
    $provenance = Get-Content -Raw -LiteralPath $provenancePath | ConvertFrom-Json
    if ($provenance.version -cne $Version) {
        throw "Release provenance version does not match $Version."
    }
    if ([string]$provenance.artifact -cne $zipName -or
        [string]$provenance.artifact_sha256 -cne $actualZipHash) {
        throw "Release provenance does not bind the reviewed ZIP digest."
    }
    if ($provenance.PSObject.Properties.Name -notcontains "source_dirty" -or
        $provenance.source_dirty -isnot [bool] -or $provenance.source_dirty) {
        throw "Release provenance must record source_dirty as exactly false."
    }
    if ($provenance.PSObject.Properties.Name -notcontains "source_commit" -or
        [string]$provenance.source_commit -cnotmatch '^[0-9a-f]{40}$') {
        throw "Release provenance must record a verified 40-lowercase-hex source_commit."
    }
    if ([int]$provenance.file_count -ne $relativePaths.Count) {
        throw "Release provenance file_count does not match the exact inventory."
    }
    $treeDigest = Get-StagedTreeDigest -Root $root -RelativePaths $relativePaths
    if ($treeDigest -cne [string]$provenance.staged_tree_sha256) {
        throw "Extracted staged-tree digest does not match release provenance."
    }
    return [PSCustomObject]@{
        Root = $root
        RelativePaths = $relativePaths
        TreeDigest = $treeDigest
    }
}
