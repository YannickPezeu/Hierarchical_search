# ============================================================
# download_from_rcp.ps1 - Download converted files from RCP
# ============================================================
#
# Usage: .\download_from_rcp.ps1 -LocalDir <path> [-RemoteDir <path>]
# Example: .\download_from_rcp.ps1 -LocalDir "C:\Dev\...\md_files" -RemoteDir "/scratch/docling/output"
#
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$LocalDir,
    
    [Parameter(Mandatory=$false)]
    [string]$RemoteDir = "/scratch/docling/output",

    [Parameter(Mandatory=$false)]
    [switch]$DownloadBySubdir = $false
)

$NAMESPACE = "runai-sci-ic-mr-pezeu"
$POD_NAME = "file-transfer-pod"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " DOWNLOAD FROM RCP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Remote: $RemoteDir"
Write-Host "  Local:  $LocalDir"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if pod exists
Write-Host "[1/4] Checking pod status..." -ForegroundColor Yellow
$podStatus = kubectl get pod $POD_NAME -n $NAMESPACE 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: Transfer pod not found!" -ForegroundColor Red
    Write-Host "  Create it first with: kubectl apply -f transfer_pod.yaml"
    exit 1
}
Write-Host "     Pod is running." -ForegroundColor Green

# Check remote files
Write-Host "[2/4] Checking remote files..." -ForegroundColor Yellow
$fileCount = kubectl exec $POD_NAME -n $NAMESPACE -- sh -c "find $RemoteDir -name '*.md' 2>/dev/null | wc -l"
Write-Host "     $fileCount markdown files found." -ForegroundColor Green

# Get list of top-level subdirectories
Write-Host "[3/4] Discovering directory structure..." -ForegroundColor Yellow
$subdirs = kubectl exec $POD_NAME -n $NAMESPACE -- sh -c "ls -1 $RemoteDir" 2>&1
$subdirList = $subdirs -split "`n" | Where-Object { $_.Trim() -ne "" }
Write-Host "     Found $($subdirList.Count) top-level directories: $($subdirList -join ', ')" -ForegroundColor Green

# Download files
Write-Host "[4/4] Downloading files..." -ForegroundColor Yellow
Write-Host ""

if ($DownloadBySubdir) {
    # Download subdirectory by subdirectory with progress
    $currentDir = 0
    $totalDirs = $subdirList.Count

    foreach ($subdir in $subdirList) {
        $currentDir++
        $percentage = [math]::Round(($currentDir / $totalDirs) * 100, 1)

        Write-Host "[$currentDir/$totalDirs] ($percentage%) Downloading: $subdir" -ForegroundColor Cyan

        # Count files in this subdirectory
        $subdirFileCount = kubectl exec $POD_NAME -n $NAMESPACE -- sh -c "find $RemoteDir/$subdir -name '*.md' 2>/dev/null | wc -l"
        Write-Host "           Files in directory: $subdirFileCount" -ForegroundColor Gray

        # Download this subdirectory
        $remotePath = "$RemoteDir/$subdir"
        $localPath = Join-Path $LocalDir $subdir

        # Create local directory if it doesn't exist
        New-Item -ItemType Directory -Force -Path $localPath | Out-Null

        # Download using relative path approach
        Push-Location $LocalDir
        kubectl -n $NAMESPACE cp "${POD_NAME}:${remotePath}" "./$subdir" 2>&1 | Out-Null
        Pop-Location

        if ($LASTEXITCODE -eq 0) {
            Write-Host "           Done" -ForegroundColor Green
        } else {
            Write-Host "           Failed to download" -ForegroundColor Red
        }
        Write-Host ""
    }
} else {
    # Download everything at once using relative path
    Write-Host "Downloading all files at once..." -ForegroundColor Cyan
    Write-Host "Command: kubectl -n $NAMESPACE cp ${POD_NAME}:${RemoteDir} $LocalDir" -ForegroundColor Gray
    Write-Host ""

    Push-Location $LocalDir
    kubectl -n $NAMESPACE cp "${POD_NAME}:${RemoteDir}" .
    Pop-Location

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ERROR: Download failed!" -ForegroundColor Red
        Write-Host "  Try running with -DownloadBySubdir flag for progress tracking:" -ForegroundColor Yellow
        Write-Host "    .\download_from_rcp.ps1 -LocalDir '$LocalDir' -DownloadBySubdir" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " DOWNLOAD COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Verify downloaded files
Write-Host "Verifying download..." -ForegroundColor Yellow
$downloadedCount = (Get-ChildItem -Path $LocalDir -Filter "*.md" -Recurse | Measure-Object).Count
Write-Host "  Total .md files in local directory: $downloadedCount" -ForegroundColor Green
Write-Host "  Expected from remote: $fileCount" -ForegroundColor Green

if ($downloadedCount -eq $fileCount) {
    Write-Host "  File count matches!" -ForegroundColor Green
} else {
    Write-Host "  File count mismatch. Some files may not have been downloaded." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Files downloaded to: $LocalDir"
Write-Host ""
Write-Host "To clean up the RCP pod:" -ForegroundColor Yellow
Write-Host "  kubectl delete pod $POD_NAME -n $NAMESPACE"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan