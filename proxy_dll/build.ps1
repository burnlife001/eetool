# ATK-Logic Proxy DLL Build Script (MSVC x64)
param(
    [ValidateSet('Release', 'Debug')]
    [string]$Build = 'Release'
)

$ErrorActionPreference = 'Stop'

$VSBat   = 'D:\Programs\MSStudio\CommunityApp\VC\Auxiliary\Build\vcvars64.bat'
$ProjDir = "$PSScriptRoot"
$OutDir  = Join-Path $ProjDir 'outdll'

# Ensure output directory exists (cleared for a clean build, preserve .gitignore)
if (Test-Path $OutDir) {
    Get-ChildItem -Path $OutDir -File | Where-Object { $_.Name -ne '.gitignore' } | Remove-Item -Force
} else {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$DebugFlags = if ($Build -eq 'Debug') { '/Zi /D_DEBUG' } else { '' }
$Optimize  = if ($Build -eq 'Debug') { '/Od' } else { '/O2' }
$LinkDebug = if ($Build -eq 'Debug') { '/DEBUG' } else { '' }

function Run-VSCmd {
    param([string]$Cmd)
    $fullCmd = "`"$VSBat`" >nul 2>&1 && $Cmd"
    cmd /c $fullCmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Cmd" }
}

Write-Host '========================================' -ForegroundColor Cyan
Write-Host "  Building Proxy DLL: $Build"             -ForegroundColor Cyan
Write-Host "  Output: $OutDir"                         -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan

$clFlags   = "/nologo /LD $Optimize /MT /GS- /utf-8 $DebugFlags"
$linkFlags = "/DEF:`"$ProjDir\Qt5Network_proxy.def`" $LinkDebug"

# cd into $OutDir so .obj lands there; .dll/.lib/.exp go alongside it.
$cmd = "cd /d `"$OutDir`" && cl $clFlags `"$ProjDir\proxy_main.c`" /Fe:Qt5Network.dll /link $linkFlags kernel32.lib user32.lib ws2_32.lib"

Write-Host "[1/1] Compiling proxy_main.c -> $OutDir\Qt5Network.dll..."
Run-VSCmd $cmd

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host "  Build OK: $OutDir\Qt5Network.dll"     -ForegroundColor Green

$dll = Get-Item "$OutDir\Qt5Network.dll"
Write-Host "  Size: $([math]::Round($dll.Length / 1024, 1)) KB" -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green

if (-not ([Environment]::GetCommandLineArgs() -contains '-NonInteractive')) {
    Pause
}
