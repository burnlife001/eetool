$ErrorActionPreference = "Stop"
$project = "{{PROJECT_NAME}}.uvprojx"
$axf = "$PSScriptRoot\Objects\{{OUTPUT_NAME}}.axf"

Push-Location $PSScriptRoot

# ---------- Build ----------
for ($attempt = 1; $attempt -le 2; $attempt++) {
    # UV4.exe does not reliably return non-zero exit codes; parse log instead
    & '{{UV4_PATH}}' -b $project -j0 -o build.log 2>&1 | Out-Null

    $buildLog = Get-Content "$PSScriptRoot\build.log" -Raw
    if ($buildLog -match '(\d+)\s*Error\(s\)') {
        $errors = [int]$Matches[1]
    } else {
        $errors = -1
    }
    if ($buildLog -match '(\d+)\s*Warning\(s\)') {
        $warnings = [int]$Matches[1]
    } else {
        $warnings = 0
    }

    if ($errors -ne 0) {
        $tag = if ($attempt -gt 1) { " (retry)" } else { "" }
        Write-Host "BUILD FAILED${tag}: $errors Error(s), $warnings Warning(s)"
        Get-Content "$PSScriptRoot\build.log" -Tail 30
        Pop-Location
        exit 1
    }

    Write-Host "Build: $errors Error(s), $warnings Warning(s)"

    if (-not (Test-Path $axf)) {
        Write-Host "ERROR: $axf not found after build"
        Pop-Location
        exit 1
    }

    $axfTime = (Get-Item $axf).LastWriteTime
    $stale = Get-ChildItem -Path "$PSScriptRoot\.." -Recurse -Include *.c,*.h,*.s `
        | Where-Object {
            $_.LastWriteTime -gt $axfTime -and
            $_.FullName -notmatch '\\(\.git|\.claude|MDK-ARM\\Objects|docs)\\'
        }

    if (-not $stale) {
        Write-Host "BUILD OK"
        break
    }

    if ($attempt -eq 1) {
        Write-Host "Incremental build stale, cleaning objects and retrying..."
        $stale | ForEach-Object { Write-Host "  $($_.FullName) ($($_.LastWriteTime)) > .axf" }
        Remove-Item "$PSScriptRoot\Objects\*.o" -Force -ErrorAction SilentlyContinue
        continue
    }

    Write-Host "BUILD STALE (retry failed): $axf ($axfTime)"
    $stale | ForEach-Object { Write-Host "  $($_.FullName) ($($_.LastWriteTime))" }
    Pop-Location
    exit 1
}

# ---------- Download ----------
& '{{UV4_PATH}}' -f $project -j0 -o download.log 2>&1 | Out-Null
$dlLog = Get-Content "$PSScriptRoot\download.log" -Raw

if ($dlLog -match 'Verify OK') {
    Write-Host "DOWNLOAD OK"
    Pop-Location
    exit 0
} else {
    Write-Host "DOWNLOAD FAILED"
    Get-Content "$PSScriptRoot\download.log" -Tail 20
    Pop-Location
    exit 1
}
