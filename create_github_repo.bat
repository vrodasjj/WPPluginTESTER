@echo off
chcp 65001 >nul
echo ========================================
echo Crear Repositorio GitHub para WordPress Plugin Manager
echo ========================================
echo.

echo OPCIONES PARA CREAR EL REPOSITORIO:
echo.
echo 1. CREAR NUEVO REPOSITORIO EN GITHUB (Recomendado)
echo    - Ve a: https://github.com/new
echo    - Nombre del repositorio: wordpress-plugin-manager
echo    - Descripcion: WordPress Plugin Manager v2.0.0 - Advanced plugin management with intelligent log analysis
echo    - Publico: Si
echo    - NO inicializar con README (importante)
echo    - NO agregar .gitignore
echo    - NO agregar licencia
echo.
echo 2. USAR REPOSITORIO EXISTENTE
echo    - Si ya tienes un repositorio, necesitas la URL completa
echo    - Formato: https://github.com/TU_USUARIO/TU_REPOSITORIO.git
echo.
echo ========================================
echo.

set /p OPTION="Que opcion prefieres? (1=Crear nuevo, 2=Usar existente): "

if "%OPTION%"=="1" (
    echo.
    echo PASOS PARA CREAR EL REPOSITORIO:
    echo.
    echo 1. Abre tu navegador en: https://github.com/new
    echo 2. Completa el formulario:
    echo    - Repository name: wordpress-plugin-manager
    echo    - Description: WordPress Plugin Manager v2.0.0 - Advanced plugin management with intelligent log analysis
    echo    - Public repository
    echo    - NO marcar "Add a README file"
    echo    - NO marcar "Add .gitignore"
    echo    - NO marcar "Choose a license"
    echo 3. Haz clic en "Create repository"
    echo 4. Copia la URL del repositorio que aparece (algo como: https://github.com/TU_USUARIO/wordpress-plugin-manager.git)
    echo.
    echo Cuando hayas creado el repositorio, ejecuta git_upload_v2.0.bat
    echo y pega la URL cuando te la pida.
    echo.
) else if "%OPTION%"=="2" (
    echo.
    echo USANDO REPOSITORIO EXISTENTE:
    echo.
    echo Asegurate de tener la URL completa de tu repositorio.
    echo Formato: https://github.com/TU_USUARIO/TU_REPOSITORIO.git
    echo.
    echo Luego ejecuta git_upload_v2.0.bat y pega la URL cuando te la pida.
    echo.
) else (
    echo.
    echo Opcion no valida. Ejecuta el script nuevamente.
    echo.
)

echo ========================================
echo INFORMACION ADICIONAL:
echo ========================================
echo.
echo Si necesitas ayuda con Git:
echo 1. Instala Git desde: https://git-scm.com/download/win
echo 2. Configura tu usuario:
echo    git config --global user.name "Tu Nombre"
echo    git config --global user.email "tu@email.com"
echo.
echo Si necesitas autenticacion:
echo 1. Usa GitHub Desktop: https://desktop.github.com/
echo 2. O configura un token personal: https://github.com/settings/tokens
echo.

pause