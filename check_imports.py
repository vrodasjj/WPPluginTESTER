#!/usr/bin/env python3
"""
Script para verificar que todas las importaciones están disponibles
"""

def check_imports():
    """Verificar que todas las dependencias están instaladas"""
    try:
        import paramiko
        print(f"✅ paramiko {paramiko.__version__} - OK")
    except ImportError as e:
        print(f"❌ paramiko - ERROR: {e}")
        return False
    
    try:
        import requests
        print(f"✅ requests {requests.__version__} - OK")
    except ImportError as e:
        print(f"❌ requests - ERROR: {e}")
        return False
    
    try:
        import tkinter as tk  # noqa: F401
        print(f"✅ tkinter - OK")
    except ImportError as e:
        print(f"❌ tkinter - ERROR: {e}")
        return False
    
    print("\n🎉 Todas las dependencias están correctamente instaladas!")
    return True

if __name__ == "__main__":
    check_imports()