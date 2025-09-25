#!/usr/bin/env python3
"""
WordPress Plugin Manager - Installation Script
Release 1.0 Installation and Setup

This script helps set up the WordPress Plugin Manager for first-time use.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_python_version():
    """Verificar que la versión de Python sea compatible"""
    if sys.version_info < (3, 6):
        print("❌ Error: Se requiere Python 3.6 o superior")
        print(f"   Versión actual: {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} - Compatible")
    return True

def check_dependencies():
    """Verificar e instalar dependencias requeridas"""
    required_packages = [
        'paramiko',
        'requests',
        'tkinter'  # Generalmente viene con Python
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'tkinter':
                import tkinter
            else:
                __import__(package)
            print(f"✅ {package} - Instalado")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - No encontrado")
    
    if missing_packages:
        print(f"\n📦 Instalando paquetes faltantes: {', '.join(missing_packages)}")
        for package in missing_packages:
            if package == 'tkinter':
                print("⚠️  tkinter debe instalarse manualmente según tu sistema operativo")
                continue
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✅ {package} instalado correctamente")
            except subprocess.CalledProcessError:
                print(f"❌ Error instalando {package}")
                return False
    
    return True

def create_default_config():
    """Crear archivo de configuración por defecto"""
    config_path = Path("config.json")
    
    if config_path.exists():
        print("✅ Archivo de configuración ya existe")
        return True
    
    default_config = {
        "ssh": {
            "host": "",
            "port": 22,
            "username": "",
            "password": "",
            "key_file": ""
        },
        "wordpress": {
            "path": "",
            "url": "",
            "db_host": "localhost",
            "db_name": "",
            "db_user": "",
            "db_password": ""
        },
        "settings": {
            "timeout": 30,
            "auto_backup": True,
            "check_health": True
        }
    }
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print("✅ Archivo de configuración creado: config.json")
        return True
    except Exception as e:
        print(f"❌ Error creando configuración: {e}")
        return False

def check_wp_cli_manager():
    """Verificar que el módulo WP-CLI Manager esté presente"""
    wp_cli_path = Path("wp_cli_manager.py")
    
    if wp_cli_path.exists():
        print("✅ WP-CLI Manager encontrado")
        return True
    else:
        print("❌ WP-CLI Manager no encontrado")
        print("   Asegúrate de que wp_cli_manager.py esté en el mismo directorio")
        return False

def run_initial_setup():
    """Ejecutar configuración inicial"""
    print("\n🔧 Configuración Inicial")
    print("=" * 50)
    
    print("\n1. Configuración SSH:")
    print("   - Edita config.json con los datos de tu servidor")
    print("   - Host, puerto, usuario y contraseña/clave SSH")
    
    print("\n2. Configuración WordPress:")
    print("   - Ruta de instalación de WordPress en el servidor")
    print("   - URL del sitio web")
    print("   - Datos de conexión a la base de datos")
    
    print("\n3. WP-CLI (Recomendado):")
    print("   - Instala WP-CLI en tu servidor para mejor rendimiento")
    print("   - El sistema funcionará sin WP-CLI pero con funcionalidad limitada")
    
    print("\n4. Ejecutar la aplicación:")
    print("   python wp_plugin_manager.py")

def main():
    """Función principal de instalación"""
    print("🚀 WordPress Plugin Manager - Release 1.0")
    print("   Instalación y Configuración")
    print("=" * 50)
    
    # Verificar Python
    if not check_python_version():
        return False
    
    # Verificar dependencias
    if not check_dependencies():
        return False
    
    # Verificar WP-CLI Manager
    if not check_wp_cli_manager():
        return False
    
    # Crear configuración por defecto
    if not create_default_config():
        return False
    
    # Configuración inicial
    run_initial_setup()
    
    print("\n🎉 ¡Instalación completada exitosamente!")
    print("\n📝 Próximos pasos:")
    print("   1. Edita config.json con tus datos de conexión")
    print("   2. Ejecuta: python wp_plugin_manager.py")
    print("   3. Usa la pestaña 'Conexión' para probar la conectividad")
    print("   4. ¡Comienza a gestionar tus plugins!")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ La instalación no se completó correctamente")
        print("   Revisa los errores anteriores y vuelve a intentar")
        sys.exit(1)
    else:
        print("\n✅ Instalación exitosa - ¡Listo para usar!")
        sys.exit(0)