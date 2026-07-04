$ErrorActionPreference = "Stop"
$project = "{{PROJECT_NAME}}.uvprojx"

Push-Location $PSScriptRoot
& '{{UV4_PATH}}' -f $project -j0 -o download.log 2>&1 | Out-Null
$log = Get-Content "$PSScriptRoot\download.log" -Raw
Pop-Location

if ($log -match 'Verify OK') {
    Write-Host "DOWNLOAD OK"
    exit 0
} else {
    Write-Host "DOWNLOAD FAILED"
    Get-Content "$PSScriptRoot\download.log" -Tail 20
    exit 1
}
