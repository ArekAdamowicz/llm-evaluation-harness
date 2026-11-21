
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ==================================================
# CONFIGURATION
# ==================================================

$OutputName = "review_packet.md"
$MaxFileSizeBytes = 1MB

$AllowedExtensions = @(
    ".py",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
    ".ini",
    ".cfg"
)

$ExcludedDirectories = @(
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "build",
    "dist"
)

$ExcludedFiles = @(
    "struktura.txt",
    "review_packet.md"
)

$SecretPattern = '(^\.env(?:\..*)?$|secret|credential|password|token|private.?key|\.pem$|\.pfx$|\.p12$)'

# ==================================================
# REPOSITORY DETECTION
# ==================================================

$gitRoot = & git rev-parse --show-toplevel 2>$null

if ($LASTEXITCODE -ne 0 -or -not $gitRoot) {
    throw "Git repository not found."
}

function ConvertTo-NormalizedFullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)

    if ([System.IO.Path]::DirectorySeparatorChar -eq '\') {
        $fullPath = $fullPath.Replace('/', '\')
    }
    else {
        $fullPath = $fullPath.Replace('\', '/')
    }

    return $fullPath
}

$repoRoot = ConvertTo-NormalizedFullPath -Path $gitRoot.Trim()

$directorySeparator = [System.IO.Path]::DirectorySeparatorChar

if (-not $repoRoot.EndsWith([string]$directorySeparator)) {
    $repoPrefix = $repoRoot + $directorySeparator
}
else {
    $repoPrefix = $repoRoot
}

$outputFullPath = ConvertTo-NormalizedFullPath -Path (
    Join-Path $repoRoot $OutputName
)

$files = [System.Collections.Generic.List[string]]::new()
$fileSet = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
$deletedFiles = [System.Collections.Generic.List[string]]::new()
$skippedFiles = [System.Collections.Generic.List[string]]::new()

# ==================================================
# HELPER: GET REPOSITORY-RELATIVE PATH
# ==================================================

function Get-RelativeRepositoryPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FullPath
    )

    $normalizedPath = ConvertTo-NormalizedFullPath -Path $FullPath

    if (-not $normalizedPath.StartsWith(
        $repoPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        return $null
    }

    return $normalizedPath.Substring($repoPrefix.Length).Replace('\', '/')
}

# ==================================================
# HELPER: ADD ONE FILE
# ==================================================

function Add-ReviewFile {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $resolved = ConvertTo-NormalizedFullPath -Path $resolvedPath

    $relative = Get-RelativeRepositoryPath -FullPath $resolved

    if (-not $relative) {
        return
    }

    if ($resolved -eq $outputFullPath) {
        return
    }

    $file = Get-Item -LiteralPath $resolved

    if ($ExcludedFiles -contains $file.Name) {
        return
    }

    $segments = $relative -split '/'

    foreach ($segment in $segments) {
        if ($ExcludedDirectories -contains $segment) {
            return
        }
    }

    if ($file.Name -match $SecretPattern) {
        $skippedFiles.Add("$relative (potential secret)")
        return
    }

    if ($file.Extension.ToLowerInvariant() -notin $AllowedExtensions) {
        $skippedFiles.Add("$relative (unsupported extension)")
        return
    }

    if ($file.Length -gt $MaxFileSizeBytes) {
        $skippedFiles.Add("$relative (larger than 1 MB)")
        return
    }

    if ($fileSet.Add($resolved)) {
        $files.Add($resolved)
    }
}

# ==================================================
# HELPER: ADD FILE OR DIRECTORY
# ==================================================

function Add-ReviewPath {
    param(
        [string]$RelativePath
    )

    $candidate = Join-Path $repoRoot $RelativePath

    if (-not (Test-Path -LiteralPath $candidate)) {
        return
    }

    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        Add-ReviewFile -Path $candidate
        return
    }

    $items = Get-ChildItem `
        -LiteralPath $candidate `
        -File `
        -Recurse `
        -Force

    foreach ($item in $items) {
        Add-ReviewFile -Path $item.FullName
    }
}

# ==================================================
# 1. DETECT GIT CHANGES
# ==================================================

Write-Host "Analyzing Git changes..."

$changedPaths = @(
    & git diff --name-only HEAD
)

if ($LASTEXITCODE -ne 0) {
    throw "Failed to read Git changes."
}

$untrackedPaths = @(
    & git ls-files --others --exclude-standard
)

if ($LASTEXITCODE -ne 0) {
    throw "Failed to read untracked Git files."
}

$allChangedPaths = @(
    $changedPaths
    $untrackedPaths
) | Where-Object { $_ } | Sort-Object -Unique

if ($allChangedPaths.Count -eq 0) {
    throw "No changes detected. Nothing to review."
}

foreach ($path in $allChangedPaths) {
    $candidate = Join-Path $repoRoot $path

    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        Add-ReviewFile -Path $candidate
    }
    else {
        $deletedFiles.Add($path.Replace('\', '/'))
    }
}

# ==================================================
# 2. DETECT RELATED COMPONENTS
# ==================================================

Write-Host "Detecting related components..."

$components = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

foreach ($path in $allChangedPaths) {
    $normalized = $path.Replace('\', '/')
    $parts = $normalized -split '/'

    if (
        $parts.Count -ge 3 -and
        $parts[0] -eq "src" -and
        $parts[1] -eq "llm_eval"
    ) {
        [void]$components.Add($parts[2])
    }

    if (
        $parts.Count -ge 2 -and
        $parts[0] -eq "tests"
    ) {
        [void]$components.Add($parts[1])
    }

    if (
        $parts.Count -ge 2 -and
        $parts[0] -eq "fixtures" -and
        $parts[1] -eq "manual-responses"
    ) {
        [void]$components.Add("providers")
    }
}

foreach ($component in $components) {
    Add-ReviewPath "src/llm_eval/$component"
    Add-ReviewPath "tests/$component"
    Add-ReviewPath "tests/unit/$component"
    Add-ReviewPath "tests/integration/$component"
    Add-ReviewPath "fixtures/$component"
}

if ($components.Contains("providers")) {
    Add-ReviewPath "fixtures/manual-responses"
    Add-ReviewPath "docs/test-cases"
}

if ($components.Contains("evaluation")) {
    Add-ReviewPath "docs/test-cases"
}

# ==================================================
# 3. ADD BASE PROJECT CONTEXT
# ==================================================

Write-Host "Adding project context..."

$baseContext = @(
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "docs/review_process.md"
)

foreach ($path in $baseContext) {
    Add-ReviewPath $path
}

if (
    $components.Contains("providers") -or
    $components.Contains("evaluation") -or
    $components.Contains("results")
) {
    Add-ReviewPath "src/llm_eval/results"
}

# ==================================================
# 4. FINAL FILE LIST
# ==================================================

$allFiles = @(
    $files | Sort-Object
)

if ($allFiles.Count -eq 0 -and $deletedFiles.Count -eq 0) {
    throw "No eligible files found for review."
}

# ==================================================
# 5. GIT INFORMATION
# ==================================================

$branch = (& git branch --show-current).Trim()
$lastCommit = (& git log -1 --format="%h %s").Trim()
$gitStatus = (& git status --short --branch) -join "`n"

# ==================================================
# 6. BUILD REVIEW PACKET
# ==================================================

Write-Host "Building review packet..."

$builder = [System.Text.StringBuilder]::new()

[void]$builder.AppendLine("# LLM Evaluation Harness - Code Review")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
[void]$builder.AppendLine("Branch: $branch")
[void]$builder.AppendLine("Last commit: $lastCommit")
[void]$builder.AppendLine()

[void]$builder.AppendLine("## Git status")
[void]$builder.AppendLine()
[void]$builder.AppendLine('```text')
[void]$builder.AppendLine($gitStatus)
[void]$builder.AppendLine('```')
[void]$builder.AppendLine()

[void]$builder.AppendLine("## Detected changes")
[void]$builder.AppendLine()

foreach ($path in $allChangedPaths) {
    [void]$builder.AppendLine("- $path")
}

[void]$builder.AppendLine()
[void]$builder.AppendLine("## Deleted files")
[void]$builder.AppendLine()

if ($deletedFiles.Count -eq 0) {
    [void]$builder.AppendLine("None.")
}
else {
    foreach ($path in $deletedFiles) {
        [void]$builder.AppendLine("- $path")
    }
}

[void]$builder.AppendLine()
[void]$builder.AppendLine("## Included files")
[void]$builder.AppendLine()

foreach ($file in $allFiles) {
    $relative = Get-RelativeRepositoryPath -FullPath $file
    [void]$builder.AppendLine("- $relative")
}

[void]$builder.AppendLine()
[void]$builder.AppendLine("---")
[void]$builder.AppendLine()

# ==================================================
# 7. APPEND FILE CONTENTS
# ==================================================

foreach ($file in $allFiles) {
    $relative = Get-RelativeRepositoryPath -FullPath $file
    $content = [System.IO.File]::ReadAllText($file)

    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    $size = (Get-Item -LiteralPath $file).Length

    $maxBackticks = 0

    foreach ($match in [regex]::Matches($content, '`{3,}')) {
        $maxBackticks = [Math]::Max($maxBackticks, $match.Length)
    }

    $fence = '`' * ([Math]::Max(4, $maxBackticks + 1))

    [void]$builder.AppendLine("## FILE: $relative")
    [void]$builder.AppendLine()
    [void]$builder.AppendLine("SHA-256: $hash")
    [void]$builder.AppendLine("Size: $size bytes")
    [void]$builder.AppendLine()
    [void]$builder.AppendLine($fence)
    [void]$builder.AppendLine($content)

    if (-not $content.EndsWith("`n")) {
        [void]$builder.AppendLine()
    }

    [void]$builder.AppendLine($fence)
    [void]$builder.AppendLine()
}

# ==================================================
# 8. SKIPPED FILES
# ==================================================

if ($skippedFiles.Count -gt 0) {
    [void]$builder.AppendLine("## Skipped files")
    [void]$builder.AppendLine()

    foreach ($path in $skippedFiles) {
        [void]$builder.AppendLine("- $path")
    }
}

# ==================================================
# 9. WRITE OUTPUT
# ==================================================

[System.IO.File]::WriteAllText(
    $outputFullPath,
    $builder.ToString(),
    [System.Text.UTF8Encoding]::new($false)
)

$outputSize = (Get-Item -LiteralPath $outputFullPath).Length

# ==================================================
# 10. SUMMARY
# ==================================================

Write-Host ""
Write-Host "Review packet generated successfully." -ForegroundColor Green
Write-Host "Branch: $branch"
Write-Host "Detected changed paths: $($allChangedPaths.Count)"
Write-Host "Included files: $($allFiles.Count)"
Write-Host "Deleted files: $($deletedFiles.Count)"
Write-Host "Skipped files: $($skippedFiles.Count)"
Write-Host "Packet size: $outputSize bytes"
Write-Host "Output: $outputFullPath"

Write-Host ""
Write-Host "Opening review packet..."

try {
    Invoke-Item -LiteralPath $outputFullPath
}
catch {
    Write-Warning "The packet was generated, but could not be opened automatically."
    Write-Warning $_.Exception.Message
}
