param(
    [string]$Source = "G:\Bjorgsun-26\app",
    [string]$Target = "G:\Bjorgsun-26",
    [string[]]$IncludeDirs = @(
        "core",
        "runtime",
        "systems",
        "scripts",
        "ui",
        "modules",
        "tools",
        "data",
        "doc",
        "docs",
        "models",
        "tessdata",
        "Tesseract",
        "ffmpeg",
        "Modding",
        "vendor",
        "platform-tools",
        "server"
    ),
    [string[]]$ExtraFiles = @(
        "README.md",
        "README.dev.md",
        "CHANGELOG.md",
        "requirements.txt",
        "VERSION",
        "server_start.bat",
        "todo_progress.md",
        "progress_status.txt"
    ),
    [string[]]$DirExcludes = @(".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".idea", ".vscode"),
    [string[]]$FileExcludes = @("*.log", "*.tmp", "*.pyc")
)

function Invoke-RoboSync {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    if (-not (Test-Path $SourcePath)) {
        Write-Warning "Skip missing source: $SourcePath"
        return
    }

    if (-not (Test-Path $TargetPath)) {
        New-Item -ItemType Directory -Path $TargetPath | Out-Null
    }

    $args = @(
        $SourcePath,
        $TargetPath,
        "/E",
        "/XO",
        "/COPY:DAT",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP"
    )

    if ($DirExcludes.Count -gt 0) {
        $args += "/XD"
        $args += $DirExcludes
    }
    if ($FileExcludes.Count -gt 0) {
        $args += "/XF"
        $args += $FileExcludes
    }

    & robocopy @args | Out-Null
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed for $SourcePath -> $TargetPath (code $code)"
    }
}

Write-Host ">>> Syncing stable release"
Write-Host "    Source: $Source"
Write-Host "    Target: $Target"

foreach ($dir in $IncludeDirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $Target $dir
    Invoke-RoboSync -SourcePath $src -TargetPath $dst
}

foreach ($file in $ExtraFiles) {
    $srcFile = Join-Path $Source $file
    if (Test-Path $srcFile) {
        $dstFile = Join-Path $Target $file
        Copy-Item $srcFile $dstFile -Force
    }
}

Write-Host ">>> Stable release sync complete."


