$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$venvDir = Join-Path $projectDir ".venv"
$localBin = "$env:USERPROFILE/.local/bin"
$pythonExe = Join-Path $venvDir "Scripts/python.exe"
$pipExe = Join-Path $venvDir "Scripts/pip.exe"

# 1. Create venv
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}

# 2. Install package
& $pipExe install -e $projectDir

# 3. Ensure local/bin exists
if (-not (Test-Path $localBin)) {
    New-Item -ItemType Directory -Force $localBin | Out-Null
}

# 4. Symlink eetool.exe
$eetoolSource = Join-Path $venvDir "Scripts/eetool.exe"
$eetoolLink = Join-Path $localBin "eetool.exe"
if (Test-Path $eetoolLink) { Remove-Item $eetoolLink -Force }
New-Item -ItemType SymbolicLink -Path $eetoolLink -Target $eetoolSource | Out-Null

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
$skillDir = "C:/Users/yg/.claude/skills/eetool"
if (Test-Path $skillDir) {
    $item = Get-Item $skillDir
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Remove-Item $skillDir -Force
    } else {
        Write-Error "Skill path exists and is not a junction: $skillDir"
    }
}
New-Item -ItemType Junction -Path $skillDir -Target $projectDir | Out-Null

# 7. ATK-Logic GUI detection + proxy DLL deployment + path sync
$StandardPaths = @(
    'D:\Programs\ATK-Logic\ATK-Logic.exe'
    'C:\Program Files\ATK-Logic\ATK-Logic.exe'
    'C:\Program Files (x86)\ATK-Logic\ATK-Logic.exe'
    "$env:LOCALAPPDATA\ATK-Logic\ATK-Logic.exe"
    "$env:ProgramFiles\ATK-Logic\ATK-Logic.exe"
    "${env:ProgramFiles(x86)}\ATK-Logic\ATK-Logic.exe"
)

$GuiExe = $null
foreach ($p in $StandardPaths) {
    if ($p -and (Test-Path $p)) {
        $GuiExe = $p
        break
    }
}

if (-not $GuiExe) {
    Write-Warning "[Install] ATK-Logic.exe not found in standard paths; skipping ATK deployment."
} else {
    $GuiDir = Split-Path $GuiExe
    Write-Host "[Install] Found ATK-Logic GUI: $GuiExe"

    # 7a. Update config.ini (authoritative runtime config)
    $configIni = Join-Path $projectDir "src/eetool/capture/config.ini"
    if (Test-Path $configIni) {
        $iniText = Get-Content $configIni -Raw -Encoding UTF8
        $guiDirFwd = $GuiDir.Replace('\', '/')
        $iniText = $iniText -replace '(?m)^GUI_DIR\s*=.*$', "GUI_DIR = $guiDirFwd"
        Set-Content $configIni -Value $iniText -Encoding UTF8 -NoNewline
        Write-Host "[Install] Updated config.ini GUI_DIR -> $GuiDir"
    }

    # 7b. Update _config.py fallback paths for portability
    $configPy = Join-Path $projectDir "src/eetool/capture/_config.py"
    if (Test-Path $configPy) {
        $pyText = Get-Content $configPy -Raw -Encoding UTF8
        $guiDirEsc = $GuiDir.Replace('\', '\\')
        $appDataAtk = "$env:APPDATA\ALIENTEK\ATK-LogicView".Replace('\', '\\')
        $pyText = $pyText -replace 'return Path\("D:/Programs/ATK-Logic"\)', "return Path(`"$guiDirEsc`")"
        $pyText = $pyText -replace 'APPDATA_ATK = Path\("C:/Users/yg/AppData/Roaming/ALIENTEK/ATK-LogicView"\)', "APPDATA_ATK = Path(`"$appDataAtk`")"
        Set-Content $configPy -Value $pyText -Encoding UTF8 -NoNewline
        Write-Host "[Install] Updated _config.py fallback paths"
    }

    # 7c. Deploy proxy DLL
    $originalDll = Join-Path $GuiDir "Qt5Network.dll"
    $backupDll = Join-Path $GuiDir "Qt5Network_real.dll"
    $proxyDll = Join-Path $projectDir "proxy_dll/outdll/Qt5Network.dll"

    if (-not (Test-Path $proxyDll)) {
        Write-Error "[Install] Proxy DLL not found at $proxyDll — run this script from the project root."
        exit 1
    }
    if (-not (Test-Path $originalDll)) {
        Write-Error "[Install] Original Qt5Network.dll not found at $originalDll"
        exit 1
    }

    $guiProcess = Get-Process -Name 'ATK-Logic' -ErrorAction SilentlyContinue
    if ($guiProcess) {
        Write-Warning "[Install] ATK-Logic GUI is running. Please close it and re-run install.ps1"
        exit 1
    }

    $isProxy = (Get-Item $originalDll).Length -lt 400KB
    if (-not $isProxy -and -not (Test-Path $backupDll)) {
        Copy-Item $originalDll $backupDll -Force
        Write-Host "[Install] Backed up Qt5Network.dll -> Qt5Network_real.dll"
    }

    Copy-Item $proxyDll $originalDll -Force
    Write-Host "[Install] Deployed proxy Qt5Network.dll"

    $deployedSize = (Get-Item $originalDll).Length
    if ($deployedSize -lt 200KB -or $deployedSize -gt 400KB) {
        Write-Warning "[Install] Proxy DLL size unexpected: $($deployedSize / 1KB) KB"
    }

    # 7d. Ensure uiautomation is available (also declared in pyproject.toml)
    & $pipExe install uiautomation | Out-Null

    # 7e. Preflight verification
    Write-Host "[Install] Running ATK-Logic preflight check..."
    & $pythonExe -m eetool.capture.capture.atk_preflight --fix --json
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[Install] Preflight check returned exit code $LASTEXITCODE"
    } else {
        Write-Host "[Install] Preflight check passed"
    }
}

Write-Host "eetool installed. Restart your terminal to use 'eetool'."
