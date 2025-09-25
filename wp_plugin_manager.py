#!/usr/bin/env python3
"""
WordPress Plugin Manager - Release 1.0
Aplicación para gestionar plugins de WordPress de forma automatizada y segura via SSH

Version: 1.0.0
Release Date: January 2025
Status: Stable Release

Features:
- SSH connection management with timeouts
- Automatic plugin scanning with WP-CLI and traditional fallback
- Real-time progress indicators
- Robust error handling with multiple fallback levels
- Site health monitoring and error detection
- Plugin testing and backup functionality
"""

__version__ = "1.0.0"
__author__ = "WordPress Plugin Manager Team"
__status__ = "Stable"

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import paramiko
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from wp_cli_manager import WPCLIManager

class WordPressPluginManager:
    def __init__(self):
        self.ssh_client = None
        self.config = self.load_config()
        self.plugins_data = []
        self.is_connected = False
        self.wp_cli_manager = None
        
        # Variables para testing automatizado
        self.testing_active = False
        self.current_backup = None
        
        # Flag para prevenir escaneos simultáneos
        self.scanning_in_progress = False
        
        # Sistema de cooldown para prevenir diálogos repetitivos
        self.last_warning_time = {}
        self.warning_cooldown = 10  # segundos
        
        # Crear la interfaz gráfica
        self.setup_gui()
        
    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        config_file = Path("config.json")
        default_config = {
            "ssh": {
                "hostname": "",
                "username": "",
                "password": "",
                "port": 22,
                "key_file": ""
            },
            "wordpress": {
                "path": "/var/www/html",
                "url": "http://localhost",
                "debug_log_path": "/var/www/html/wp-content/debug.log"
            },
            "safety": {
                "check_interval": 5,
                "max_retries": 3,
                "timeout": 30
            }
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_config
        else:
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config=None):
        """Guardar configuración en archivo JSON"""
        if config is None:
            config = self.config
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def should_show_warning(self, warning_type):
        """Verificar si se debe mostrar un diálogo de advertencia basado en cooldown"""
        current_time = time.time()
        last_time = self.last_warning_time.get(warning_type, 0)
        
        if current_time - last_time >= self.warning_cooldown:
            self.last_warning_time[warning_type] = current_time
            return True
        return False
    
    def setup_gui(self):
        """Configurar la interfaz gráfica"""
        self.root = tk.Tk()
        self.root.title(f"WordPress Plugin Manager v{__version__} - Release 1.0")
        self.root.geometry("1000x700")
        
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña de conexión
        self.setup_connection_tab()
        
        # Pestaña de plugins
        self.setup_plugins_tab()
        
        # Pestaña de testing automatizado
        self.setup_testing_tab()
        
        # Pestaña de logs
        self.setup_logs_tab()
        
        # Pestaña de configuración
        self.setup_config_tab()
        
        # Barra de estado
        self.status_var = tk.StringVar()
        self.status_var.set("Desconectado")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_connection_tab(self):
        """Configurar pestaña de conexión SSH"""
        self.conn_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.conn_frame, text="Conexión SSH")
        
        # Campos de conexión
        ttk.Label(self.conn_frame, text="Servidor:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.hostname_var = tk.StringVar(value=self.config["ssh"]["hostname"])
        ttk.Entry(self.conn_frame, textvariable=self.hostname_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(self.conn_frame, text="Usuario:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.username_var = tk.StringVar(value=self.config["ssh"]["username"])
        ttk.Entry(self.conn_frame, textvariable=self.username_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(self.conn_frame, text="Contraseña:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.password_var = tk.StringVar(value=self.config["ssh"]["password"])
        ttk.Entry(self.conn_frame, textvariable=self.password_var, show="*", width=30).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(self.conn_frame, text="Puerto:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar(value=str(self.config["ssh"]["port"]))
        ttk.Entry(self.conn_frame, textvariable=self.port_var, width=30).grid(row=3, column=1, padx=5, pady=5)
        
        # Botones
        ttk.Button(self.conn_frame, text="Conectar", command=self.connect_ssh).grid(row=4, column=0, padx=5, pady=10)
        ttk.Button(self.conn_frame, text="Desconectar", command=self.disconnect_ssh).grid(row=4, column=1, padx=5, pady=10)
        ttk.Button(self.conn_frame, text="Probar Conexión", command=self.test_connection).grid(row=4, column=2, padx=5, pady=10)
        
        # Estado de conexión
        self.conn_status_var = tk.StringVar(value="Desconectado")
        ttk.Label(self.conn_frame, textvariable=self.conn_status_var, foreground="red").grid(row=5, column=0, columnspan=3, pady=10)
    
    def setup_plugins_tab(self):
        """Configurar pestaña de gestión de plugins"""
        self.plugins_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plugins_frame, text="Gestión de Plugins")
        
        # Botones de acción - Primera fila
        button_frame1 = ttk.Frame(self.plugins_frame)
        button_frame1.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame1, text="🔍 Escanear Plugins", command=self.scan_plugins).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame1, text="✅ Activar Seleccionado", command=self.activate_selected_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame1, text="❌ Desactivar Seleccionado", command=self.deactivate_selected_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame1, text="🌐 Verificar Sitio Web", command=self.check_website_health).pack(side=tk.LEFT, padx=5)
        
        # Botones de acción - Segunda fila (WP-CLI)
        button_frame2 = ttk.Frame(self.plugins_frame)
        button_frame2.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame2, text="🔄 Actualizar Plugin", command=self.update_selected_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame2, text="🗑️ Desinstalar Plugin", command=self.uninstall_selected_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame2, text="📦 Instalar Plugin", command=self.install_new_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame2, text="🔍 Buscar en Repositorio", command=self.search_plugin_repository).pack(side=tk.LEFT, padx=5)
        
        # Información de WP-CLI
        wp_cli_frame = ttk.Frame(self.plugins_frame)
        wp_cli_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.wp_cli_status_var = tk.StringVar(value="WP-CLI: No verificado")
        ttk.Label(wp_cli_frame, textvariable=self.wp_cli_status_var, foreground="blue").pack(side=tk.LEFT, padx=5)
        ttk.Button(wp_cli_frame, text="ℹ️ Info WordPress", command=self.show_wordpress_info).pack(side=tk.RIGHT, padx=5)
        
        # Barra de progreso
        progress_frame = ttk.Frame(self.plugins_frame)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.StringVar(value="Listo")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        
        # Lista de plugins
        self.plugins_tree = ttk.Treeview(self.plugins_frame, columns=("status", "version", "description"), show="tree headings")
        self.plugins_tree.heading("#0", text="Plugin")
        self.plugins_tree.heading("status", text="Estado")
        self.plugins_tree.heading("version", text="Versión")
        self.plugins_tree.heading("description", text="Descripción")
        
        self.plugins_tree.column("#0", width=200)
        self.plugins_tree.column("status", width=100)
        self.plugins_tree.column("version", width=100)
        self.plugins_tree.column("description", width=300)
        
        # Scrollbar para la lista
        scrollbar = ttk.Scrollbar(self.plugins_frame, orient=tk.VERTICAL, command=self.plugins_tree.yview)
        self.plugins_tree.configure(yscrollcommand=scrollbar.set)
        
        self.plugins_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_testing_tab(self):
        """Configurar pestaña de testing automatizado"""
        self.testing_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.testing_frame, text="Testing Automatizado")
        
        # Frame principal con scroll
        main_canvas = tk.Canvas(self.testing_frame)
        scrollbar = ttk.Scrollbar(self.testing_frame, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # === SECCIÓN DE HEALTH CHECK ===
        health_frame = ttk.LabelFrame(scrollable_frame, text="Verificación de Salud del Sitio")
        health_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # URL del sitio
        url_frame = ttk.Frame(health_frame)
        url_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(url_frame, text="URL del sitio:").pack(side=tk.LEFT)
        self.test_url_var = tk.StringVar()
        self.test_url_entry = ttk.Entry(url_frame, textvariable=self.test_url_var, width=50)
        self.test_url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Botones de health check
        health_buttons = ttk.Frame(health_frame)
        health_buttons.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(health_buttons, text="Verificar Salud del Sitio", command=self.check_site_health).pack(side=tk.LEFT, padx=5)
        ttk.Button(health_buttons, text="Verificar Logs de Error", command=self.check_error_logs).pack(side=tk.LEFT, padx=5)
        
        # === SECCIÓN DE TESTING INDIVIDUAL ===
        individual_frame = ttk.LabelFrame(scrollable_frame, text="Testing Individual de Plugins")
        individual_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Selección de plugin para test individual
        plugin_select_frame = ttk.Frame(individual_frame)
        plugin_select_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(plugin_select_frame, text="Plugin a probar:").pack(side=tk.LEFT)
        self.test_plugin_var = tk.StringVar()
        self.test_plugin_combo = ttk.Combobox(plugin_select_frame, textvariable=self.test_plugin_var, width=40)
        self.test_plugin_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Botones de testing individual
        individual_buttons = ttk.Frame(individual_frame)
        individual_buttons.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(individual_buttons, text="Probar Plugin", command=self.test_individual_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(individual_buttons, text="Actualizar Lista", command=self.update_plugin_combo).pack(side=tk.LEFT, padx=5)
        
        # === SECCIÓN DE TESTING POR LOTES ===
        batch_frame = ttk.LabelFrame(scrollable_frame, text="Testing por Lotes")
        batch_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Opciones de testing por lotes
        batch_options = ttk.Frame(batch_frame)
        batch_options.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_rollback_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(batch_options, text="Rollback automático", variable=self.auto_rollback_var).pack(side=tk.LEFT, padx=5)
        
        self.test_inactive_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(batch_options, text="Solo plugins inactivos", variable=self.test_inactive_only_var).pack(side=tk.LEFT, padx=5)
        
        # Botones de testing por lotes
        batch_buttons = ttk.Frame(batch_frame)
        batch_buttons.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(batch_buttons, text="Probar Todos los Plugins", command=self.test_all_plugins).pack(side=tk.LEFT, padx=5)
        ttk.Button(batch_buttons, text="Probar Plugins Seleccionados", command=self.test_selected_plugins).pack(side=tk.LEFT, padx=5)
        ttk.Button(batch_buttons, text="Detener Testing", command=self.stop_testing).pack(side=tk.LEFT, padx=5)
        
        # === SECCIÓN DE BACKUP Y RESTAURACIÓN ===
        backup_frame = ttk.LabelFrame(scrollable_frame, text="Backup y Restauración")
        backup_frame.pack(fill=tk.X, padx=5, pady=5)
        
        backup_buttons = ttk.Frame(backup_frame)
        backup_buttons.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(backup_buttons, text="Crear Backup", command=self.create_plugin_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_buttons, text="Restaurar Backup", command=self.restore_plugin_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_buttons, text="Ver Backups", command=self.show_backups).pack(side=tk.LEFT, padx=5)
        
        # === ÁREA DE RESULTADOS ===
        results_frame = ttk.LabelFrame(scrollable_frame, text="Resultados de Testing")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Progreso del testing
        self.testing_progress_var = tk.StringVar(value="Listo para testing")
        ttk.Label(results_frame, textvariable=self.testing_progress_var).pack(pady=5)
        
        self.testing_progress = ttk.Progressbar(results_frame, mode='determinate')
        self.testing_progress.pack(fill=tk.X, padx=5, pady=5)
        
        # Área de texto para resultados
        self.testing_results = scrolledtext.ScrolledText(results_frame, height=15)
        self.testing_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configurar scroll
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Variables de control
        self.testing_active = False
        self.current_backup = None
    
    def setup_logs_tab(self):
        """Configurar pestaña de logs"""
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="Logs y Debug")
        
        # Botones
        button_frame = ttk.Frame(self.logs_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Leer Debug.log", command=self.read_debug_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Limpiar Debug.log", command=self.clear_debug_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Actualizar", command=self.refresh_logs).pack(side=tk.LEFT, padx=5)
        
        # Área de texto para logs
        self.logs_text = scrolledtext.ScrolledText(self.logs_frame, height=25)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def setup_config_tab(self):
        """Configurar pestaña de configuración"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuración")
        
        # WordPress Path
        ttk.Label(self.config_frame, text="Ruta de WordPress:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.wp_path_var = tk.StringVar(value=self.config["wordpress"]["path"])
        ttk.Entry(self.config_frame, textvariable=self.wp_path_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.config_frame, text="Detectar Auto", command=self.auto_configure_wordpress_path).grid(row=0, column=2, padx=5, pady=5)
        
        # WordPress URL
        ttk.Label(self.config_frame, text="URL del sitio:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.wp_url_var = tk.StringVar(value=self.config["wordpress"]["url"])
        ttk.Entry(self.config_frame, textvariable=self.wp_url_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        
        # Debug log path
        ttk.Label(self.config_frame, text="Ruta debug.log:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.debug_path_var = tk.StringVar(value=self.config["wordpress"]["debug_log_path"])
        ttk.Entry(self.config_frame, textvariable=self.debug_path_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        
        # Botón guardar
        ttk.Button(self.config_frame, text="Guardar Configuración", command=self.save_current_config).grid(row=3, column=0, columnspan=3, pady=20)
    
    def connect_ssh(self):
        """Conectar al servidor via SSH"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Actualizar configuración con valores actuales
            self.config["ssh"]["hostname"] = self.hostname_var.get()
            self.config["ssh"]["username"] = self.username_var.get()
            self.config["ssh"]["password"] = self.password_var.get()
            self.config["ssh"]["port"] = int(self.port_var.get())
            
            self.ssh_client.connect(
                hostname=self.config["ssh"]["hostname"],
                username=self.config["ssh"]["username"],
                password=self.config["ssh"]["password"],
                port=self.config["ssh"]["port"],
                timeout=30
            )
            
            self.is_connected = True
            self.conn_status_var.set("Conectado ✓")
            self.status_var.set(f"Conectado a {self.config['ssh']['hostname']}")
            
            # Inicializar WP-CLI Manager
            wp_path = self.config.get("wordpress", {}).get("path", "/var/www/html")
            self.wp_cli_manager = WPCLIManager(self.execute_ssh_command, wp_path)
            
            self.save_config()
            messagebox.showinfo("Éxito", "Conexión SSH establecida correctamente")
            
        except Exception as e:
            self.is_connected = False
            self.conn_status_var.set("Error de conexión ✗")
            self.status_var.set("Desconectado")
            messagebox.showerror("Error", f"Error al conectar: {str(e)}")
    
    def disconnect_ssh(self):
        """Desconectar del servidor SSH"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
        
        self.is_connected = False
        self.conn_status_var.set("Desconectado")
        self.status_var.set("Desconectado")
        messagebox.showinfo("Info", "Desconectado del servidor")
    
    def test_connection(self):
        """Probar la conexión SSH sin guardar"""
        try:
            test_client = paramiko.SSHClient()
            test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            test_client.connect(
                hostname=self.hostname_var.get(),
                username=self.username_var.get(),
                password=self.password_var.get(),
                port=int(self.port_var.get()),
                timeout=10
            )
            
            test_client.close()
            messagebox.showinfo("Éxito", "Conexión SSH probada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en la prueba de conexión: {str(e)}")
    
    def execute_ssh_command(self, command, timeout=30):
        """Ejecutar comando SSH y devolver resultado con timeout"""
        if not self.is_connected or not self.ssh_client:
            raise Exception("No hay conexión SSH activa")
        
        try:
            print(f"DEBUG: Ejecutando comando SSH: {command[:100]}...")
            start_time = time.time()
            
            # Ejecutar comando con timeout
            _, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            
            # Configurar timeout para la lectura
            stdout.channel.settimeout(timeout)
            stderr.channel.settimeout(timeout)
            
            try:
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
            except Exception as e:
                if "timed out" in str(e).lower():
                    raise Exception(f"Timeout de {timeout}s alcanzado para comando: {command[:50]}...")
                else:
                    raise Exception(f"Error leyendo resultado SSH: {str(e)}")
            
            execution_time = time.time() - start_time
            print(f"DEBUG: Comando completado en {execution_time:.2f}s")
            
            # Filtrar warnings de WordPress que no son errores reales
            if error:
                # Lista de patrones que indican warnings/notices de WordPress, no errores reales
                wordpress_warnings = [
                    "Notice:",
                    "Warning:",
                    "Deprecated:",
                    "register_rest_route",
                    "permission_callback",
                    "wp-includes/functions.php",
                    "Este mensaje fue añadido en la versión"
                ]
                
                # Verificar si el error contiene solo warnings de WordPress
                error_lines = error.strip().split('\n')
                real_errors = []
                
                for line in error_lines:
                    line = line.strip()
                    if line:  # Si la línea no está vacía
                        # Verificar si es un warning de WordPress
                        is_wp_warning = any(warning in line for warning in wordpress_warnings)
                        if not is_wp_warning:
                            real_errors.append(line)
                
                # Solo lanzar excepción si hay errores reales (no warnings de WordPress)
                if real_errors:
                    print(f"DEBUG: Errores reales encontrados: {real_errors[:3]}")
                    raise Exception(f"Error en comando SSH: {chr(10).join(real_errors)}")
                else:
                    print(f"DEBUG: Solo warnings de WordPress encontrados, ignorando")
            
            return output
            
        except Exception as e:
            print(f"DEBUG: Excepción en execute_ssh_command: {e}")
            raise
    
    def detect_wordpress_paths(self):
        """Detectar automáticamente las rutas raíz de WordPress en el servidor"""
        if not self.is_connected:
            return None
        
        detected_paths = []
        
        try:
            # Rutas comunes donde se instala WordPress
            common_root_paths = [
                "/wordpress",           # Instalación directa en /wordpress
                "/wp",                  # Instalación directa en /wp  
                "/var/www/html",        # Apache por defecto
                "/var/www/wordpress",   # Apache con carpeta wordpress
                "/var/www/wp",          # Apache con carpeta wp
                "/var/www",             # Apache raíz
                "/usr/share/nginx/html", # Nginx por defecto
                "/opt/lampp/htdocs",    # XAMPP Linux
                "/Applications/XAMPP/htdocs", # XAMPP macOS
                "/home/wordpress",      # Instalación en home
                "/opt/wordpress",       # Instalación en opt
                "/srv/www",             # Algunas distribuciones
                "/var/www/vhosts"       # Hosting compartido
            ]
            
            # Método 1: Verificación directa de rutas comunes (más rápido)
            for path in common_root_paths:
                try:
                    # Verificar si es una instalación válida de WordPress
                    check_cmd = f"test -f '{path}/wp-config.php' && test -d '{path}/wp-content' && test -d '{path}/wp-admin' && echo 'valid'"
                    result = self.execute_ssh_command(check_cmd)
                    if 'valid' in result and path not in detected_paths:
                        detected_paths.append(path)
                except Exception:
                    continue
            
            # Método 2: Búsqueda en subdirectorios de rutas principales (solo si no encontramos nada)
            if not detected_paths:
                search_bases = ["/var/www", "/home", "/opt"]
                
                for base in search_bases:
                    try:
                        # Buscar wp-config.php en subdirectorios (máximo 2 niveles)
                        find_cmd = f"timeout 8 find {base} -maxdepth 2 -name 'wp-config.php' -type f 2>/dev/null"
                        result = self.execute_ssh_command(find_cmd)
                        
                        for line in result.strip().split('\n'):
                            if line and 'wp-config.php' in line and line.strip():
                                wp_path = line.replace('/wp-config.php', '')
                                if wp_path and wp_path not in detected_paths:
                                    # Verificar que es una instalación completa
                                    check_cmd = f"test -d '{wp_path}/wp-content' && test -d '{wp_path}/wp-admin' && echo 'valid'"
                                    check_result = self.execute_ssh_command(check_cmd)
                                    if 'valid' in check_result:
                                        detected_paths.append(wp_path)
                    except Exception:
                        continue
            
            # Método 3: Usar locate como último recurso (solo si está disponible)
            if not detected_paths:
                try:
                    locate_cmd = "timeout 5 locate wp-config.php 2>/dev/null | head -5"
                    result = self.execute_ssh_command(locate_cmd)
                    
                    for line in result.strip().split('\n'):
                        if line and 'wp-config.php' in line and line.strip():
                            wp_path = line.replace('/wp-config.php', '')
                            if wp_path and wp_path not in detected_paths:
                                # Verificar que es una instalación completa
                                check_cmd = f"test -d '{wp_path}/wp-content' && test -d '{wp_path}/wp-admin' && echo 'valid'"
                                check_result = self.execute_ssh_command(check_cmd)
                                if 'valid' in check_result:
                                    detected_paths.append(wp_path)
                except Exception:
                    pass
            
            # Filtrar rutas inválidas y ordenar
            valid_paths = []
            for path in detected_paths:
                if path and path != '/' and len(path) > 1:
                    valid_paths.append(path)
            
            # Eliminar duplicados y ordenar por especificidad (rutas más largas primero)
            valid_paths = list(set(valid_paths))
            valid_paths.sort(key=len, reverse=True)
            
            return valid_paths
            
        except Exception as e:
            print(f"Error detectando rutas de WordPress: {e}")
            return []
    
    def auto_configure_wordpress_path(self):
        """Configurar automáticamente la ruta de WordPress"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        self.status_var.set("Detectando rutas de WordPress...")
        
        try:
            detected_paths = self.detect_wordpress_paths()
            
            if not detected_paths:
                messagebox.showwarning("No encontrado", 
                    "No se pudieron detectar automáticamente las rutas de WordPress.\n"
                    "Por favor, configure la ruta manualmente.")
                return
            
            if len(detected_paths) == 1:
                # Solo una ruta encontrada, usarla automáticamente
                wp_path = detected_paths[0]
                self.wp_path_var.set(wp_path)
                self.debug_path_var.set(f"{wp_path}/wp-content/debug.log")
                
                messagebox.showinfo("Éxito", 
                    f"Ruta de WordPress detectada automáticamente:\n{wp_path}")
                
            else:
                # Múltiples rutas encontradas, permitir al usuario elegir
                self.show_path_selection_dialog(detected_paths)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al detectar rutas: {str(e)}")
        finally:
            self.status_var.set("Conectado" if self.is_connected else "Desconectado")
    
    def show_path_selection_dialog(self, paths):
        """Mostrar diálogo para seleccionar entre múltiples rutas detectadas"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar Ruta de WordPress")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Se encontraron múltiples instalaciones de WordPress:").pack(pady=10)
        
        # Lista de rutas
        listbox = tk.Listbox(dialog, height=8)
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for path in paths:
            listbox.insert(tk.END, path)
        
        # Seleccionar la primera por defecto
        listbox.selection_set(0)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_path = paths[selection[0]]
                self.wp_path_var.set(selected_path)
                self.debug_path_var.set(f"{selected_path}/wp-content/debug.log")
                dialog.destroy()
                messagebox.showinfo("Éxito", 
                    f"Ruta de WordPress configurada:\n{selected_path}")
        
        def on_cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Seleccionar", command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=5)
    
    def scan_plugins(self):
        """Escanear plugins de WordPress usando WP-CLI (optimizado)"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        # Prevenir escaneos simultáneos
        if self.scanning_in_progress:
            print("DEBUG: Escaneo ya en progreso, ignorando solicitud adicional")
            return
        
        self.scanning_in_progress = True
        
        try:
            # Iniciar indicadores de progreso
            self.progress_var.set("Iniciando escaneo...")
            self.progress_bar.start(10)
            self.status_var.set("Escaneando plugins con WP-CLI...")
            self.root.update()  # Actualizar GUI
            
            # Limpiar lista actual
            for item in self.plugins_tree.get_children():
                self.plugins_tree.delete(item)
            
            # Verificar si WP-CLI está disponible
            if not self.wp_cli_manager:
                print("DEBUG: No hay WP-CLI manager disponible")
                self.wp_cli_status_var.set("WP-CLI: ❌ Sin conexión SSH")
                self.progress_var.set("Usando método tradicional...")
                self.root.update()
                self.scan_plugins_traditional()
                return
                
            self.progress_var.set("Verificando WP-CLI...")
            self.root.update()
            print("DEBUG: Verificando disponibilidad de WP-CLI...")
            wp_cli_available = self.wp_cli_manager.check_wp_cli_availability()
            print(f"DEBUG: WP-CLI disponible: {wp_cli_available}")
            
            if not wp_cli_available:
                # Fallback al método tradicional si WP-CLI no está disponible
                print("DEBUG: WP-CLI no disponible, usando método tradicional")
                self.wp_cli_status_var.set("WP-CLI: ❌ No disponible")
                self.progress_var.set("Usando método tradicional...")
                self.root.update()
                self.scan_plugins_traditional()
                return
            else:
                self.wp_cli_status_var.set("WP-CLI: ✅ Disponible")
            
            # Usar WP-CLI para obtener todos los plugins de forma rápida
            self.progress_var.set("Obteniendo lista de plugins...")
            self.root.update()
            print("DEBUG: Obteniendo lista de plugins...")
            plugins = self.wp_cli_manager.list_plugins('all')
            print(f"DEBUG: Se obtuvieron {len(plugins) if plugins else 0} plugins")
            
            if not plugins:
                print("DEBUG: No se encontraron plugins")
                self.progress_var.set("No se encontraron plugins")
                self.status_var.set("No se encontraron plugins")
                # Usar sistema de cooldown para evitar diálogos repetitivos
                if self.should_show_warning("no_plugins"):
                    messagebox.showwarning("Advertencia", "No se encontraron plugins o WP-CLI no está funcionando correctamente")
                return
            
            # Procesar cada plugin
            self.progress_var.set(f"Procesando {len(plugins)} plugins...")
            self.root.update()
            
            for i, plugin in enumerate(plugins, 1):
                # Actualizar progreso cada 5 plugins para no sobrecargar la GUI
                if i % 5 == 0 or i == len(plugins):
                    self.progress_var.set(f"Procesando plugin {i}/{len(plugins)}: {plugin.get('name', 'N/A')}")
                    self.root.update()
                
                plugin_name = plugin.get('name', 'N/A')
                status = plugin.get('status', 'unknown')
                version = plugin.get('version', 'N/A')
                
                # Obtener descripción adicional si está disponible
                description = plugin.get('description', 'N/A')
                if description == 'N/A' or not description:
                    # Intentar obtener más información del plugin
                    plugin_info = self.wp_cli_manager.get_plugin_info(plugin_name)
                    description = plugin_info.get('description', 'N/A')
                
                # Formatear descripción
                if len(description) > 50:
                    description = description[:50] + "..."
                
                # Determinar estado visual
                if status == 'active':
                    status_display = "✓ Activo"
                elif status == 'inactive':
                    status_display = "○ Inactivo"
                elif status == 'must-use':
                    status_display = "⚡ Must-Use"
                else:
                    status_display = f"? {status}"
                
                # Agregar a la lista
                item_id = self.plugins_tree.insert("", "end", text=plugin_name, values=(
                    status_display,
                    version,
                    description
                ))
                
                # Aplicar color según estado (si es posible)
                try:
                    self.plugins_tree.set(item_id, "status", status_display)
                except:
                    pass
            
            # Finalizar progreso
            self.progress_bar.stop()
            self.progress_var.set(f"Completado: {len(plugins)} plugins encontrados")
            self.status_var.set(f"Escaneados {len(plugins)} plugins con WP-CLI")
            messagebox.showinfo("Éxito", f"Se encontraron {len(plugins)} plugins usando WP-CLI")
            
        except Exception as e:
            # Detener progreso en caso de error
            self.progress_bar.stop()
            self.progress_var.set("Error en escaneo")
            messagebox.showerror("Error", f"Error al escanear plugins: {str(e)}")
            self.status_var.set("Error en escaneo")
            # Fallback al método tradicional en caso de error
            self.scan_plugins_traditional()
        finally:
            # Siempre resetear el flag de escaneo y detener progreso
            self.scanning_in_progress = False
            self.progress_bar.stop()
            if hasattr(self, 'progress_var'):
                self.progress_var.set("Listo")
    
    def scan_plugins_traditional(self):
        """Método tradicional de escaneo (fallback cuando WP-CLI no está disponible)"""
        # Prevenir escaneos simultáneos
        if self.scanning_in_progress:
            print("DEBUG: Escaneo tradicional ya en progreso, ignorando solicitud adicional")
            return
        
        self.scanning_in_progress = True
        
        try:
            # Iniciar indicadores de progreso
            self.progress_var.set("Iniciando escaneo tradicional...")
            self.progress_bar.start(10)
            self.status_var.set("Escaneando plugins (método tradicional)...")
            self.root.update()
            
            wp_path = self.wp_path_var.get()
            plugins_path = f"{wp_path}/wp-content/plugins"
            
            # Verificar si la ruta existe
            self.progress_var.set("Verificando ruta de plugins...")
            self.root.update()
            check_path_cmd = f"test -d {plugins_path} && echo 'exists' || echo 'not_exists'"
            path_check = self.execute_ssh_command(check_path_cmd, timeout=15).strip()
            
            if path_check == 'not_exists':
                error_msg = f"La ruta de plugins no existe: {plugins_path}\n\n"
                error_msg += "¿Desea detectar automáticamente la ruta correcta de WordPress?"
                
                if messagebox.askyesno("Ruta no encontrada", error_msg):
                    self.auto_configure_wordpress_path()
                    return
                else:
                    self.status_var.set("Ruta de plugins no válida")
                    return
            
            # Obtener lista de plugins instalados (con timeout)
            self.progress_var.set("Obteniendo lista de plugins...")
            self.root.update()
            command = f"timeout 30 find {plugins_path} -maxdepth 1 -type d -name '*' | grep -v '^{plugins_path}$'"
            plugin_dirs = self.execute_ssh_command(command, timeout=35).strip().split('\n')
            
            # Obtener plugins activos
            self.progress_var.set("Verificando plugins activos...")
            self.root.update()
            active_plugin_names = self.get_active_plugins_from_db()
            
            # Procesar cada plugin
            self.progress_var.set(f"Procesando {len(plugin_dirs)} plugins...")
            self.root.update()
            for i, plugin_dir in enumerate(plugin_dirs, 1):
                if plugin_dir.strip():
                    # Actualizar progreso cada 3 plugins para no sobrecargar la GUI
                    if i % 3 == 0 or i == len(plugin_dirs):
                        plugin_name_preview = plugin_dir.split('/')[-1]
                        self.progress_var.set(f"Procesando plugin {i}/{len(plugin_dirs)}: {plugin_name_preview}")
                        self.root.update()
                    
                    plugin_name = plugin_dir.split('/')[-1]
                    plugin_info = self.get_plugin_info(plugin_dir, plugin_name)
                    
                    status = "Activo" if plugin_name in active_plugin_names else "Inactivo"
                    
                    # Agregar a la lista
                    item_id = self.plugins_tree.insert("", "end", text=plugin_name, values=(
                        status,
                        plugin_info.get('version', 'N/A'),
                        plugin_info.get('description', 'N/A')[:50] + "..." if len(plugin_info.get('description', '')) > 50 else plugin_info.get('description', 'N/A')
                    ))
                    
                    # Colorear según estado
                    if status == "Activo":
                        self.plugins_tree.set(item_id, "status", "✓ Activo")
                    else:
                        self.plugins_tree.set(item_id, "status", "○ Inactivo")
            
            # Finalizar progreso
            self.progress_bar.stop()
            self.progress_var.set(f"Completado: {len(plugin_dirs)} plugins encontrados")
            self.status_var.set(f"Escaneados {len(plugin_dirs)} plugins (método tradicional)")
            
        except Exception as e:
            # Detener progreso en caso de error
            self.progress_bar.stop()
            self.progress_var.set("Error en escaneo")
            messagebox.showerror("Error", f"Error en escaneo tradicional: {str(e)}")
            self.status_var.set("Error en escaneo tradicional")
        finally:
            # Siempre resetear el flag de escaneo y detener progreso
            self.scanning_in_progress = False
            self.progress_bar.stop()
            if hasattr(self, 'progress_var'):
                self.progress_var.set("Listo")
    
    def get_plugin_info(self, plugin_dir, plugin_name):
        """Obtener información de un plugin desde su archivo principal"""
        try:
            # Buscar archivo principal del plugin
            main_file_cmd = f"find {plugin_dir} -name '*.php' -exec grep -l 'Plugin Name:' {{}} \\; | head -1"
            main_file = self.execute_ssh_command(main_file_cmd).strip()
            
            if main_file:
                # Leer header del plugin
                header_cmd = f"head -20 '{main_file}'"
                header_content = self.execute_ssh_command(header_cmd)
                
                info = {}
                for line in header_content.split('\n'):
                    if 'Plugin Name:' in line:
                        info['name'] = line.split('Plugin Name:')[1].strip()
                    elif 'Version:' in line:
                        info['version'] = line.split('Version:')[1].strip()
                    elif 'Description:' in line:
                        info['description'] = line.split('Description:')[1].strip()
                
                return info
            
        except:
            pass
        
        return {'name': plugin_name, 'version': 'N/A', 'description': 'N/A'}
    
    def get_active_plugins_from_db(self):
        """Obtener plugins activos desde la base de datos (fallback)"""
        try:
            wp_path = self.wp_path_var.get()
            # Intentar leer wp-config.php para obtener datos de DB
            config_cmd = f"cat {wp_path}/wp-config.php | grep -E 'DB_NAME|DB_USER|DB_PASSWORD|DB_HOST'"
            _ = self.execute_ssh_command(config_cmd)
            
            # Extraer configuración de DB (implementación básica)
            # En una implementación completa, aquí se conectaría a MySQL
            return []
            
        except:
            return []
    
    def activate_selected_plugins(self):
        """Activar plugins seleccionados de forma segura"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        selected_items = self.plugins_tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "Debe seleccionar al menos un plugin")
            return
        
        # Confirmar acción
        plugin_names = [self.plugins_tree.item(item)['text'] for item in selected_items]
        if not messagebox.askyesno("Confirmar", f"¿Activar los siguientes plugins?\n\n" + "\n".join(plugin_names)):
            return
        
        # Activar plugins uno por uno con verificación
        self.activate_plugins_safely(plugin_names)
    
    def activate_plugins_safely(self, plugin_names):
        """Activar plugins de forma segura con verificación de salud del sitio"""
        wp_path = self.wp_path_var.get()
        
        for plugin_name in plugin_names:
            try:
                self.status_var.set(f"Activando {plugin_name}...")
                
                # Verificar salud del sitio antes
                if not self.check_website_health(silent=True):
                    messagebox.showerror("Error", f"El sitio web tiene problemas antes de activar {plugin_name}")
                    break
                
                # Activar plugin
                activate_cmd = f"cd {wp_path} && wp plugin activate {plugin_name}"
                self.execute_ssh_command(activate_cmd)
                
                # Esperar un momento
                time.sleep(2)
                
                # Verificar salud del sitio después
                if not self.check_website_health(silent=True):
                    # El sitio falló, desactivar plugin
                    deactivate_cmd = f"cd {wp_path} && wp plugin deactivate {plugin_name}"
                    self.execute_ssh_command(deactivate_cmd)
                    
                    messagebox.showerror("Error Crítico", 
                        f"El plugin '{plugin_name}' causó problemas en el sitio web.\n\n"
                        f"ACCIONES REALIZADAS:\n"
                        f"✓ Plugin desactivado automáticamente\n"
                        f"✓ Sitio web restaurado\n\n"
                        f"INSTRUCCIONES:\n"
                        f"1. Revise los logs de error\n"
                        f"2. Verifique compatibilidad del plugin\n"
                        f"3. Contacte al desarrollador del plugin si es necesario\n"
                        f"4. Considere actualizar WordPress o el plugin")
                    break
                else:
                    messagebox.showinfo("Éxito", f"Plugin '{plugin_name}' activado correctamente")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error al activar {plugin_name}: {str(e)}")
                break
        
        # Actualizar lista de plugins
        self.scan_plugins()
        self.status_var.set("Activación completada")
    
    def check_website_health(self, silent=False):
        """Verificar que el sitio web esté funcionando correctamente"""
        try:
            url = self.wp_url_var.get()
            response = requests.get(url, timeout=10)
            
            # Verificar código de respuesta
            if response.status_code == 200:
                # Verificar que no hay errores fatales en el contenido
                content = response.text.lower()
                error_indicators = ['fatal error', 'parse error', 'call to undefined', 'cannot redeclare']
                
                for indicator in error_indicators:
                    if indicator in content:
                        if not silent:
                            messagebox.showerror("Error", f"Sitio web con errores: {indicator}")
                        return False
                
                if not silent:
                    messagebox.showinfo("Éxito", "Sitio web funcionando correctamente")
                return True
            else:
                if not silent:
                    messagebox.showerror("Error", f"Sitio web devuelve código {response.status_code}")
                return False
                
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Error al verificar sitio web: {str(e)}")
            return False
    
    def read_debug_log(self):
        """Leer el archivo debug.log de WordPress"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        try:
            debug_path = self.debug_path_var.get()
            
            # Verificar si el archivo debug.log existe
            check_command = f"test -f {debug_path} && echo 'exists' || echo 'not_exists'"
            file_status = self.execute_ssh_command(check_command).strip()
            
            if file_status == 'not_exists':
                # El archivo no existe, crearlo
                wp_content_dir = debug_path.rsplit('/', 1)[0]  # Obtener directorio wp-content
                
                # Verificar si el directorio wp-content existe
                dir_check = f"test -d {wp_content_dir} && echo 'dir_exists' || echo 'dir_not_exists'"
                dir_status = self.execute_ssh_command(dir_check).strip()
                
                if dir_status == 'dir_not_exists':
                    messagebox.showerror("Error", 
                        f"El directorio wp-content no existe: {wp_content_dir}\n"
                        f"Verifique que la ruta de WordPress sea correcta.")
                    return
                
                # Crear el archivo debug.log vacío
                create_command = f"touch {debug_path} && chmod 644 {debug_path}"
                self.execute_ssh_command(create_command)
                
                # Mostrar mensaje informativo
                self.logs_text.delete(1.0, tk.END)
                self.logs_text.insert(tk.END, f"=== DEBUG.LOG CREADO ===\n")
                self.logs_text.insert(tk.END, f"Archivo: {debug_path}\n")
                self.logs_text.insert(tk.END, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.logs_text.insert(tk.END, "="*50 + "\n\n")
                self.logs_text.insert(tk.END, "El archivo debug.log no existía y ha sido creado.\n")
                self.logs_text.insert(tk.END, "Para habilitar el logging de debug en WordPress, agregue estas líneas a wp-config.php:\n\n")
                self.logs_text.insert(tk.END, "define('WP_DEBUG', true);\n")
                self.logs_text.insert(tk.END, "define('WP_DEBUG_LOG', true);\n")
                self.logs_text.insert(tk.END, "define('WP_DEBUG_DISPLAY', false);\n\n")
                self.logs_text.insert(tk.END, "El archivo está listo para recibir logs de debug.")
                
                self.status_var.set("Debug.log creado correctamente")
                return
            
            # El archivo existe, leer su contenido
            # Verificar si el archivo tiene contenido
            size_command = f"wc -l {debug_path} | cut -d' ' -f1"
            line_count = self.execute_ssh_command(size_command).strip()
            
            if line_count == "0":
                # Archivo vacío
                self.logs_text.delete(1.0, tk.END)
                self.logs_text.insert(tk.END, f"=== DEBUG.LOG (archivo vacío) ===\n")
                self.logs_text.insert(tk.END, f"Archivo: {debug_path}\n")
                self.logs_text.insert(tk.END, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.logs_text.insert(tk.END, "="*50 + "\n\n")
                self.logs_text.insert(tk.END, "El archivo debug.log existe pero está vacío.\n")
                self.logs_text.insert(tk.END, "No hay errores registrados actualmente.")
                
                self.status_var.set("Debug.log vacío")
                return
            
            # Leer últimas 100 líneas del debug.log
            command = f"tail -100 {debug_path}"
            log_content = self.execute_ssh_command(command)
            
            # Mostrar en el área de texto
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(tk.END, f"=== DEBUG.LOG (últimas 100 líneas) ===\n")
            self.logs_text.insert(tk.END, f"Archivo: {debug_path}\n")
            self.logs_text.insert(tk.END, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.logs_text.insert(tk.END, f"Total de líneas: {line_count}\n")
            self.logs_text.insert(tk.END, "="*50 + "\n\n")
            self.logs_text.insert(tk.END, log_content)
            
            self.status_var.set("Debug.log leído correctamente")
            
        except Exception as e:
            error_msg = str(e)
            if "No such file or directory" in error_msg:
                messagebox.showerror("Error", 
                    f"El archivo debug.log no se pudo encontrar en: {debug_path}\n\n"
                    f"Posibles soluciones:\n"
                    f"1. Verificar que la ruta de WordPress sea correcta\n"
                    f"2. Verificar que el directorio wp-content exista\n"
                    f"3. Usar 'Detectar Auto' para encontrar la ruta correcta")
            else:
                messagebox.showerror("Error", f"Error al leer debug.log: {error_msg}")
    
    def clear_debug_log(self):
        """Limpiar el archivo debug.log"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        if messagebox.askyesno("Confirmar", "¿Está seguro de que desea limpiar el debug.log?"):
            try:
                debug_path = self.debug_path_var.get()
                
                # Verificar si el archivo existe antes de limpiarlo
                check_command = f"test -f {debug_path} && echo 'exists' || echo 'not_exists'"
                file_status = self.execute_ssh_command(check_command).strip()
                
                if file_status == 'not_exists':
                    # El archivo no existe, crearlo vacío
                    wp_content_dir = debug_path.rsplit('/', 1)[0]
                    
                    # Verificar si el directorio wp-content existe
                    dir_check = f"test -d {wp_content_dir} && echo 'dir_exists' || echo 'dir_not_exists'"
                    dir_status = self.execute_ssh_command(dir_check).strip()
                    
                    if dir_status == 'dir_not_exists':
                        messagebox.showerror("Error", 
                            f"El directorio wp-content no existe: {wp_content_dir}\n"
                            f"Verifique que la ruta de WordPress sea correcta.")
                        return
                    
                    # Crear el archivo debug.log vacío
                    create_command = f"touch {debug_path} && chmod 644 {debug_path}"
                    self.execute_ssh_command(create_command)
                    
                    messagebox.showinfo("Éxito", 
                        "El archivo debug.log no existía y ha sido creado vacío.\n"
                        "El archivo está listo para recibir logs de debug.")
                else:
                    # El archivo existe, limpiarlo
                    command = f"echo '' > {debug_path}"
                    self.execute_ssh_command(command)
                    
                    messagebox.showinfo("Éxito", "Debug.log limpiado correctamente")
                
                self.refresh_logs()
                
            except Exception as e:
                error_msg = str(e)
                if "No such file or directory" in error_msg:
                    messagebox.showerror("Error", 
                        f"Error al acceder al archivo debug.log en: {debug_path}\n\n"
                        f"Posibles soluciones:\n"
                        f"1. Verificar que la ruta de WordPress sea correcta\n"
                        f"2. Verificar que el directorio wp-content exista\n"
                        f"3. Usar 'Detectar Auto' para encontrar la ruta correcta")
                else:
                    messagebox.showerror("Error", f"Error al limpiar debug.log: {error_msg}")
    
    def refresh_logs(self):
        """Actualizar la vista de logs"""
        self.read_debug_log()
    
    def save_current_config(self):
        """Guardar configuración actual"""
        self.config["wordpress"]["path"] = self.wp_path_var.get()
        self.config["wordpress"]["url"] = self.wp_url_var.get()
        self.config["wordpress"]["debug_log_path"] = self.debug_path_var.get()
        
        self.save_config()
        messagebox.showinfo("Éxito", "Configuración guardada correctamente")
    
    # ===== FUNCIONES WP-CLI =====
    
    def activate_selected_plugin(self):
        """Activar plugin seleccionado usando WP-CLI"""
        selected = self.plugins_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un plugin para activar")
            return
        
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        plugin_name = self.plugins_tree.item(selected[0])['text']
        
        try:
            self.status_var.set(f"Activando plugin {plugin_name}...")
            success, message = self.wp_cli_manager.activate_plugin(plugin_name)
            
            if success:
                messagebox.showinfo("Éxito", message)
                self.scan_plugins()  # Refrescar lista
            else:
                messagebox.showerror("Error", message)
                
            self.status_var.set("Listo")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al activar plugin: {str(e)}")
            self.status_var.set("Error")
    
    def deactivate_selected_plugin(self):
        """Desactivar plugin seleccionado usando WP-CLI"""
        selected = self.plugins_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un plugin para desactivar")
            return
        
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        plugin_name = self.plugins_tree.item(selected[0])['text']
        
        # Confirmar desactivación
        if not messagebox.askyesno("Confirmar", f"¿Está seguro de desactivar el plugin '{plugin_name}'?"):
            return
        
        try:
            self.status_var.set(f"Desactivando plugin {plugin_name}...")
            success, message = self.wp_cli_manager.deactivate_plugin(plugin_name)
            
            if success:
                messagebox.showinfo("Éxito", message)
                self.scan_plugins()  # Refrescar lista
            else:
                messagebox.showerror("Error", message)
                
            self.status_var.set("Listo")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al desactivar plugin: {str(e)}")
            self.status_var.set("Error")
    
    def update_selected_plugin(self):
        """Actualizar plugin seleccionado usando WP-CLI"""
        selected = self.plugins_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un plugin para actualizar")
            return
        
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        plugin_name = self.plugins_tree.item(selected[0])['text']
        
        try:
            self.status_var.set(f"Actualizando plugin {plugin_name}...")
            success, message = self.wp_cli_manager.update_plugin(plugin_name)
            
            if success:
                messagebox.showinfo("Éxito", message)
                self.scan_plugins()  # Refrescar lista
            else:
                messagebox.showinfo("Información", message)
                
            self.status_var.set("Listo")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar plugin: {str(e)}")
            self.status_var.set("Error")
    
    def uninstall_selected_plugin(self):
        """Desinstalar plugin seleccionado usando WP-CLI"""
        selected = self.plugins_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un plugin para desinstalar")
            return
        
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        plugin_name = self.plugins_tree.item(selected[0])['text']
        
        # Confirmar desinstalación
        if not messagebox.askyesno("Confirmar Desinstalación", 
                                   f"¿Está seguro de DESINSTALAR completamente el plugin '{plugin_name}'?\n\n"
                                   f"Esta acción eliminará todos los archivos del plugin y no se puede deshacer."):
            return
        
        try:
            self.status_var.set(f"Desinstalando plugin {plugin_name}...")
            success, message = self.wp_cli_manager.uninstall_plugin(plugin_name)
            
            if success:
                messagebox.showinfo("Éxito", message)
                self.scan_plugins()  # Refrescar lista
            else:
                messagebox.showerror("Error", message)
                
            self.status_var.set("Listo")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al desinstalar plugin: {str(e)}")
            self.status_var.set("Error")
    
    def install_new_plugin(self):
        """Instalar nuevo plugin desde el repositorio usando WP-CLI"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        # Crear diálogo para instalar plugin
        dialog = tk.Toplevel(self.root)
        dialog.title("Instalar Plugin")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar diálogo
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        ttk.Label(dialog, text="Slug del Plugin:").pack(pady=10)
        plugin_slug_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=plugin_slug_var, width=40).pack(pady=5)
        
        activate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Activar después de instalar", variable=activate_var).pack(pady=10)
        
        def install_plugin():
            slug = plugin_slug_var.get().strip()
            if not slug:
                messagebox.showwarning("Advertencia", "Ingrese el slug del plugin")
                return
            
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "WP-CLI no está disponible")
                return
            
            try:
                dialog.destroy()
                self.status_var.set(f"Instalando plugin {slug}...")
                success, message = self.wp_cli_manager.install_plugin(slug, activate_var.get())
                
                if success:
                    messagebox.showinfo("Éxito", message)
                    self.scan_plugins()  # Refrescar lista
                else:
                    messagebox.showerror("Error", message)
                    
                self.status_var.set("Listo")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error al instalar plugin: {str(e)}")
                self.status_var.set("Error")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Instalar", command=install_plugin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def search_plugin_repository(self):
        """Buscar plugins en el repositorio de WordPress"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        # Crear diálogo de búsqueda
        dialog = tk.Toplevel(self.root)
        dialog.title("Buscar Plugins en Repositorio")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar diálogo
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Campo de búsqueda
        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(search_frame, text="Buscar:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Lista de resultados
        results_frame = ttk.Frame(dialog)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        results_tree = ttk.Treeview(results_frame, columns=("rating", "description"), show="tree headings")
        results_tree.heading("#0", text="Plugin")
        results_tree.heading("rating", text="Rating")
        results_tree.heading("description", text="Descripción")
        
        results_tree.column("#0", width=150)
        results_tree.column("rating", width=80)
        results_tree.column("description", width=300)
        
        results_tree.pack(fill=tk.BOTH, expand=True)
        
        def search_plugins():
            search_term = search_var.get().strip()
            if not search_term:
                messagebox.showwarning("Advertencia", "Ingrese un término de búsqueda")
                return
            
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "WP-CLI no está disponible")
                return
            
            try:
                # Limpiar resultados anteriores
                for item in results_tree.get_children():
                    results_tree.delete(item)
                
                self.status_var.set(f"Buscando plugins: {search_term}...")
                plugins = self.wp_cli_manager.search_plugins(search_term, 20)
                
                for plugin in plugins:
                    name = plugin.get('name', 'N/A')
                    rating = plugin.get('rating', 'N/A')
                    description = plugin.get('description', 'N/A')
                    
                    if len(description) > 60:
                        description = description[:60] + "..."
                    
                    results_tree.insert("", "end", text=name, values=(rating, description))
                
                self.status_var.set(f"Encontrados {len(plugins)} plugins")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error en búsqueda: {str(e)}")
                self.status_var.set("Error en búsqueda")
        
        def install_selected():
            selected = results_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Seleccione un plugin para instalar")
                return
            
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "WP-CLI no está disponible")
                return
            
            plugin_name = results_tree.item(selected[0])['text']
            
            if messagebox.askyesno("Confirmar", f"¿Instalar el plugin '{plugin_name}'?"):
                try:
                    dialog.destroy()
                    self.status_var.set(f"Instalando plugin {plugin_name}...")
                    success, message = self.wp_cli_manager.install_plugin(plugin_name, True)
                    
                    if success:
                        messagebox.showinfo("Éxito", message)
                        self.scan_plugins()  # Refrescar lista
                    else:
                        messagebox.showerror("Error", message)
                        
                    self.status_var.set("Listo")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Error al instalar plugin: {str(e)}")
                    self.status_var.set("Error")
        
        # Botones
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Buscar", command=search_plugins).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Instalar Seleccionado", command=install_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cerrar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Permitir búsqueda con Enter
        search_entry.bind('<Return>', lambda e: search_plugins())
        search_entry.focus()
    
    def show_wordpress_info(self):
        """Mostrar información de WordPress usando WP-CLI"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible")
            return
        
        try:
            self.status_var.set("Obteniendo información de WordPress...")
            wp_info = self.wp_cli_manager.get_wordpress_info()
            
            if wp_info:
                info_text = "=== INFORMACIÓN DE WORDPRESS ===\n\n"
                info_text += f"Versión de WordPress: {wp_info.get('wp_version', 'N/A')}\n"
                info_text += f"URL del sitio: {wp_info.get('site_url', 'N/A')}\n"
                info_text += f"Título del sitio: {wp_info.get('site_title', 'N/A')}\n"
                info_text += f"Debug habilitado: {wp_info.get('debug_enabled', 'N/A')}\n"
                
                # Verificar actualizaciones disponibles
                updates = self.wp_cli_manager.check_plugin_updates()
                if updates:
                    info_text += f"\n=== ACTUALIZACIONES DISPONIBLES ===\n"
                    for plugin in updates:
                        info_text += f"• {plugin.get('name', 'N/A')} - {plugin.get('version', 'N/A')}\n"
                else:
                    info_text += f"\n✅ Todos los plugins están actualizados\n"
                
                # Mostrar en diálogo
                dialog = tk.Toplevel(self.root)
                dialog.title("Información de WordPress")
                dialog.geometry("500x400")
                dialog.transient(self.root)
                dialog.grab_set()
                
                text_widget = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                text_widget.insert(tk.END, info_text)
                text_widget.config(state=tk.DISABLED)
                
                ttk.Button(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
                
                # Actualizar estado de WP-CLI
                self.wp_cli_status_var.set("WP-CLI: ✅ Disponible")
            else:
                messagebox.showerror("Error", "No se pudo obtener información de WordPress")
                self.wp_cli_status_var.set("WP-CLI: ❌ Error")
                
            self.status_var.set("Listo")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener información: {str(e)}")
            self.wp_cli_status_var.set("WP-CLI: ❌ Error")
            self.status_var.set("Error")
    
    # ===== FUNCIONES DE TESTING AUTOMATIZADO =====
    
    def check_site_health(self):
        """Verificar la salud del sitio web"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "No hay conexión SSH activa. Conecte primero desde la pestaña 'Conexión SSH'.")
            return
            
        # Verificar si hay una URL específica o usar la del sitio
        url = self.test_url_var.get().strip()
        if not url:
            # Intentar obtener la URL del sitio desde WordPress
            try:
                wp_info = self.wp_cli_manager.get_wordpress_info()
                if wp_info and 'site_url' in wp_info:
                    url = wp_info['site_url']
                    self.test_url_var.set(url)  # Actualizar el campo
                else:
                    messagebox.showwarning("Advertencia", 
                        "No se pudo obtener la URL del sitio automáticamente.\n"
                        "Por favor, ingrese la URL manualmente en el campo 'URL del sitio'.")
                    return
            except Exception as e:
                messagebox.showwarning("Advertencia", 
                    f"Error al obtener información del sitio: {str(e)}\n"
                    "Por favor, ingrese la URL manualmente en el campo 'URL del sitio'.")
                return
        
        try:
            self.testing_progress_var.set("Verificando salud del sitio...")
            self.testing_results.delete(1.0, tk.END)
            
            # Verificar WP-CLI primero
            if not self.wp_cli_manager.check_wp_cli_availability():
                self.testing_results.insert(tk.END, "❌ WP-CLI no está disponible.\n")
                self.testing_results.insert(tk.END, "Verificando solo conectividad HTTP...\n\n")
            
            result = self.wp_cli_manager.check_site_health(url)
            
            if result[0]:
                health_data = result[1]
                
                # Mostrar resultados
                results_text = f"=== VERIFICACIÓN DE SALUD DEL SITIO ===\n"
                results_text += f"URL: {health_data['url']}\n"
                results_text += f"Código de estado: {health_data['status_code']}\n"
                results_text += f"Tiempo de respuesta: {health_data['response_time']}s\n"
                results_text += f"Sitio accesible: {'✅ Sí' if health_data['accessible'] else '❌ No'}\n"
                results_text += f"Tiene errores: {'❌ Sí' if health_data['has_errors'] else '✅ No'}\n"
                
                if health_data['error_details']:
                    results_text += f"\nDetalles de errores:\n"
                    for error in health_data['error_details']:
                        results_text += f"  - {error}\n"
                
                self.testing_results.insert(tk.END, results_text)
                
                if health_data['accessible'] and not health_data['has_errors']:
                    self.testing_progress_var.set("✅ Sitio saludable")
                else:
                    self.testing_progress_var.set("⚠️ Sitio con problemas")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.testing_results.insert(tk.END, f"❌ Error al verificar sitio: {error_msg}\n")
                self.testing_progress_var.set("❌ Error en verificación")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar salud del sitio: {str(e)}")
            self.testing_progress_var.set("❌ Error")
    
    def check_error_logs(self):
        """Verificar logs de error"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible. Conecte primero.")
            return
        
        try:
            self.testing_progress_var.set("Verificando logs de error...")
            
            log_data = self.wp_cli_manager.check_error_logs()
            
            results_text = f"=== VERIFICACIÓN DE LOGS DE ERROR ===\n"
            results_text += f"Errores recientes: {'❌ Sí' if log_data['has_recent_errors'] else '✅ No'}\n"
            results_text += f"Ruta del log: {log_data.get('log_path', 'No disponible')}\n\n"
            
            if log_data['recent_errors']:
                results_text += "Errores encontrados:\n"
                for error in log_data['recent_errors']:
                    results_text += f"  {error}\n"
            else:
                results_text += "No se encontraron errores recientes.\n"
            
            self.testing_results.delete(1.0, tk.END)
            self.testing_results.insert(tk.END, results_text)
            
            if log_data['has_recent_errors']:
                self.testing_progress_var.set("⚠️ Errores encontrados en logs")
            else:
                self.testing_progress_var.set("✅ Logs limpios")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar logs: {str(e)}")
            self.testing_progress_var.set("❌ Error")
    
    def update_plugin_combo(self):
        """Actualizar la lista de plugins en el combobox"""
        if not self.wp_cli_manager:
            return
        
        try:
            plugins = self.wp_cli_manager.list_plugins('all')
            if plugins:
                plugin_names = [plugin['name'] for plugin in plugins]
                self.test_plugin_combo['values'] = plugin_names
                
        except Exception as e:
            print(f"Error al actualizar lista de plugins: {str(e)}")
    
    def test_individual_plugin(self):
        """Probar un plugin individual"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible. Conecte primero.")
            return
        
        plugin_name = self.test_plugin_var.get().strip()
        if not plugin_name:
            messagebox.showerror("Error", "Seleccione un plugin para probar.")
            return
        
        try:
            self.testing_progress_var.set(f"Probando plugin: {plugin_name}")
            self.testing_results.delete(1.0, tk.END)
            
            url = self.test_url_var.get().strip() or None
            result = self.wp_cli_manager.test_plugin_activation(plugin_name, url)
            
            if result[0]:
                test_data = result[1]
                
                results_text = f"=== RESULTADO DEL TEST: {plugin_name} ===\n"
                results_text += f"Activación exitosa: {'✅ Sí' if test_data['activation_successful'] else '❌ No'}\n"
                results_text += f"Sitio accesible: {'✅ Sí' if test_data['site_accessible'] else '❌ No'}\n"
                results_text += f"Tiempo de respuesta: {test_data['response_time']}s\n"
                results_text += f"Código de estado: {test_data['status_code']}\n"
                results_text += f"Tiene errores: {'❌ Sí' if test_data['has_errors'] else '✅ No'}\n"
                results_text += f"Test aprobado: {'✅ Sí' if test_data['test_passed'] else '❌ No'}\n"
                
                if test_data['error_details']:
                    results_text += f"\nErrores detectados:\n"
                    for error in test_data['error_details']:
                        results_text += f"  - {error}\n"
                
                self.testing_results.insert(tk.END, results_text)
                
                if test_data['test_passed']:
                    self.testing_progress_var.set("✅ Plugin aprobado")
                else:
                    self.testing_progress_var.set("❌ Plugin con problemas")
                    
                    # Preguntar si desactivar el plugin
                    if messagebox.askyesno("Plugin Problemático", 
                                         f"El plugin '{plugin_name}' causa problemas. ¿Desactivarlo?"):
                        self.wp_cli_manager.deactivate_plugin(plugin_name)
                        self.testing_progress_var.set("🔄 Plugin desactivado")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.testing_results.insert(tk.END, f"❌ Error al probar plugin: {error_msg}\n")
                self.testing_progress_var.set("❌ Error en test")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al probar plugin: {str(e)}")
            self.testing_progress_var.set("❌ Error")
    
    def test_all_plugins(self):
        """Probar todos los plugins"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible. Conecte primero.")
            return
        
        try:
            # Obtener lista de plugins
            all_plugins = self.wp_cli_manager.list_plugins('all')
            if not all_plugins:
                messagebox.showerror("Error", "No se pudo obtener la lista de plugins.")
                return
            
            # Filtrar plugins según configuración
            if self.test_inactive_only_var.get():
                plugins_to_test = [p['name'] for p in all_plugins if p.get('status') == 'inactive']
            else:
                plugins_to_test = [p['name'] for p in all_plugins]
            
            if not plugins_to_test:
                messagebox.showinfo("Info", "No hay plugins para probar.")
                return
            
            # Confirmar testing
            if not messagebox.askyesno("Confirmar Testing", 
                                     f"¿Probar {len(plugins_to_test)} plugins?\n"
                                     f"Rollback automático: {'Sí' if self.auto_rollback_var.get() else 'No'}"):
                return
            
            self.testing_active = True
            self.testing_progress['maximum'] = len(plugins_to_test)
            self.testing_progress['value'] = 0
            self.testing_results.delete(1.0, tk.END)
            
            # Ejecutar testing por lotes
            url = self.test_url_var.get().strip() or None
            auto_rollback = self.auto_rollback_var.get()
            
            result = self.wp_cli_manager.test_plugin_batch(plugins_to_test, url, auto_rollback)
            
            if result[0]:
                batch_data = result[1]
                
                results_text = f"=== RESULTADOS DEL TESTING POR LOTES ===\n"
                results_text += f"Total probados: {batch_data['total_tested']}\n"
                results_text += f"Tests exitosos: {batch_data['successful_tests']}\n"
                results_text += f"Plugins problemáticos: {len(batch_data['problematic_plugins'])}\n\n"
                
                if batch_data['problematic_plugins']:
                    results_text += "Plugins con problemas:\n"
                    for plugin in batch_data['problematic_plugins']:
                        results_text += f"  ❌ {plugin}\n"
                    results_text += "\n"
                
                results_text += "Resultados detallados:\n"
                for test_result in batch_data['detailed_results']:
                    plugin_name = test_result['plugin_name']
                    if test_result.get('test_passed', False):
                        results_text += f"  ✅ {plugin_name} - OK\n"
                    else:
                        results_text += f"  ❌ {plugin_name} - PROBLEMA\n"
                        if 'error_details' in test_result:
                            for error in test_result['error_details']:
                                results_text += f"      - {error}\n"
                
                self.testing_results.insert(tk.END, results_text)
                self.testing_progress['value'] = len(plugins_to_test)
                self.testing_progress_var.set(f"✅ Testing completado: {batch_data['successful_tests']}/{batch_data['total_tested']} exitosos")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.testing_results.insert(tk.END, f"❌ Error en testing por lotes: {error_msg}\n")
                self.testing_progress_var.set("❌ Error en testing")
            
            self.testing_active = False
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en testing por lotes: {str(e)}")
            self.testing_progress_var.set("❌ Error")
            self.testing_active = False
    
    def test_selected_plugins(self):
        """Probar plugins seleccionados en la lista principal"""
        selected_items = self.plugins_tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Seleccione plugins en la pestaña de Plugins.")
            return
        
        try:
            # Obtener nombres de plugins seleccionados
            plugins_to_test = []
            for item in selected_items:
                plugin_name = self.plugins_tree.item(item)['values'][0]
                plugins_to_test.append(plugin_name)
            
            if not plugins_to_test:
                return
            
            # Confirmar testing
            if not messagebox.askyesno("Confirmar Testing", 
                                     f"¿Probar {len(plugins_to_test)} plugins seleccionados?\n"
                                     f"Rollback automático: {'Sí' if self.auto_rollback_var.get() else 'No'}"):
                return
            
            self.testing_active = True
            self.testing_progress['maximum'] = len(plugins_to_test)
            self.testing_progress['value'] = 0
            self.testing_results.delete(1.0, tk.END)
            
            # Ejecutar testing
            url = self.test_url_var.get().strip() or None
            auto_rollback = self.auto_rollback_var.get()
            
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "No hay conexión SSH activa. Conecte primero desde la pestaña 'Conexión SSH'.")
                self.testing_active = False
                return
            
            result = self.wp_cli_manager.test_plugin_batch(plugins_to_test, url, auto_rollback)
            
            if result[0]:
                batch_data = result[1]
                
                results_text = f"=== TESTING DE PLUGINS SELECCIONADOS ===\n"
                results_text += f"Total probados: {batch_data['total_tested']}\n"
                results_text += f"Tests exitosos: {batch_data['successful_tests']}\n"
                results_text += f"Plugins problemáticos: {len(batch_data['problematic_plugins'])}\n\n"
                
                for test_result in batch_data['detailed_results']:
                    plugin_name = test_result['plugin_name']
                    if test_result.get('test_passed', False):
                        results_text += f"  ✅ {plugin_name} - OK\n"
                    else:
                        results_text += f"  ❌ {plugin_name} - PROBLEMA\n"
                
                self.testing_results.insert(tk.END, results_text)
                self.testing_progress['value'] = len(plugins_to_test)
                self.testing_progress_var.set(f"✅ Testing completado")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.testing_results.insert(tk.END, f"❌ Error: {error_msg}\n")
                self.testing_progress_var.set("❌ Error")
            
            self.testing_active = False
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en testing: {str(e)}")
            self.testing_active = False
    
    def stop_testing(self):
        """Detener el testing en curso"""
        self.testing_active = False
        self.testing_progress_var.set("🛑 Testing detenido")
    
    def create_plugin_backup(self):
        """Crear backup del estado actual de plugins"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible. Conecte primero.")
            return
        
        try:
            result = self.wp_cli_manager.create_backup_state()
            if result[0]:
                self.current_backup = result[1]
                backup_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.current_backup['timestamp']))
                
                backup_text = f"=== BACKUP CREADO ===\n"
                backup_text += f"Fecha: {backup_time}\n"
                backup_text += f"Plugins activos: {len(self.current_backup['active_plugins'])}\n"
                backup_text += f"Plugins inactivos: {len(self.current_backup['inactive_plugins'])}\n\n"
                backup_text += "Plugins activos:\n"
                for plugin in self.current_backup['active_plugins']:
                    backup_text += f"  ✅ {plugin}\n"
                
                self.testing_results.delete(1.0, tk.END)
                self.testing_results.insert(tk.END, backup_text)
                self.testing_progress_var.set("✅ Backup creado")
                
                messagebox.showinfo("Éxito", "Backup del estado de plugins creado exitosamente.")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                messagebox.showerror("Error", f"Error al crear backup: {error_msg}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al crear backup: {str(e)}")
    
    def restore_plugin_backup(self):
        """Restaurar backup de plugins"""
        if not self.current_backup:
            messagebox.showerror("Error", "No hay backup disponible. Cree uno primero.")
            return
        
        if not messagebox.askyesno("Confirmar Restauración", 
                                 "¿Restaurar el estado de plugins desde el backup?\n"
                                 "Esto desactivará todos los plugins y reactivará solo los del backup."):
            return
        
        try:
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "No hay conexión SSH activa. Conecte primero desde la pestaña 'Conexión SSH'.")
                return
            
            result = self.wp_cli_manager.restore_backup_state(self.current_backup)
            if result[0]:
                backup_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.current_backup['timestamp']))
                
                restore_text = f"=== BACKUP RESTAURADO ===\n"
                restore_text += f"Backup del: {backup_time}\n"
                restore_text += f"Plugins reactivados: {len(self.current_backup['active_plugins'])}\n\n"
                
                self.testing_results.delete(1.0, tk.END)
                self.testing_results.insert(tk.END, restore_text)
                self.testing_progress_var.set("✅ Backup restaurado")
                
                # Actualizar lista de plugins
                self.scan_plugins()
                
                messagebox.showinfo("Éxito", "Estado de plugins restaurado exitosamente.")
            else:
                messagebox.showerror("Error", f"Error al restaurar backup: {result[1]}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al restaurar backup: {str(e)}")
    
    def show_backups(self):
        """Mostrar información del backup actual"""
        if not self.current_backup:
            messagebox.showinfo("Info", "No hay backup disponible.")
            return
        
        backup_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.current_backup['timestamp']))
        
        backup_info = f"=== INFORMACIÓN DEL BACKUP ===\n"
        backup_info += f"Fecha de creación: {backup_time}\n"
        backup_info += f"Plugins activos: {len(self.current_backup['active_plugins'])}\n"
        backup_info += f"Plugins inactivos: {len(self.current_backup['inactive_plugins'])}\n\n"
        
        backup_info += "Plugins que estaban activos:\n"
        for plugin in self.current_backup['active_plugins']:
            backup_info += f"  ✅ {plugin}\n"
        
        self.testing_results.delete(1.0, tk.END)
        self.testing_results.insert(tk.END, backup_info)
        self.testing_progress_var.set("📋 Información del backup")
    
    def run(self):
        """Ejecutar la aplicación"""
        self.root.mainloop()

if __name__ == "__main__":
    app = WordPressPluginManager()
    app.run()