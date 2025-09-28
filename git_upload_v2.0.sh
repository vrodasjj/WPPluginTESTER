#!/bin/bash

echo "========================================"
echo "WordPress Plugin Manager v2.0.0 Upload"
echo "========================================"
echo

# Configurar variables
REPO_URL="https://github.com/vrodasjj/WPPluginTESTER.git"
echo "Repositorio configurado: $REPO_URL"
echo "NOTA: Este es un repositorio privado"
PROJECT_DIR="/z/Proyectos/WPPluginTESTER"
TEMP_DIR="/tmp/wp-plugin-manager-v2"

echo "1. Creando directorio temporal..."
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo "2. Clonando repositorio existente..."
cd /tmp
git clone "$REPO_URL" wp-plugin-manager-v2
cd wp-plugin-manager-v2

echo "3. Creando rama para preservar v1.0.0..."
git checkout -b release/v1.0.0
git push origin release/v1.0.0

echo "4. Volviendo a main para v2.0.0..."
git checkout main

echo "5. Copiando archivos actualizados de v2.0.0..."
# Copiar archivos principales (excluir archivos sensibles)
cp "$PROJECT_DIR/wp_plugin_manager.py" .
cp "$PROJECT_DIR/log_manager.py" .
cp "$PROJECT_DIR/wp_cli_manager.py" .
cp "$PROJECT_DIR/VERSION" .

# Copiar configuración
cp "$PROJECT_DIR/requirements.txt" .
cp "$PROJECT_DIR/requirements-dev.txt" .
cp "$PROJECT_DIR/config.example.json" .
cp "$PROJECT_DIR/setup.py" .
cp "$PROJECT_DIR/install.py" .

# Copiar documentación actualizada
cp "$PROJECT_DIR/README.md" .
cp "$PROJECT_DIR/CHANGELOG.md" .
cp "$PROJECT_DIR/RELEASE_NOTES_v2.0.md" .
cp "$PROJECT_DIR/MEJORAS_IMPLEMENTADAS.md" .
cp "$PROJECT_DIR/FILES_LIST_v2.0.md" .
cp "$PROJECT_DIR/GITHUB_UPLOAD_v2.0_INSTRUCTIONS.md" .

# Copiar documentación existente
cp "$PROJECT_DIR/RELEASE_NOTES_v1.0.md" .
cp "$PROJECT_DIR/RELEASE_NOTES_v1.1.md" .
cp "$PROJECT_DIR/RELEASE_1.0_SUMMARY.md" .
cp "$PROJECT_DIR/RELEASE_1.0_FILES.md" .
cp "$PROJECT_DIR/QUICK_START.md" .
cp "$PROJECT_DIR/DIAGNOSTICS_SOLUTIONS.md" .
cp "$PROJECT_DIR/GITHUB_UPLOAD_INSTRUCTIONS.md" .

# Copiar configuración de desarrollo
cp "$PROJECT_DIR/.gitignore" .
cp "$PROJECT_DIR/.pylintrc" .
cp "$PROJECT_DIR/pyrightconfig.json" .
cp "$PROJECT_DIR/check_imports.py" .

# Copiar licencias
cp "$PROJECT_DIR/LICENSE" .
cp "$PROJECT_DIR/LICENSE_INFO.md" .

# Copiar capturas de pantalla
cp "$PROJECT_DIR/screenshot.png" .
cp "$PROJECT_DIR/screenshot_improved.png" .
cp "$PROJECT_DIR/screenshot_testing.png" .

echo "6. Añadiendo archivos al repositorio..."
git add .

echo "7. Creando commit para v2.0.0..."
git commit -m "Release 2.0.0: WordPress Plugin Manager con Análisis Inteligente de Logs

🎯 NUEVAS FUNCIONALIDADES PRINCIPALES:
- Sistema completo de análisis de logs con LogManager inteligente
- Recomendaciones automáticas basadas en análisis de errores
- Detección de plugins afectados por problemas
- Contadores detallados (errores, warnings, fatales, info)
- Rangos temporales inteligentes para análisis
- Lista de errores principales priorizados

🛠️ CORRECCIONES CRÍTICAS:
- Fix AttributeError: LogAnalysis object has no attribute 'info_count'
- Prevención de bucles infinitos en verificación de estado
- Mejora en estabilidad de la interfaz

🔧 MEJORAS TÉCNICAS:
- Arquitectura mejorada del LogManager
- Nuevos métodos: _generate_recommendations(), _extract_affected_plugins()
- API interna actualizada para mejor rendimiento
- Manejo robusto de errores mejorado

📊 ANÁLISIS INTELIGENTE:
- Evaluación automática de gravedad de problemas
- Sugerencias contextuales específicas por tipo de error
- Priorización de acciones por importancia

BREAKING CHANGES:
- Nueva arquitectura LogManager con atributos adicionales
- API interna actualizada para análisis avanzado

Versión 2.0.0 - Análisis de logs profesional para WordPress"

echo "8. Subiendo cambios a GitHub..."
git push origin main

echo "9. Creando tag para v2.0.0..."
git tag -a v2.0.0 -m "Release 2.0.0 - WordPress Plugin Manager con Análisis Inteligente de Logs"
git push origin v2.0.0

echo
echo "========================================"
echo "✅ SUBIDA COMPLETADA EXITOSAMENTE"
echo "========================================"
echo
echo "📍 Repositorio: $REPO_URL"
echo "📍 Rama principal: main (v2.0.0)"
echo "📍 Rama preservada: release/v1.0.0 (v1.0.0)"
echo "📍 Tags: v1.0.0, v2.0.0"
echo
echo "🎯 Próximos pasos:"
echo "1. Ve a GitHub: $REPO_URL"
echo "2. Crea un Release para v2.0.0"
echo "3. Usa el contenido de RELEASE_NOTES_v2.0.md como descripción"
echo
echo "¡WordPress Plugin Manager v2.0.0 está oficialmente en GitHub! 🚀"
echo