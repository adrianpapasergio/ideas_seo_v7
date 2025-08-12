@echo off
setlocal ENABLEEXTENSIONS

REM ====== Config ======
set "BRANCH=main"
set "APP_FILE=app.py"

REM ====== Ir a la carpeta del proyecto (donde está el .bat) ======
cd /d "%~dp0"

echo ============================================
echo  Proyecto: %CD%
echo  Rama: %BRANCH%
echo ============================================

REM ====== Verificar Git ======
where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git no esta instalado o no esta en PATH.
  echo Descargalo: https://git-scm.com/download/win
  pause
  exit /b 1
)

REM ====== Sincronizar con GitHub ======
echo.
echo [GIT] Preparando sincronizacion...

REM Detectar si hay repo git
if not exist ".git" (
  echo [ERROR] No parece un repositorio Git inicializado.
  echo Ejecuta una vez:  git init  y  git remote add origin https://github.com/adrianpapasergio/ideas_seo_v7.git
  pause
  exit /b 1
)

REM Guardar si hay cambios sin commitear (incluye untracked)
for /f "tokens=1,2*" %%a in ('git status --porcelain') do set DIRTY=1
if defined DIRTY (
  echo [GIT] Cambios locales detectados. Haciendo stash temporal...
  git stash push -u -m "auto-stash run_and_update" >nul
  set STASHED=1
) else (
  set STASHED=
)

echo [GIT] Fetch remoto...
git fetch origin
if errorlevel 1 (
  echo [ERROR] git fetch fallo.
  if defined STASHED git stash pop
  pause
  exit /b 1
)

echo [GIT] Rebase con origin/%BRANCH%...
git rebase origin/%BRANCH%
if errorlevel 1 (
  echo.
  echo [ERROR] Hubo conflictos durante el rebase.
  echo - Resuelvelos (git status para ver archivos).
  echo - Luego: git add ... y git rebase --continue
  echo - Si queres abortar: git rebase --abort
  echo.
  echo Si se hizo stash automatico, no se aplicara hasta resolver el rebase.
  pause
  exit /b 1
)

REM Reaplicar stash si existia
if defined STASHED (
  echo [GIT] Reaplicando cambios locales (stash pop)...
  git stash pop
  if errorlevel 1 (
    echo.
    echo [ATENCION] Conflictos al aplicar tu stash.
    echo - Resuelvelos manualmente y commitea.
    echo - Luego podes re-ejecutar este script.
    pause
    exit /b 1
  )
)

echo [GIT] Listo. Working tree sincronizado.
echo.

REM ====== Verificar Python / crear venv ======
where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instalar desde https://www.python.org/downloads/windows/
    pause
    exit /b 1
  ) else (
    set PYTHON=py
  )
) else (
  set PYTHON=python
)

if not exist "venv" (
  echo [VENV] Creando entorno virtual...
  %PYTHON% -m venv venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
  )
)

echo [VENV] Activando entorno...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar el entorno virtual.
  pause
  exit /b 1
)

REM ====== Instalar dependencias ======
if exist "requirements.txt" (
  echo [PIP] Instalando/actualizando dependencias...
  pip install -r requirements.txt
) else (
  echo [PIP] No hay requirements.txt (continuo de todas formas)
)

REM ====== Variables FLASK y arranque ======
set FLASK_APP=%APP_FILE%
set FLASK_ENV=development

echo.
echo ============================================
echo  Iniciando: %APP_FILE%
echo  URL: http://127.0.0.1:5000
echo ============================================
echo.

%PYTHON% "%APP_FILE%"
set EXITCODE=%ERRORLEVEL%

echo.
echo [FIN] El servidor termino con codigo %EXITCODE%.
pause
endlocal
