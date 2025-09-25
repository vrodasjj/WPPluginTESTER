# WordPress Plugin Manager - Inicio Rápido

## 🚀 Instalación en 3 pasos

### 1. Requisitos previos
- Python 3.6 o superior
- Acceso SSH al servidor WordPress
- WP-CLI instalado en el servidor

### 2. Instalación automática
```bash
python install.py
```

### 3. Configuración
1. Copia `config.example.json` a `config.json`
2. Edita `config.json` con tus datos de conexión
3. Ejecuta la aplicación:
```bash
python wp_plugin_manager.py
```

## ⚡ Configuración rápida

### SSH
```json
{
    "ssh": {
        "host": "tu-servidor.com",
        "username": "tu-usuario",
        "password": "tu-contraseña"
    }
}
```

### WordPress
```json
{
    "wordpress": {
        "path": "/var/www/html",
        "url": "https://tu-sitio.com"
    }
}
```

## 🔧 Verificación
1. Abre la aplicación
2. Ve a la pestaña "Configuración"
3. Haz clic en "Probar Conexión SSH"
4. Verifica que WP-CLI funcione

## 📚 Documentación completa
- [README.md](README.md) - Documentación completa
- [RELEASE_NOTES_v1.0.md](RELEASE_NOTES_v1.0.md) - Notas de la versión
- [CHANGELOG.md](CHANGELOG.md) - Historial de cambios

## 🆘 Soporte
Si encuentras problemas, revisa la documentación completa o reporta un issue en GitHub.