@echo OFF
setlocal EnableDelayedExpansion

:: ============================================================
:: download_from_rcp.bat - Download converted files from RCP
:: ============================================================
::
:: Usage: download_from_rcp.bat <local_dest> [remote_dir]
:: Example: download_from_rcp.bat "C:\Dev\...\md_files" "/scratch/docling/output"
::
:: ============================================================

set NAMESPACE=runai-sci-ic-mr-pezeu
set POD_NAME=file-transfer-pod
set LOCAL_DIR=%~1
set REMOTE_DIR=%~2

if "%LOCAL_DIR%"=="" (
    echo.
    echo Usage: download_from_rcp.bat ^<local_dest^> [remote_dir]
    echo Example: download_from_rcp.bat "C:\Dev\...\md_files" "/scratch/docling/output"
    echo.
    exit /b 1
)

if "%REMOTE_DIR%"=="" (
    set REMOTE_DIR=/scratch/docling/output
)

echo.
echo ============================================================
echo  DOWNLOAD FROM RCP
echo ============================================================
echo   Remote: %REMOTE_DIR%
echo   Local:  %LOCAL_DIR%
echo ============================================================
echo.

:: Vérifier que le pod existe
kubectl get pod %POD_NAME% -n %NAMESPACE% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Transfer pod not found!
    echo  Run upload_to_rcp.bat first to create the pod.
    exit /b 1
)

:: Vérifier le contenu à télécharger
echo [1/2] Checking remote files...
kubectl exec %POD_NAME% -n %NAMESPACE% -- sh -c "find %REMOTE_DIR% -name '*.md' 2>/dev/null | wc -l"
echo      markdown files found.

:: Télécharger
echo [2/2] Downloading files...
kubectl cp %NAMESPACE%/%POD_NAME%:%REMOTE_DIR%/ "%LOCAL_DIR%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Download failed!
    exit /b 1
)

echo.
echo ============================================================
echo  DOWNLOAD COMPLETE
echo ============================================================
echo.
echo Files downloaded to: %LOCAL_DIR%
echo.
echo To clean up the RCP pod:
echo   kubectl delete pod %POD_NAME% -n %NAMESPACE%
echo.
echo ============================================================

endlocal