$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$venvDir = Join-Path $projectDir ".venv"
$localBin = "$env:USERPROFILE/.local/bin"

# 1. Create venv
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}

# 2. Install package
& "$venvDir/Scripts/pip.exe" install -e $projectDir

# 3. Ensure local/bin exists
if (-not (Test-Path $localBin)) {
    New-Item -ItemType Directory -Force $localBin | Out-Null
}

# 4. Symlink ee.exe
$eeSource = Join-Path $venvDir "Scripts/ee.exe"
$eeLink = Join-Path $localBin "ee.exe"
if (Test-Path $eeLink) { Remove-Item $eeLink -Force }
New-Item -ItemType SymbolicLink -Path $eeLink -Target $eeSource | Out-Null

# 5. Add to PATH if missing
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$localBin*") {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$userPath;$localBin",
        "User"
    )
}

# 6. Create skill junction
$skillDir = "C:/Users/yg/.claude/skills/ee-toolkit"
if (Test-Path $skillDir) {
    $item = Get-Item $skillDir
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Remove-Item $skillDir -Force
    } else {
        Write-Error "Skill path exists and is not a junction: $skillDir"
    }
}
New-Item -ItemType Junction -Path $skillDir -Target $projectDir | Out-Null

Write-Host "ee-toolkit installed. Restart your terminal to use 'ee'."
