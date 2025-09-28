@echo off
echo ========================================
echo WordPress Plugin Manager v2.0.0 Upload
echo ========================================
echo.

REM Configurar variables
set REPO_URL=https://github.com/vrodasjj/WPPluginTESTER.git
set PROJECT_DIR=Z:\Proyectos\WPPluginTESTER
set TEMP_DIR=C:\temp\wp-plugin-manager-v2

echo Repositorio configurado: %REPO_URL%
echo NOTA: Este es un repositorio privado
echo.

echo 1. Creando directorio temporal...
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

echo 2. Clonando repositorio existente...
cd /d C:\temp
git clone "%REPO_URL%" wp-plugin-manager-v2
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo clonar el repositorio
    echo Verifica que:
    echo 1. La URL sea correcta
    echo 2. Tengas acceso al repositorio
    echo 3. Git este instalado y configurado
    echo.
    pause
    exit /b 1
)
cd wp-plugin-manager-v2

echo 3. Creando rama para preservar v1.0.0...
git checkout -b release/v1.0.0
git push origin release/v1.0.0

echo 4. Volviendo a rama main...
git checkout main

echo 5. Copiando archivos actualizados...
copy "%PROJECT_DIR%\wp_plugin_manager.py" .
copy "%PROJECT_DIR%\log_manager.py" .
copy "%PROJECT_DIR%\wp_cli_manager.py" .
copy "%PROJECT_DIR%\install.py" .
copy "%PROJECT_DIR%\setup.py" .
copy "%PROJECT_DIR%\check_imports.py" .
copy "%PROJECT_DIR%\requirements.txt" .
copy "%PROJECT_DIR%\requirements-dev.txt" .
copy "%PROJECT_DIR%\config.example.json" .
copy "%PROJECT_DIR%\.env" .
copy "%PROJECT_DIR%\.gitignore" .
copy "%PROJECT_DIR%\.pylintrc" .
copy "%PROJECT_DIR%\pyrightconfig.json" .
copy "%PROJECT_DIR%\README.md" .
copy "%PROJECT_DIR%\CHANGELOG.md" .
copy "%PROJECT_DIR%\LICENSE" .
copy "%PROJECT_DIR%\LICENSE_INFO.md" .
copy "%PROJECT_DIR%\VERSION" .
copy "%PROJECT_DIR%\QUICK_START.md" .
copy "%PROJECT_DIR%\DIAGNOSTICS_SOLUTIONS.md" .
copy "%PROJECT_DIR%\MEJORAS_IMPLEMENTADAS.md" .
copy "%PROJECT_DIR%\RELEASE_NOTES_v2.0.md" .

echo 6. Agregando archivos al repositorio...
git add .

echo 7. Creando commit para v2.0.0...
git commit -m "Release 2.0.0: WordPress Plugin Manager con Analisis Inteligente de Logs"

echo 8. Subiendo cambios a GitHub...
git push origin main

echo 9. Creando tag para v2.0.0...
git tag v2.0.0
git push origin v2.0.0

echo.
echo ========================================
echo SUBIDA COMPLETADA EXITOSAMENTE
echo ========================================
echo.
echo Repositorio: %REPO_URL%
echo Rama principal: main (v2.0.0)
echo Rama preservada: release/v1.0.0 (v1.0.0)
echo Tags: v1.0.0, v2.0.0
echo.
echo Proximos pasos:
echo 1. Ve a GitHub: %REPO_URL%
echo 2. Crea un Release para v2.0.0
echo 3. Usa el contenido de RELEASE_NOTES_v2.0.md como descripcion
echo.
echo WordPress Plugin Manager v2.0.0 esta oficialmente en GitHub!
echo.
pause