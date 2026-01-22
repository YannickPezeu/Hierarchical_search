@echo OFF
setlocal EnableDelayedExpansion

:: ============================================================
:: run_docling_job.bat - Deploy Docling converter on RCP
:: ============================================================
::
:: AVANT DE LANCER:
:: 1. Créer les dossiers sur ton PVC:
::    - /data/docling/input/   <- mettre tes PDF/HTML ici
::    - /data/docling/output/  <- les .md seront créés ici
::
:: 2. Copier tes fichiers dans /data/docling/input/
::
:: ============================================================

:: --- Configuration ---
set JOB_NAME=docling-converter
set IMAGE_NAME=ic-registry.epfl.ch/mr-pezeu/docling-converter:latest

:: PVC mount - RCP scratch
set PVC_NAME=sci-ic-mr-scratch
set PVC_MOUNT=%PVC_NAME%:/scratch:rw

:: Resources - Docling a besoin de RAM pour les modèles
set CPU=16
set MEMORY=64G
set GPU=1

:: Dossiers sur le PVC
set INPUT_DIR=/scratch/docling/input
set OUTPUT_DIR=/scratch/docling/output
set REPORT_FILE=/scratch/docling/conversion_report.txt

:: --- 1. Nettoyer l'ancien job ---
echo [INFO] Cleaning up previous job: %JOB_NAME%
runai delete job %JOB_NAME% 2>nul
timeout /t 3 /nobreak >nul

:: --- 2. Build Docker image ---
echo.
echo [INFO] Building Docker image: %IMAGE_NAME%
echo [INFO] This may take 5-10 minutes (downloading Docling models)...

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
echo [INFO] Input:  %INPUT_DIR%
echo [INFO] Output: %OUTPUT_DIR%

runai submit %JOB_NAME% ^
    --image %IMAGE_NAME% ^
    --existing-pvc claimname=%PVC_NAME%,path=/scratch ^
    --gpu %GPU% ^
    --cpu %CPU% ^
    --memory %MEMORY% ^
    -e INPUT_DIR=%INPUT_DIR% ^
    -e OUTPUT_DIR=%OUTPUT_DIR% ^
    -e REPORT_FILE=%REPORT_FILE%

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
echo Commands:
echo   runai list jobs              - voir le statut
echo   runai logs %JOB_NAME%        - voir les logs en direct
echo   runai logs %JOB_NAME% -f     - suivre les logs
echo   runai describe job %JOB_NAME% - détails du job
echo.
echo Output:
echo   Les fichiers .md seront dans: %OUTPUT_DIR%
echo   Le rapport de conversion:     %REPORT_FILE%
echo.
echo ============================================================

endlocal