@echo OFF
setlocal EnableDelayedExpansion

:: ============================================================
:: run_docling_job.bat - Deploy Docling converter on RCP
:: ============================================================
::
:: IMAGE OPTIONS (NEW!):
::   IMAGE_MODE=placeholder  -> Just <!-- image --> markers (RECOMMENDED)
::   IMAGE_MODE=referenced   -> Save images as separate files
::   IMAGE_MODE=embedded     -> Base64 inline (WARNING: huge files!)
::   SKIP_IMAGES=true        -> Skip image extraction entirely (fastest)
::
:: ============================================================

:: --- Configuration ---
set JOB_NAME=docling-converter
set IMAGE_NAME=ic-registry.epfl.ch/mr-pezeu/docling-converter:latest

:: PVC mount - RCP scratch
set PVC_NAME=sci-ic-mr-scratch
set PVC_MOUNT=%PVC_NAME%:/scratch:rw

:: Resources
set CPU=16
set MEMORY=64G
set GPU=1

:: Dossiers sur le PVC
set INPUT_DIR=/scratch/docling/input
set OUTPUT_DIR=/scratch/docling/output
set REPORT_FILE=/scratch/docling/conversion_report.txt

:: === IMAGE HANDLING - CHOOSE YOUR MODE ===
:: Option 1: PLACEHOLDER (recommended) - smallest files, text only
set IMAGE_MODE=placeholder
set SKIP_IMAGES=false

:: Option 2: REFERENCED - images saved as separate .png files
:: set IMAGE_MODE=referenced
:: set SKIP_IMAGES=false

:: Option 3: Skip images entirely (fastest)
:: set IMAGE_MODE=placeholder
:: set SKIP_IMAGES=true

:: Option 4: EMBEDDED - WARNING: can create 10GB+ files!
:: set IMAGE_MODE=embedded
:: set SKIP_IMAGES=false

:: --- 1. Nettoyer l'ancien job ---
echo [INFO] Cleaning up previous job: %JOB_NAME%
runai delete job %JOB_NAME% 2>nul
timeout /t 3 /nobreak >nul

:: --- 2. Build Docker image ---
echo.
echo [INFO] Building Docker image: %IMAGE_NAME%

docker build --tag %IMAGE_NAME% -f Dockerfile.docling . > docker_docling_build.log 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker build failed! Check docker_docling_build.log
    type docker_docling_build.log
    GOTO :EOF
)
echo [INFO] Docker build successful

:: --- 3. Push image ---
echo.
echo [INFO] Pushing image to registry...
docker push %IMAGE_NAME%

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker push failed!
    GOTO :EOF
)
echo [INFO] Push successful

:: --- 4. Submit Run:AI job ---
echo.
echo [INFO] Submitting job to Run:AI...
echo [INFO] Input:      %INPUT_DIR%
echo [INFO] Output:     %OUTPUT_DIR%
echo [INFO] Image Mode: %IMAGE_MODE%
echo [INFO] Skip Images: %SKIP_IMAGES%

runai submit %JOB_NAME% ^
    --image %IMAGE_NAME% ^
    --existing-pvc claimname=%PVC_NAME%,path=/scratch ^
    --gpu %GPU% ^
    --cpu %CPU% ^
    --memory %MEMORY% ^
    -e INPUT_DIR=%INPUT_DIR% ^
    -e OUTPUT_DIR=%OUTPUT_DIR% ^
    -e REPORT_FILE=%REPORT_FILE% ^
    -e IMAGE_MODE=%IMAGE_MODE% ^
    -e SKIP_IMAGES=%SKIP_IMAGES%

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Job submission failed!
    GOTO :EOF
)

:: --- 5. Instructions ---
echo.
echo ============================================================
echo [SUCCESS] Job submitted: %JOB_NAME%
echo ============================================================
echo.
echo IMAGE SETTINGS:
echo   IMAGE_MODE=%IMAGE_MODE%
echo   SKIP_IMAGES=%SKIP_IMAGES%
echo.
echo Commands:
echo   runai list jobs              - voir le statut
echo   runai logs %JOB_NAME%        - voir les logs en direct
echo   runai logs %JOB_NAME% -f     - suivre les logs
echo   runai describe job %JOB_NAME% - details du job
echo.
echo Output:
echo   Les fichiers .md seront dans: %OUTPUT_DIR%
echo   Le rapport de conversion:     %REPORT_FILE%
echo.
echo ============================================================

endlocal