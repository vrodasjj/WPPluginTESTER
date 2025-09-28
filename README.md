# WordPress Plugin Manager

## 🎉 Release 2.0 - Sistema Completo de Análisis de Logs

Una aplicación de escritorio profesional para gestionar plugins de WordPress de forma segura a través de conexión SSH. La aplicación permite conectarse a un servidor web, revisar logs de debug, listar plugins instalados y gestionarlos de forma individual o en lote con verificación de salud del sitio.

### ✨ Novedades en v2.0
- **Sistema completo de análisis de logs** con LogManager inteligente
- **Recomendaciones automáticas** basadas en análisis de errores
- **Detección de plugins afectados** por problemas específicos
- **Contadores detallados** por tipo de mensaje (errores, warnings, fatales, info)
- **Rangos de tiempo inteligentes** para análisis temporal
- **Corrección crítica** del error AttributeError en LogAnalysis

## 🚀 Características Principales

### 🔌 Gestión Avanzada de Plugins
- **Escaneo automático** con WP-CLI y fallback tradicional
- **Selección múltiple** con checkboxes para operaciones en lote
- **Activación/Desactivación** individual y masiva con verificación de salud
- **Actualización** individual y en lote de plugins
- **Instalación** desde el repositorio oficial
- **Desinstalación completa** con limpieza
- **Testing individual y masivo** de plugins seleccionados

### 🔍 Monitoreo y Diagnóstico Avanzado
- **Verificación de salud** del sitio web en tiempo real
- **Detección automática** de errores 500 y problemas críticos
- **Sistema completo de análisis de logs** con LogManager inteligente
  - **Contadores detallados**: Errores, warnings, fatales e información
  - **Detección de plugins afectados**: Identifica plugins problemáticos
  - **Recomendaciones automáticas**: Sugerencias basadas en análisis
  - **Rangos de tiempo**: Análisis temporal inteligente
  - **Top errores**: Lista de errores más frecuentes
- **Verificación de WP-CLI** y configuración del servidor

### 🚀 Rendimiento y Estabilidad
- **Timeouts configurables** para prevenir bloqueos indefinidos
- **Indicadores de progreso** en tiempo real durante operaciones
- **Manejo robusto de errores** con múltiples niveles de fallback
- **Conexiones SSH optimizadas** con reintentos automáticos

### 🎨 Interfaz de Usuario (Mejorada en v1.1)
- **Diseño moderno** con colores y estilos actualizados
- **Selección múltiple** con checkboxes y contador dinámico
- **Canvas con scroll** para mejor rendimiento con muchos plugins
- **Ventana más grande** (1200x800) para mejor visualización
- **Barra de progreso visual** para operaciones largas
- **Mensajes de estado detallados** en tiempo real
- **Configuración persistente** de conexiones y rutas

## 📋 Requisitos

### Sistema
- Python 3.7 o superior
- Sistema operativo: Windows, Linux o macOS
- Acceso SSH al servidor web

### Servidor WordPress
- WordPress instalado y funcionando
- WP-CLI instalado (recomendado)
- Acceso SSH con permisos para gestionar archivos de WordPress
- Debug logging habilitado en WordPress

## 🛠️ Instalación

1. **Clonar o descargar** los archivos del proyecto
2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Ejecutar la aplicación**:
   ```bash
   python wp_plugin_manager.py
   ```

## 📖 Uso

### 1. Configuración inicial

1. **Abrir la pestaña "Conexión SSH"**
2. **Completar los datos de conexión**:
   - Servidor: IP o dominio del servidor
   - Usuario: Usuario SSH
   - Contraseña: Contraseña SSH
   - Puerto: Puerto SSH (por defecto 22)
3. **Probar la conexión** antes de conectar
4. **Conectar al servidor**

### 2. Configuración de WordPress

1. **Ir a la pestaña "Configuración"**
2. **Configurar las rutas**:
   - Ruta de WordPress: `/var/www/html` (ejemplo)
   - URL del sitio: `https://tusitio.com`
   - Ruta debug.log: `/var/www/html/wp-content/debug.log`
3. **Guardar configuración**

### 3. Gestión de plugins

1. **Ir a la pestaña "Gestión de Plugins"**
2. **Hacer clic en "Escanear Plugins"** para obtener la lista
3. **Seleccionar los plugins** que desea activar
4. **Hacer clic en "Activar Seleccionados"**

⚠️ **IMPORTANTE**: La aplicación activará los plugins uno por uno y verificará que el sitio siga funcionando después de cada activación. Si detecta problemas, desactivará automáticamente el plugin problemático.

### 4. Monitoreo de logs

1. **Ir a la pestaña "Logs y Debug"**
2. **Hacer clic en "Leer Debug.log"** para ver los errores recientes
3. **Usar "Limpiar Debug.log"** para vaciar el archivo de logs
4. **Usar "Actualizar"** para refrescar la vista

## 🔒 Características de seguridad

### Verificación de salud del sitio
- Antes de activar cada plugin, verifica que el sitio esté funcionando
- Después de activar cada plugin, verifica nuevamente el sitio
- Si detecta errores, desactiva automáticamente el plugin problemático

### Detección de errores
La aplicación detecta los siguientes tipos de errores:
- Fatal errors
- Parse errors
- Call to undefined function/method
- Cannot redeclare errors
- Códigos de respuesta HTTP diferentes a 200

### Reversión automática
Si un plugin causa problemas:
1. Se desactiva automáticamente
2. Se muestra un mensaje detallado del error
3. Se proporcionan instrucciones para resolver el problema

## 📁 Estructura de archivos

```
WPPluginTESTER/
├── wp_plugin_manager.py    # Aplicación principal
├── requirements.txt        # Dependencias de Python
├── README.md              # Documentación
└── config.json            # Configuración (se crea automáticamente)
```

## ⚙️ Configuración avanzada

### Archivo config.json
```json
{
    "ssh": {
        "hostname": "tu-servidor.com",
        "username": "usuario",
        "password": "contraseña",
        "port": 22,
        "key_file": ""
    },
    "wordpress": {
        "path": "/var/www/html",
        "url": "https://tusitio.com",
        "debug_log_path": "/var/www/html/wp-content/debug.log"
    },
    "safety": {
        "check_interval": 5,
        "max_retries": 3,
        "timeout": 30
    }
}
```

### Habilitar debug logging en WordPress
Agregar al archivo `wp-config.php`:
```php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);
```

## 🚨 Instrucciones de emergencia

### Si un plugin causa problemas graves:

1. **Acceso SSH directo**:
   ```bash
   cd /ruta/a/wordpress
   wp plugin deactivate nombre-del-plugin
   ```

2. **Acceso FTP/cPanel**:
   - Renombrar la carpeta del plugin en `/wp-content/plugins/`
   - Ejemplo: `plugin-problematico` → `plugin-problematico-disabled`

3. **Acceso a base de datos**:
   - Editar la tabla `wp_options`
   - Buscar `active_plugins`
   - Remover el plugin de la lista

### Restaurar sitio desde backup:
1. Restaurar archivos desde backup
2. Restaurar base de datos desde backup
3. Verificar que el sitio funcione correctamente

## 🐛 Solución de problemas

### Error de conexión SSH
- Verificar credenciales
- Comprobar que el puerto SSH esté abierto
- Verificar que el usuario tenga permisos suficientes

### WP-CLI no encontrado
- Instalar WP-CLI en el servidor
- O usar métodos alternativos de activación de plugins

### Sitio web no responde
- Verificar que la URL esté correcta
- Comprobar que el sitio esté accesible desde internet
- Verificar configuración de firewall

### Problemas del IDE/Linter

Si tu IDE muestra errores de "import no resuelto" para paramiko:

1. **Verificar instalación**:
   ```bash
   python check_imports.py
   ```

2. **VS Code**: Los archivos `.vscode/settings.json` y `pyrightconfig.json` están configurados

3. **Reinstalar dependencias**:
   ```bash
   pip uninstall paramiko
   pip install paramiko
   ```

4. **Usar entorno virtual**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

## 📞 Soporte

Para problemas o sugerencias:
1. Revisar los logs de debug
2. Verificar la configuración
3. Comprobar permisos del servidor
4. Contactar al administrador del servidor si es necesario

## ⚖️ Licencia

Este proyecto es de código abierto. Úsalo bajo tu propia responsabilidad.

## 🔄 Actualizaciones

Para mantener la aplicación actualizada:
1. Descargar la versión más reciente
2. Hacer backup de tu archivo `config.json`
3. Reemplazar los archivos
4. Restaurar tu configuración