#!/usr/bin/env python3
"""
WordPress Plugin Manager - Release 2.0
Aplicación para gestionar plugins de WordPress de forma automatizada y segura via SSH

Version: 2.0.0
Release Date: January 2025
Status: Stable Release

New Features in 2.0:
- Enhanced security with personal information cleanup
- Improved repository structure and documentation
- Optimized codebase with removed development files
- Better configuration management
- Streamlined installation process

Features from 1.1:
- Multi-selection of plugins with checkboxes
- Improved modern UI with better colors and layout
- Bulk operations for selected plugins
- Enhanced user experience with visual indicators
- Better organization of controls and information

Core Features:
- SSH connection management with timeouts
- Automatic plugin scanning with WP-CLI and traditional fallback
- Real-time progress indicators
- Robust error handling with multiple fallback levels
- Site health monitoring and error detection
- Plugin testing and backup functionality
"""

__version__ = "2.0.0"
__author__ = "vrodasjj"
__status__ = "Stable"

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import paramiko
import json
import os
import sys
import time
import threading
import requests
import re
from datetime import datetime
from pathlib import Path
from wp_cli_manager import WPCLIManager
from log_manager import LogManager, LogType

class PythonOutputCapture:
    """Clase para capturar la salida de Python (stdout) y redirigirla al área de logs"""
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.original_stdout = sys.stdout
        self.capturing = False
    
    def start_capture(self):
        """Iniciar captura de stdout"""
        if not self.capturing:
            sys.stdout = self
            self.capturing = True
    
    def stop_capture(self):
        """Detener captura de stdout"""
        if self.capturing:
            sys.stdout = self.original_stdout
            self.capturing = False
    
    def write(self, text):
        """Método llamado cuando se hace print()"""
        # Escribir también a stdout original para mantener funcionalidad normal
        self.original_stdout.write(text)
        self.original_stdout.flush()
        
        # Enviar al área de logs si hay texto significativo
        if text.strip():
            self.log_callback(text.strip(), "PYTHON")
    
    def flush(self):
        """Método requerido para compatibilidad con stdout"""
        self.original_stdout.flush()

class WordPressPluginManager:
    def __init__(self):
        self.ssh_client = None
        self.config = self.load_config()
        self.plugins_data = []
        self.is_connected = False
        self.wp_cli_manager = None
        self.log_manager = None
        
        # Variables para testing automatizado
        self.testing_active = False
        self.current_backup = None
        
        # Flag para prevenir escaneos simultáneos
        self.scanning_in_progress = False
        
        # Sistema de cooldown para prevenir diálogos repetitivos
        self.last_warning_time = {}
        self.warning_cooldown = 10  # segundos
        
        # Variables para selección múltiple (NEW in 1.1)
        self.selected_plugins = set()
        self.all_plugins_data = []
        
        # Sistema de captura de salida Python (NEW)
        self.python_capture = None
        self.python_capture_active = False
        
        # Variables para actualización automática del log en tiempo real
        self.auto_refresh_logs = False
        self.log_refresh_interval = 5000  # 5 segundos
        self.log_refresh_timer_id = None
        
        # Crear la interfaz gráfica
        self.setup_gui()
        
        # Inicializar captura de Python si está habilitada por defecto
        if self.config.get("python_capture", {}).get("enabled", True):
            self.toggle_python_capture()
        
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
            },
            "python_capture": {
                "enabled": True
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
        """Configurar la interfaz gráfica con diseño mejorado (ENHANCED in 1.1)"""
        self.root = tk.Tk()
        self.root.title(f"WordPress Plugin Manager v{__version__} - Release 2.0")
        self.root.geometry("1400x800")  # Aumentado el ancho para acomodar el panel de logs
        self.root.minsize(1200, 700)  # Tamaño mínimo ajustado
        self.root.configure(bg='#f8fafc')
        
        # Configurar protocolo de cierre para limpiar captura Python
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Inicializar variables de Tkinter después de crear root
        self.select_all_var = tk.BooleanVar()
        self.selected_count_var = tk.StringVar(value="0 plugins seleccionados")
        
        # Configurar estilo moderno
        self.setup_modern_style()
        
        # Header visual atractivo
        self.setup_header()
        
        # === CONTENEDOR PRINCIPAL CON PANEDWINDOW PARA REDIMENSIONAMIENTO ===
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        
        # === PANEL IZQUIERDO - PESTAÑAS (Nuevo diseño) ===
        self.left_panel = ttk.LabelFrame(main_container, text="🚀 Panel de Control", padding=2)
        
        # Configurar expansión del panel izquierdo
        self.left_panel.grid_rowconfigure(0, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        # Notebook moderno con mejor configuración y expansión completa
        self.notebook = ttk.Notebook(self.left_panel)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        # Configurar textos adaptativos para las pestañas
        self.tab_texts = {
            'full': ["🔗 Conexión SSH", "🔌 Gestión de Plugins", "🧪 Testing Automatizado", 
                    "📋 Logs y Debug", "⚙️ Configuración", "❓ Ayuda"],
            'medium': ["🔗 Conexión", "🔌 Plugins", "🧪 Testing", 
                      "📋 Logs", "⚙️ Config", "❓ Ayuda"],
            'short': ["🔗", "🔌", "🧪", "📋", "⚙️", "❓"]
        }
        
        # Configurar evento de redimensionamiento para texto adaptativo
        self.left_panel.bind('<Configure>', self.on_panel_resize)
        
        # === PANEL DERECHO - LOGS GLOBALES (Nuevo diseño) ===
        self.right_panel = ttk.Frame(main_container)
        
        # Configurar expansión del panel derecho - solo la fila de logs se expande
        self.right_panel.grid_rowconfigure(1, weight=1)  # Solo la fila de logs se expande
        self.right_panel.grid_columnconfigure(0, weight=1)
        
        # Agregar paneles al PanedWindow
        main_container.add(self.left_panel, weight=2)  # Panel izquierdo más ancho
        main_container.add(self.right_panel, weight=1)  # Panel derecho
        
        self.setup_global_log_panel(self.right_panel)
        
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
        
        # Pestaña de ayuda
        self.setup_help_tab()
        
        # Configurar texto adaptativo inicial después de crear todas las pestañas
        self.root.after(100, self.on_panel_resize)  # Llamada inicial con delay
        
        # Barra de estado mejorada
        self.setup_status_bar()
    
    def setup_modern_style(self):
        """Configurar estilo moderno y colorido para la aplicación (ENHANCED in 1.1)"""
        style = ttk.Style()
        
        # Configurar tema moderno
        style.theme_use('clam')
        
        # Paleta de colores vibrante y moderna
        colors = {
            'primary': '#6366f1',      # Indigo vibrante
            'secondary': '#06b6d4',    # Cyan brillante
            'success': '#10b981',      # Verde esmeralda
            'warning': '#f59e0b',      # Ámbar dorado
            'danger': '#ef4444',       # Rojo coral
            'info': '#3b82f6',         # Azul brillante
            'purple': '#8b5cf6',       # Púrpura vibrante
            'pink': '#ec4899',         # Rosa fucsia
            'light': '#f8fafc',        # Gris muy claro
            'dark': '#1e293b',         # Gris oscuro
            'accent': '#14b8a6',       # Teal
            'gradient_start': '#667eea',
            'gradient_end': '#764ba2'
        }
        
        # Configurar estilos de texto con colores vibrantes
        style.configure('Title.TLabel', 
                       font=('Segoe UI', 14, 'bold'), 
                       foreground=colors['primary'],
                       background=colors['light'])
        
        style.configure('Heading.TLabel', 
                       font=('Segoe UI', 11, 'bold'), 
                       foreground=colors['dark'])
        
        style.configure('Success.TLabel', 
                       foreground=colors['success'], 
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Warning.TLabel', 
                       foreground=colors['warning'], 
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Danger.TLabel', 
                       foreground=colors['danger'], 
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Info.TLabel', 
                       foreground=colors['info'], 
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Purple.TLabel', 
                       foreground=colors['purple'], 
                       font=('Segoe UI', 10, 'bold'))
        
        # Botones con colores vibrantes y efectos hover
        style.configure('Primary.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['primary'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Primary.TButton',
                 background=[('active', '#5855eb'), ('pressed', '#4f46e5')])
        
        style.configure('Success.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['success'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Success.TButton',
                 background=[('active', '#059669'), ('pressed', '#047857')])
        
        style.configure('Warning.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['warning'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Warning.TButton',
                 background=[('active', '#d97706'), ('pressed', '#b45309')])
        
        style.configure('Danger.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['danger'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Danger.TButton',
                 background=[('active', '#dc2626'), ('pressed', '#b91c1c')])
        
        style.configure('Info.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['info'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Info.TButton',
                 background=[('active', '#2563eb'), ('pressed', '#1d4ed8')])
        
        style.configure('Purple.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background=colors['purple'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Purple.TButton',
                 background=[('active', '#7c3aed'), ('pressed', '#6d28d9')])
        
        style.configure('Secondary.TButton', 
                       font=('Segoe UI', 10, 'bold'),
                       foreground='white',
                       background='#6b7280',
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Secondary.TButton',
                 background=[('active', '#4b5563'), ('pressed', '#374151')])
        
        # Notebook con pestañas coloridas y mejor distribución
        style.configure('TNotebook.Tab', 
                       padding=[12, 8], 
                       font=('Segoe UI', 9, 'bold'),
                       background='#e2e8f0',  # Gris más oscuro para pestañas no seleccionadas
                       foreground=colors['dark'],
                       expand=[1, 0, 0, 0],  # Expandir horizontalmente para distribuir mejor
                       anchor='center')  # Centrar el texto en las pestañas
        
        style.map('TNotebook.Tab',
                 background=[('selected', colors['primary']),
                           ('active', colors['secondary']),
                           ('!selected', '#e2e8f0')],  # Gris para pestañas no seleccionadas
                 foreground=[('selected', 'white'),
                           ('active', 'white'),
                           ('!selected', colors['dark'])])
        
        # Configurar el notebook para mejor distribución de pestañas
        style.configure('TNotebook', 
                       tabposition='n',
                       background='#e2e8f0',  # Mismo gris para el fondo del notebook
                       tabmargins=[0, 0, 0, 0])  # Eliminar márgenes para mejor distribución
        
        # Frames con colores de fondo
        style.configure('Colored.TFrame', background=colors['light'])
        style.configure('Primary.TFrame', background=colors['primary'])
        style.configure('Success.TFrame', background=colors['success'])
        
        # LabelFrames con colores
        style.configure('Primary.TLabelframe', 
                       background=colors['light'],
                       foreground=colors['primary'],
                       borderwidth=2)
        
        style.configure('Primary.TLabelframe.Label', 
                       background=colors['light'],
                       foreground=colors['primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # LabelFrame del panel de control con color gris uniforme
        style.configure('TLabelframe', 
                       background='#e2e8f0',  # Mismo gris que el notebook
                       foreground=colors['dark'],
                       borderwidth=1)
        
        style.configure('TLabelframe.Label', 
                       background='#e2e8f0',  # Mismo gris que el notebook
                       foreground=colors['primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # Progressbar con colores vibrantes
        style.configure('Colorful.Horizontal.TProgressbar',
                       background=colors['success'],
                       troughcolor=colors['light'],
                       borderwidth=0,
                       lightcolor=colors['success'],
                       darkcolor=colors['success'])
        
        # Entry fields con mejor estilo
        style.configure('Modern.TEntry',
                       fieldbackground='white',
                       borderwidth=2,
                       relief='solid',
                       focuscolor=colors['primary'])
        
        # Checkbuttons con colores
        style.configure('Modern.TCheckbutton',
                       font=('Segoe UI', 9),
                       focuscolor='none')
        
        # Estilos para LabelFrames modernos
        style.configure('Modern.TLabelframe', 
                       background='white',
                       foreground=colors['dark'],
                       borderwidth=1,
                       relief='solid')
        
        style.configure('Modern.TLabelframe.Label', 
                       background='white',
                       foreground=colors['primary'],
                       font=('Segoe UI', 11, 'bold'))
        
        # Estilo para Spinbox moderno
        style.configure('Modern.TSpinbox',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='solid',
                       arrowcolor=colors['primary'])
        
        # Estilo para Combobox moderno
        style.configure('Modern.TCombobox',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='solid',
                       arrowcolor=colors['primary'])
        
        # Estilo para Scrollbar moderno
        style.configure('Modern.Vertical.TScrollbar',
                       background=colors['light'],
                       troughcolor='white',
                       borderwidth=0,
                       arrowcolor=colors['primary'])
        
        # Estilo para separadores
        style.configure('Modern.TSeparator',
                       background=colors['primary'])
        
        # Estilo para el notebook con mejor apariencia
        style.configure('TNotebook', 
                       background='white',
                       borderwidth=0)
        
        # Mejorar el estilo de las pestañas
        style.configure('TNotebook.Tab', 
                       padding=[20, 12], 
                       font=('Segoe UI', 10, 'bold'),
                       background='#f1f5f9',
                       foreground=colors['dark'],
                       borderwidth=0)
        
        style.map('TNotebook.Tab',
                 background=[('selected', colors['primary']),
                           ('active', '#e2e8f0')],
                 foreground=[('selected', 'white'),
                           ('active', colors['dark'])])
        
        # Guardar colores para uso posterior
        self.colors = colors
    
    def setup_status_bar(self):
        """Configurar barra de estado mejorada (ENHANCED in 1.1)"""
        status_frame = tk.Frame(self.root, bg='#6366f1', height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)
        
        # Estado de conexión con colores modernos
        self.status_var = tk.StringVar()
        self.status_var.set("🔴 Desconectado")
        status_label = tk.Label(status_frame, textvariable=self.status_var, 
                               bg='#6366f1', fg='white', font=('Segoe UI', 10, 'bold'))
        status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Información adicional con mejor contraste
        self.info_var = tk.StringVar()
        self.info_var.set("✨ Listo para comenzar")
        info_label = tk.Label(status_frame, textvariable=self.info_var,
                             bg='#6366f1', fg='#e0e7ff', font=('Segoe UI', 9))
        info_label.pack(side=tk.RIGHT, padx=10, pady=5)

    def setup_header(self):
        """Configurar header visual atractivo"""
        header_frame = tk.Frame(self.root, bg='#f8fafc', height=55)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Crear un canvas para el gradiente
        self.header_canvas = tk.Canvas(header_frame, height=55, bg='#f8fafc', highlightthickness=0)
        self.header_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind para redimensionar el gradiente cuando cambie el tamaño
        self.header_canvas.bind('<Configure>', self.update_header_gradient)
        
        # Dibujar el gradiente inicial
        self.root.after(100, self.update_header_gradient)
    
    def update_header_gradient(self, event=None):
        """Actualizar el gradiente del header según el ancho actual"""
        # Limpiar el canvas
        self.header_canvas.delete("all")
        
        # Obtener el ancho actual del canvas
        width = self.header_canvas.winfo_width()
        if width <= 1:  # Si aún no se ha renderizado, usar un ancho por defecto
            width = 1200
        
        # Simular gradiente con rectángulos
        for i in range(0, width, 2):  # Usar pasos de 2 para mejor rendimiento
            # Gradiente de indigo a cyan
            ratio = i / width if width > 0 else 0
            r = int(99 + (6 - 99) * ratio)
            g = int(102 + (182 - 102) * ratio)
            b = int(241 + (212 - 241) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.header_canvas.create_line(i, 0, i, 80, fill=color, width=2)
        
        # Título principal
        self.header_canvas.create_text(50, 20, text="🔌 WordPress Plugin Manager", 
                          font=('Segoe UI', 14, 'bold'), fill='white', anchor='w')
        
        # Subtítulo
        self.header_canvas.create_text(50, 40, text="v2.0 - Gestión Avanzada de Plugins", 
                          font=('Segoe UI', 9), fill='#e0e7ff', anchor='w')
        
        # Icono decorativo en la esquina derecha
        self.header_canvas.create_text(width-50, 28, text="⚡", 
                          font=('Segoe UI', 20), fill='white', anchor='e')



    def setup_global_log_panel(self, parent):
        """Configurar panel global de logs en el lado derecho"""
        # Configurar expansión del contenedor padre
        parent.grid_rowconfigure(1, weight=1)  # La fila 1 es donde está el área de logs
        parent.grid_columnconfigure(0, weight=1)
        
        # === CONTROLES DEL PANEL (con título integrado) ===
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(2, 2))
        
        # Primera fila de controles
        controls_row1 = ttk.Frame(controls_frame)
        controls_row1.pack(fill=tk.X)
        
        # Título integrado
        ttk.Label(controls_row1, text="📋 Logs del Sistema", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro de nivel
        ttk.Label(controls_row1, text="Nivel:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self.global_log_level_var = tk.StringVar(value="TODOS")
        global_level_combo = ttk.Combobox(controls_row1, textvariable=self.global_log_level_var, 
                                         values=["TODOS", "INFO", "SUCCESS", "WARNING", "ERROR", "PYTHON"], 
                                         width=8, state="readonly")
        global_level_combo.pack(side=tk.LEFT, padx=2)
        global_level_combo.bind('<<ComboboxSelected>>', self.filter_global_logs)
        
        # Filtro por fuente
        ttk.Label(controls_row1, text="Fuente:", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(5,0))
        self.global_log_source_var = tk.StringVar(value="TODAS")
        global_source_combo = ttk.Combobox(controls_row1, textvariable=self.global_log_source_var, 
                                          values=["TODAS", "SSH", "PYTHON", "System", "Testing", "Plugin Manager"], 
                                          width=10, state="readonly")
        global_source_combo.pack(side=tk.LEFT, padx=2)
        global_source_combo.bind('<<ComboboxSelected>>', self.filter_global_logs)
        
        # Botón pausar
        self.global_log_pause_var = tk.StringVar(value="⏸️ Pausar")
        self.global_pause_btn = ttk.Button(controls_row1, textvariable=self.global_log_pause_var,
                                          command=self.toggle_global_log_pause)
        self.global_pause_btn.pack(side=tk.RIGHT, padx=2)
        
        # Segunda fila de controles
        controls_row2 = ttk.Frame(controls_frame)
        controls_row2.pack(fill=tk.X)
        
        # Botón limpiar
        clear_btn = ttk.Button(controls_row2, text="🧹 Limpiar",
                              command=self.clear_global_logs)
        clear_btn.pack(side=tk.LEFT, padx=2)
        
        # Botón exportar
        export_btn = ttk.Button(controls_row2, text="💾 Exportar",
                               command=self.export_global_logs)
        export_btn.pack(side=tk.LEFT, padx=2)
        
        # Control de tamaño de fuente
        font_frame = ttk.Frame(controls_row2)
        font_frame.pack(side=tk.LEFT, padx=(5, 2))
        
        ttk.Label(font_frame, text="Fuente:", font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.console_font_size = tk.IntVar(value=9)
        font_spinbox = ttk.Spinbox(font_frame, from_=8, to=16, width=3, 
                                  textvariable=self.console_font_size,
                                  command=self.update_console_font)
        font_spinbox.pack(side=tk.LEFT, padx=2)
        font_spinbox.bind('<Return>', lambda e: self.update_console_font())
        
        # Contador de logs
        self.global_log_count_var = tk.StringVar(value="0 logs")
        count_label = ttk.Label(controls_row2, textvariable=self.global_log_count_var,
                               font=('Segoe UI', 8))
        count_label.pack(side=tk.RIGHT)
        
        # === ÁREA DE LOGS ===
        log_frame = ttk.Frame(parent)
        log_frame.grid(row=1, column=0, sticky="nsew")
        
        # Configurar expansión del frame de logs
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # ScrolledText para los logs
        self.global_logs_text = scrolledtext.ScrolledText(
            log_frame, 
            height=20, 
            width=40,
            bg='#1f2937', 
            fg='#f9fafb',
            font=('Consolas', self.console_font_size.get()),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.global_logs_text.grid(row=0, column=0, sticky="nsew")
        
        # Configurar tags de colores para diferentes tipos de logs
        self.global_logs_text.tag_configure("INFO", foreground="#60a5fa")      # Azul
        self.global_logs_text.tag_configure("SUCCESS", foreground="#34d399")   # Verde
        self.global_logs_text.tag_configure("WARNING", foreground="#fbbf24")   # Amarillo
        self.global_logs_text.tag_configure("ERROR", foreground="#f87171")     # Rojo
        self.global_logs_text.tag_configure("PYTHON", foreground="#a855f7")    # Púrpura
        self.global_logs_text.tag_configure("TIMESTAMP", foreground="#9ca3af") # Gris
        
        # Inicializar variables del sistema de logs global
        self.global_log_paused = False
        self.global_all_logs = []
        
        # Mensaje inicial
        self.global_log_message("INFO", "Console global iniciada - Listo para recibir logs de todas las pestañas")

    def setup_connection_tab(self):
        """Configurar pestaña de conexión SSH"""
        self.conn_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.conn_frame, text="🔗 Conexión SSH")
        
        # Configurar expansión del frame principal
        self.conn_frame.grid_columnconfigure(0, weight=1)
        self.conn_frame.grid_rowconfigure(0, weight=1)
        
        # Contenedor principal centrado
        main_container = ttk.Frame(self.conn_frame)
        main_container.grid(row=0, column=0, padx=20, pady=15)
        
        # Título de la sección
        title_label = ttk.Label(main_container, text="🔗 Configuración de Conexión SSH", 
                               font=('Segoe UI', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15))
        
        # Frame para los campos de conexión
        fields_frame = ttk.LabelFrame(main_container, text="📋 Datos de Conexión", padding=15)
        fields_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        # Configurar expansión del fields_frame
        fields_frame.grid_columnconfigure(1, weight=1)
        
        # Campos de conexión con mejor espaciado
        ttk.Label(fields_frame, text="🖥️ Servidor:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky="w", pady=(0, 15))
        self.hostname_var = tk.StringVar(value=self.config["ssh"]["hostname"])
        hostname_entry = ttk.Entry(fields_frame, textvariable=self.hostname_var, width=35, font=('Segoe UI', 10))
        hostname_entry.grid(row=0, column=1, sticky="ew", padx=(15, 0), pady=(0, 15))
        
        ttk.Label(fields_frame, text="👤 Usuario:", font=('Segoe UI', 10)).grid(row=1, column=0, sticky="w", pady=(0, 15))
        self.username_var = tk.StringVar(value=self.config["ssh"]["username"])
        username_entry = ttk.Entry(fields_frame, textvariable=self.username_var, width=35, font=('Segoe UI', 10))
        username_entry.grid(row=1, column=1, sticky="ew", padx=(15, 0), pady=(0, 15))
        
        ttk.Label(fields_frame, text="🔐 Contraseña:", font=('Segoe UI', 10)).grid(row=2, column=0, sticky="w", pady=(0, 15))
        self.password_var = tk.StringVar(value=self.config["ssh"]["password"])
        password_entry = ttk.Entry(fields_frame, textvariable=self.password_var, show="*", width=35, font=('Segoe UI', 10))
        password_entry.grid(row=2, column=1, sticky="ew", padx=(15, 0), pady=(0, 15))
        
        ttk.Label(fields_frame, text="🔌 Puerto:", font=('Segoe UI', 10)).grid(row=3, column=0, sticky="w")
        self.port_var = tk.StringVar(value=str(self.config["ssh"]["port"]))
        port_entry = ttk.Entry(fields_frame, textvariable=self.port_var, width=35, font=('Segoe UI', 10))
        port_entry.grid(row=3, column=1, sticky="ew", padx=(15, 0))
        
        # Frame para botones
        buttons_frame = ttk.Frame(main_container)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=(0, 20))
        
        # Botones con mejor diseño
        ttk.Button(buttons_frame, text="🔗 Conectar", command=self.connect_ssh).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(buttons_frame, text="🔌 Desconectar", command=self.disconnect_ssh).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(buttons_frame, text="🧪 Probar Conexión", command=self.test_connection).grid(row=0, column=2)
        
        # Frame para estado de conexión
        status_frame = ttk.LabelFrame(main_container, text="📊 Estado de Conexión", padding=10)
        status_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        
        # Estado de conexión con mejor presentación
        self.conn_status_var = tk.StringVar(value="❌ Desconectado")
        status_label = ttk.Label(status_frame, textvariable=self.conn_status_var, 
                               font=('Segoe UI', 11, 'bold'))
        status_label.grid(row=0, column=0)
    
    def setup_plugins_tab(self):
        """Configurar pestaña de gestión de plugins con UI moderna y responsiva"""
        self.plugins_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plugins_frame, text="🔌 Gestión de Plugins")
        
        # Configurar grid weights para responsividad
        self.plugins_frame.grid_rowconfigure(0, weight=1)
        self.plugins_frame.grid_columnconfigure(0, weight=1)
        
        # === PANEDWINDOW PRINCIPAL PARA LAYOUT RESPONSIVO ===
        main_paned = ttk.PanedWindow(self.plugins_frame, orient=tk.VERTICAL)
        main_paned.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # === PANEL SUPERIOR: CONTROLES Y ACCIONES ===
        top_frame = ttk.Frame(main_paned)
        main_paned.add(top_frame, weight=1)
        
        # Header moderno
        header_frame = tk.Frame(top_frame, bg='#6366f1', height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        header_content = tk.Frame(header_frame, bg='#6366f1')
        header_content.pack(expand=True, fill=tk.BOTH)
        
        title_label = tk.Label(header_content, text="🔌 Gestión de Plugins WordPress", 
                              font=('Segoe UI', 16, 'bold'), bg='#6366f1', fg='white')
        title_label.pack(side=tk.LEFT, padx=15, pady=10)
        
        # Contador de selección en el header
        self.selected_count_var = tk.StringVar(value="0 plugins seleccionados")
        count_label = tk.Label(header_content, textvariable=self.selected_count_var,
                              font=('Segoe UI', 10, 'bold'), bg='#6366f1', fg='#e0e7ff')
        count_label.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # === CONTROLES PRINCIPALES EN GRID RESPONSIVO ===
        controls_container = ttk.Frame(top_frame)
        controls_container.pack(fill=tk.X, pady=(0, 10))
        
        # Fila 1: Controles básicos
        controls_row1 = ttk.Frame(controls_container)
        controls_row1.pack(fill=tk.X, pady=2)
        
        ttk.Button(controls_row1, text="🔍 Escanear Plugins", 
                  command=self.scan_plugins, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_row1, text="🔄 Refrescar", 
                  command=self.scan_plugins, style='Info.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_row1, text="🌐 Verificar Sitio", 
                  command=self.check_website_health, style='Purple.TButton').pack(side=tk.LEFT, padx=5)
        
        # Controles de selección en la misma fila
        ttk.Checkbutton(controls_row1, text="Seleccionar Todos", 
                       variable=self.select_all_var, 
                       command=self.toggle_select_all).pack(side=tk.RIGHT, padx=5)
        ttk.Button(controls_row1, text="🧹 Limpiar", 
                  command=self.clear_selection, style='Warning.TButton').pack(side=tk.RIGHT, padx=5)
        
        # Fila 2: Acciones para seleccionados
        actions_frame = ttk.LabelFrame(controls_container, text="Acciones para Plugins Seleccionados", padding=5)
        actions_frame.pack(fill=tk.X, pady=5)
        
        actions_row = ttk.Frame(actions_frame)
        actions_row.pack(fill=tk.X)
        
        ttk.Button(actions_row, text="✅ Activar", 
                  command=self.activate_selected_plugins, style='Success.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(actions_row, text="❌ Desactivar", 
                  command=self.deactivate_selected_plugins, style='Warning.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(actions_row, text="🧪 Probar", 
                  command=self.test_selected_plugins, style='Primary.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(actions_row, text="🔄 Actualizar", 
                  command=self.update_selected_plugins, style='Info.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(actions_row, text="🗑️ Desinstalar", 
                  command=self.uninstall_selected_plugins, style='Danger.TButton').pack(side=tk.LEFT, padx=3)
        
        # === ÁREA DE FEEDBACK VISUAL ===
        feedback_frame = ttk.LabelFrame(controls_container, text="📊 Estado y Feedback", padding=5)
        feedback_frame.pack(fill=tk.X, pady=5)
        
        # Panel de estado actual
        status_panel = ttk.Frame(feedback_frame)
        status_panel.pack(fill=tk.X, pady=2)
        
        # Fase actual
        phase_frame = ttk.Frame(status_panel)
        phase_frame.pack(fill=tk.X, pady=2)
        ttk.Label(phase_frame, text="Fase actual:", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT)
        self.plugins_current_phase_var = tk.StringVar(value="Esperando")
        phase_label = ttk.Label(phase_frame, textvariable=self.plugins_current_phase_var, 
                               font=('Segoe UI', 9), foreground='#2563eb')
        phase_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Tiempo transcurrido
        time_frame = ttk.Frame(status_panel)
        time_frame.pack(fill=tk.X, pady=2)
        ttk.Label(time_frame, text="Tiempo:", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT)
        self.plugins_elapsed_time_var = tk.StringVar(value="00:00")
        time_label = ttk.Label(time_frame, textvariable=self.plugins_elapsed_time_var, 
                              font=('Segoe UI', 9), foreground='#059669')
        time_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Panel de logs con controles
        logs_panel = ttk.Frame(feedback_frame)
        logs_panel.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Controles de logs
        log_controls = ttk.Frame(logs_panel)
        log_controls.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(log_controls, text="Nivel:", font=('Segoe UI', 8, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        self.plugins_log_level_combo = ttk.Combobox(log_controls, values=["TODOS", "INFO", "SUCCESS", "WARNING", "ERROR"], 
                                                   state="readonly", width=10)
        self.plugins_log_level_combo.set("TODOS")
        self.plugins_log_level_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.plugins_log_level_combo.bind('<<ComboboxSelected>>', self.filter_plugins_logs)
        
        # Botones de control
        ttk.Button(log_controls, text="Limpiar", command=self.clear_plugins_logs, 
                  style='Warning.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(log_controls, text="Exportar", command=self.export_plugins_logs, 
                  style='Info.TButton').pack(side=tk.LEFT, padx=2)
        
        self.plugins_pause_btn = ttk.Button(log_controls, text="Pausar", command=self.toggle_plugins_log_pause, 
                                           style='Secondary.TButton')
        self.plugins_pause_btn.pack(side=tk.LEFT, padx=2)
        
        # Área de logs
        self.plugins_log_text = scrolledtext.ScrolledText(logs_panel, height=8, wrap=tk.WORD, 
                                                         font=('Consolas', 9))
        self.plugins_log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configurar tags de colores para los logs
        self.plugins_log_text.tag_configure("INFO", foreground="#2563eb")
        self.plugins_log_text.tag_configure("SUCCESS", foreground="#059669")
        self.plugins_log_text.tag_configure("WARNING", foreground="#d97706")
        self.plugins_log_text.tag_configure("ERROR", foreground="#dc2626")
        self.plugins_log_text.tag_configure("TIMESTAMP", foreground="#6b7280")
        
        # === PANEL INFERIOR: LISTA DE PLUGINS ===
        bottom_frame = ttk.Frame(main_paned)
        main_paned.add(bottom_frame, weight=3)
        
        # Configurar grid para el panel inferior
        bottom_frame.grid_rowconfigure(1, weight=1)
        bottom_frame.grid_columnconfigure(0, weight=1)
        
        # === FILTROS Y BÚSQUEDA ===
        search_frame = ttk.LabelFrame(bottom_frame, text="🔍 Filtros y Búsqueda", padding=5)
        search_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        
        search_controls = ttk.Frame(search_frame)
        search_controls.pack(fill=tk.X)
        
        ttk.Label(search_controls, text="Buscar:", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_controls, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.search_entry.bind('<KeyRelease>', self.filter_plugins)
        self.search_entry.bind('<FocusIn>', self._on_search_focus_in)
        self.search_entry.bind('<FocusOut>', self._on_search_focus_out)
        
        # Configurar placeholder
        self.search_placeholder = "Buscar por nombre, descripción, autor, versión..."
        self.search_entry.insert(0, self.search_placeholder)
        self.search_entry.config(foreground='gray')
        
        ttk.Label(search_controls, text="Estado:", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        self.status_filter_var = tk.StringVar(value="Todos")
        status_combo = ttk.Combobox(search_controls, textvariable=self.status_filter_var, 
                                   values=["Todos", "Activos", "Inactivos", "Con Actualizaciones"], 
                                   state="readonly", width=15)
        status_combo.pack(side=tk.LEFT, padx=(0, 15))
        status_combo.bind('<<ComboboxSelected>>', self.filter_plugins)
        
        # === INFORMACIÓN DE ESTADO ===
        info_frame = ttk.LabelFrame(bottom_frame, text="Estado del Sistema", padding=10)
        info_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        
        info_row = tk.Frame(info_frame)
        info_row.pack(fill=tk.X)
        
        self.wp_cli_status_var = tk.StringVar(value="WP-CLI: No verificado")
        ttk.Label(info_row, textvariable=self.wp_cli_status_var, 
                 style='Heading.TLabel').pack(side=tk.LEFT, padx=5)
        
        # Barra de progreso mejorada
        progress_container = tk.Frame(info_frame)
        progress_container.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.StringVar(value="Listo")
        ttk.Label(progress_container, textvariable=self.progress_var, 
                 style='Heading.TLabel').pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(progress_container, mode='indeterminate', style='Colorful.Horizontal.TProgressbar')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # === LISTA DE PLUGINS CON CHECKBOXES NATIVOS ===
        plugins_container = ttk.LabelFrame(bottom_frame, text="📋 Lista de Plugins", padding=5)
        plugins_container.grid(row=1, column=0, sticky='nsew')
        
        # Configurar grid para el contenedor de plugins
        plugins_container.grid_rowconfigure(0, weight=1)
        plugins_container.grid_columnconfigure(0, weight=1)
        
        # Canvas con scrollbar para la lista de plugins
        self.plugins_canvas = tk.Canvas(plugins_container, bg='white')
        plugins_scrollbar = ttk.Scrollbar(plugins_container, orient="vertical", command=self.plugins_canvas.yview)
        self.plugins_scrollable_frame = ttk.Frame(self.plugins_canvas)
        
        self.plugins_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.plugins_canvas.configure(scrollregion=self.plugins_canvas.bbox("all"))
        )
        
        self.plugins_canvas.create_window((0, 0), window=self.plugins_scrollable_frame, anchor="nw")
        self.plugins_canvas.configure(yscrollcommand=plugins_scrollbar.set)
        
        # Grid del canvas y scrollbar con configuración responsiva
        self.plugins_canvas.grid(row=0, column=0, sticky='nsew')
        plugins_scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Configurar peso de columnas para responsividad
        plugins_container.grid_columnconfigure(0, weight=1)
        plugins_container.grid_columnconfigure(1, weight=0)
        
        # Bind para scroll con rueda del mouse - mejorado para funcionar en toda el área
        self.plugins_canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.plugins_scrollable_frame.bind('<MouseWheel>', self._on_mousewheel)
        
        # Diccionario para almacenar variables de checkbox de cada plugin
        self.plugin_vars = {}
        
        # Bind para redimensionar el canvas
        self.plugins_canvas.bind('<Configure>', self._on_canvas_configure)
    
    def setup_testing_tab(self):
        """Configurar pestaña de testing automatizado"""
        self.testing_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.testing_frame, text="🧪 Testing Automatizado")
        
        # Configurar el frame para expansión completa
        self.testing_frame.grid_rowconfigure(0, weight=1)
        self.testing_frame.grid_columnconfigure(0, weight=1)
        
        # Frame principal con scroll usando Text widget
        main_frame = ttk.Frame(self.testing_frame)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configurar expansión del frame principal
        main_frame.grid_rowconfigure(0, weight=0)  # Header
        main_frame.grid_rowconfigure(1, weight=0)  # Health check
        main_frame.grid_rowconfigure(2, weight=1)  # Testing area
        main_frame.grid_columnconfigure(0, weight=1)
        
        # === HEADER ===
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="🧪 Testing Automatizado", 
                               font=('Segoe UI', 14, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # === SECCIÓN DE HEALTH CHECK ===
        health_frame = ttk.LabelFrame(main_frame, text="🏥 Verificación de Salud del Sitio", padding=15)
        health_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar expansión del health frame
        health_frame.grid_rowconfigure(0, weight=0)
        health_frame.grid_rowconfigure(1, weight=0)
        health_frame.grid_columnconfigure(1, weight=1)
        
        # URL del sitio
        ttk.Label(health_frame, text="URL del sitio:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.test_url_var = tk.StringVar()
        self.test_url_entry = ttk.Entry(health_frame, textvariable=self.test_url_var, font=('Segoe UI', 10))
        self.test_url_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))
        
        # Botones de health check
        health_buttons = ttk.Frame(health_frame)
        health_buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        ttk.Button(health_buttons, text="🏥 Verificar Salud del Sitio", 
                  command=self.check_site_health).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(health_buttons, text="📋 Verificar Logs de Error", 
                  command=self.check_error_logs).pack(side=tk.LEFT)
        
        # === SECCIÓN DE TESTING INDIVIDUAL ===
        individual_frame = ttk.LabelFrame(main_frame, text="🎯 Testing Individual de Plugins", padding=15)
        individual_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar expansión
        individual_frame.grid_rowconfigure(0, weight=0)
        individual_frame.grid_rowconfigure(1, weight=0)
        individual_frame.grid_columnconfigure(1, weight=1)
        
        # Selección de plugin para test individual
        ttk.Label(individual_frame, text="Plugin a probar:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.test_plugin_var = tk.StringVar()
        self.test_plugin_combo = ttk.Combobox(individual_frame, textvariable=self.test_plugin_var, font=('Segoe UI', 10))
        self.test_plugin_combo.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))
        
        # Botones de testing individual
        individual_buttons = ttk.Frame(individual_frame)
        individual_buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        ttk.Button(individual_buttons, text="🧪 Probar Plugin", 
                  command=self.test_individual_plugin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(individual_buttons, text="🔄 Actualizar Lista", 
                  command=self.update_plugin_combo).pack(side=tk.LEFT)
        
        # === SECCIÓN DE TESTING POR LOTES ===
        batch_frame = ttk.LabelFrame(main_frame, text="🚀 Testing por Lotes", padding=15)
        batch_frame.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar expansión
        batch_frame.grid_rowconfigure(0, weight=0)
        batch_frame.grid_rowconfigure(1, weight=0)
        batch_frame.grid_columnconfigure(0, weight=1)
        
        # Opciones de testing por lotes
        batch_options = ttk.Frame(batch_frame)
        batch_options.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        self.auto_rollback_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(batch_options, text="✅ Rollback automático", 
                       variable=self.auto_rollback_var, 
                       style='Modern.TCheckbutton').pack(side=tk.LEFT, padx=(0, 20))
        
        self.test_inactive_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(batch_options, text="🔒 Solo plugins inactivos", 
                       variable=self.test_inactive_only_var,
                       style='Modern.TCheckbutton').pack(side=tk.LEFT)
        
        # Botones de testing por lotes
        batch_buttons = ttk.Frame(batch_frame)
        batch_buttons.grid(row=1, column=0, sticky="ew")
        
        ttk.Button(batch_buttons, text="🧪 Probar Todos los Plugins", 
                  command=self.test_all_plugins).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(batch_buttons, text="🎯 Probar Plugins Seleccionados", 
                  command=self.test_selected_plugins).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(batch_buttons, text="⏹️ Detener Testing", 
                  command=self.stop_testing).pack(side=tk.LEFT)
        
        # === SECCIÓN DE BACKUP Y RESTAURACIÓN ===
        backup_frame = ttk.LabelFrame(main_frame, text="💾 Backup y Restauración", padding=15)
        backup_frame.grid(row=4, column=0, sticky="ew", pady=(0, 15))
        
        backup_buttons = ttk.Frame(backup_frame)
        backup_buttons.pack(fill=tk.X)
        
        ttk.Button(backup_buttons, text="💾 Crear Backup", 
                  command=self.create_plugin_backup).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(backup_buttons, text="🔄 Restaurar Backup", 
                  command=self.restore_plugin_backup).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(backup_buttons, text="📋 Ver Backups", 
                  command=self.show_backups).pack(side=tk.LEFT)
        
        # === ÁREA DE RESULTADOS ===
        results_frame = ttk.LabelFrame(main_frame, text="📊 Resultados de Testing", padding=15)
        results_frame.grid(row=5, column=0, sticky="nsew")
        
        # Configurar expansión del área de resultados
        results_frame.grid_rowconfigure(1, weight=1)  # El área de logs se expande
        results_frame.grid_columnconfigure(0, weight=1)
        
        # === PANEL DE ESTADO EN TIEMPO REAL ===
        status_panel = ttk.LabelFrame(results_frame, text="⚡ Estado Actual", padding=10)
        status_panel.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar expansión del status panel
        status_panel.grid_rowconfigure(2, weight=0)
        status_panel.grid_columnconfigure(0, weight=1)
        
        # Estado principal
        self.testing_progress_var = tk.StringVar(value="✅ Listo para testing")
        status_label = ttk.Label(status_panel, textvariable=self.testing_progress_var, 
                               font=('Segoe UI', 11, 'bold'))
        status_label.grid(row=0, column=0, pady=(0, 10))
        
        # Progreso general
        self.testing_progress = ttk.Progressbar(status_panel, mode='determinate')
        self.testing_progress.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        # Panel de detalles de la fase actual
        phase_frame = ttk.Frame(status_panel)
        phase_frame.grid(row=2, column=0, sticky="ew")
        
        # Configurar grid del phase_frame
        phase_frame.grid_columnconfigure(1, weight=1)
        phase_frame.grid_columnconfigure(3, weight=1)
        phase_frame.grid_columnconfigure(5, weight=1)
        
        # Fase actual
        ttk.Label(phase_frame, text="📋 Fase:", font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.current_phase_var = tk.StringVar(value="Esperando...")
        ttk.Label(phase_frame, textvariable=self.current_phase_var, 
                 font=('Segoe UI', 9, 'bold')).grid(row=0, column=1, sticky='w', padx=(0, 20))
        
        # Plugin actual
        ttk.Label(phase_frame, text="🔌 Plugin:", font=('Segoe UI', 9)).grid(row=0, column=2, sticky='w', padx=(0, 5))
        self.current_plugin_var = tk.StringVar(value="Ninguno")
        ttk.Label(phase_frame, textvariable=self.current_plugin_var, 
                 font=('Segoe UI', 9, 'bold')).grid(row=0, column=3, sticky='w', padx=(0, 20))
        
        # Tiempo transcurrido
        ttk.Label(phase_frame, text="⏱️ Tiempo:", font=('Segoe UI', 9)).grid(row=0, column=4, sticky='w', padx=(0, 5))
        self.elapsed_time_var = tk.StringVar(value="00:00")
        ttk.Label(phase_frame, textvariable=self.elapsed_time_var, 
                 font=('Segoe UI', 9, 'bold')).grid(row=0, column=5, sticky='w')
        
        # === PANEL DE LOGS EN TIEMPO REAL ===
        logs_panel = ttk.LabelFrame(results_frame, text="📊 Logs en Tiempo Real")
        logs_panel.grid(row=1, column=0, sticky="nsew", pady=(15, 0))
        
        # Configurar expansión del logs panel
        logs_panel.grid_rowconfigure(1, weight=1)
        logs_panel.grid_columnconfigure(0, weight=1)
        
        # Controles de logs
        log_controls = ttk.Frame(logs_panel)
        log_controls.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        # Configurar grid para controles
        log_controls.grid_columnconfigure(6, weight=1)
        
        # Filtros de nivel de log
        ttk.Label(log_controls, text="🔍 Nivel:", font=('Segoe UI', 9)).grid(row=0, column=0, padx=(0, 5))
        self.log_level_var = tk.StringVar(value="ALL")
        log_level_combo = ttk.Combobox(log_controls, textvariable=self.log_level_var, 
                                     values=["ALL", "INFO", "WARNING", "ERROR", "SUCCESS"], 
                                     width=10, state="readonly")
        log_level_combo.grid(row=0, column=1, padx=(0, 15))
        log_level_combo.bind('<<ComboboxSelected>>', self.filter_logs)
        
        # Botones de control
        ttk.Button(log_controls, text="🗑️ Limpiar", command=self.clear_logs).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(log_controls, text="💾 Exportar", command=self.export_logs).grid(row=0, column=3, padx=(0, 5))
        ttk.Button(log_controls, text="⏸️ Pausar", command=self.toggle_log_pause).grid(row=0, column=4, padx=(0, 5))
        
        # Botón para actualización automática del log (también en testing)
        self.testing_auto_refresh_button = ttk.Button(log_controls, text="⏱️ Auto-Debug", command=self.toggle_auto_refresh_logs)
        self.testing_auto_refresh_button.grid(row=0, column=5, padx=(0, 15))
        
        # Auto-scroll
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_controls, text="📜 Auto-scroll", variable=self.auto_scroll_var).grid(row=0, column=7, sticky="e")
        
        # Área de logs con colores
        self.testing_results = scrolledtext.ScrolledText(logs_panel, height=12, wrap=tk.WORD, 
                                                       font=('Consolas', 9))
        self.testing_results.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Configurar tags de colores para diferentes tipos de mensajes
        self.testing_results.tag_configure("INFO", foreground="#0066CC", font=('Consolas', 9))
        self.testing_results.tag_configure("SUCCESS", foreground="#00AA00", font=('Consolas', 9, 'bold'))
        self.testing_results.tag_configure("WARNING", foreground="#FF8800", font=('Consolas', 9, 'bold'))
        self.testing_results.tag_configure("ERROR", foreground="#CC0000", font=('Consolas', 9, 'bold'))
        self.testing_results.tag_configure("PHASE", foreground="#8800CC", font=('Consolas', 9, 'bold'))
        self.testing_results.tag_configure("TIMESTAMP", foreground="#666666", font=('Consolas', 8))
        
        # Variables de control
        self.testing_active = False
        self.current_backup = None
        
        # Variables para logging y feedback (Testing tab)
        self.log_paused = False
        self.test_start_time = None
        self.all_logs = []  # Almacenar todos los logs para filtrado
        self.current_test_phase = "Esperando"
        
        # Variables para logging y feedback (Plugins tab)
        self.plugins_log_paused = False
        self.plugins_start_time = None
        self.plugins_all_logs = []  # Almacenar todos los logs para filtrado
        self.plugins_current_phase = "Esperando"
    
    def setup_logs_tab(self):
        """Configurar pestaña de logs"""
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="📋 Logs y Debug")
        
        # Configurar expansión del frame principal
        self.logs_frame.grid_rowconfigure(2, weight=1)
        self.logs_frame.grid_columnconfigure(0, weight=1)
        
        # Título de la sección
        title_frame = ttk.Frame(self.logs_frame)
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        
        title_label = ttk.Label(title_frame, text="📋 Gestión de Logs y Debug", 
                               font=('Segoe UI', 14, 'bold'))
        title_label.grid(row=0, column=0, sticky="w")
        
        # Panel de selección de tipo de log
        log_type_frame = ttk.LabelFrame(self.logs_frame, text="📂 Tipo de Log", padding=10)
        log_type_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 0))
        
        # Selector de tipo de log
        self.log_type_var = tk.StringVar(value="debug")
        log_types = [
            ("📝 Debug Log (WordPress)", "debug"),
            ("🚨 Error Log (Servidor)", "error"),
            ("🌐 Access Log (Servidor)", "access"),
            ("⚡ Cache Log", "cache"),
            ("🔌 Plugin Logs", "plugin")
        ]
        
        for i, (text, value) in enumerate(log_types):
            ttk.Radiobutton(log_type_frame, text=text, variable=self.log_type_var, 
                           value=value, command=self.on_log_type_change).grid(row=0, column=i, padx=10, sticky="w")
        
        # Frame principal de contenido
        content_frame = ttk.Frame(self.logs_frame)
        content_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=20)
        
        # Configurar expansión del content_frame
        content_frame.grid_rowconfigure(2, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Panel de controles
        controls_panel = ttk.LabelFrame(content_frame, text="🛠️ Controles de Logs", padding=15)
        controls_panel.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar grid para controles
        controls_panel.grid_columnconfigure(6, weight=1)
        
        # Fila 1: Controles principales
        ttk.Button(controls_panel, text="📖 Leer Log", command=self.read_selected_log).grid(row=0, column=0, padx=(0, 10), pady=(0, 10))
        ttk.Button(controls_panel, text="🔍 Detectar Logs", command=self.detect_available_logs).grid(row=0, column=1, padx=(0, 10), pady=(0, 10))
        ttk.Button(controls_panel, text="📊 Analizar", command=self.analyze_current_log).grid(row=0, column=2, padx=(0, 10), pady=(0, 10))
        ttk.Button(controls_panel, text="🧹 Limpiar", command=self.clear_selected_log).grid(row=0, column=3, padx=(0, 10), pady=(0, 10))
        ttk.Button(controls_panel, text="🔄 Actualizar", command=self.refresh_logs).grid(row=0, column=4, padx=(0, 10), pady=(0, 10))
        
        # Fila 2: Controles automáticos
        self.auto_refresh_button = ttk.Button(controls_panel, text="⏱️ Auto-Actualizar", command=self.toggle_auto_refresh_logs)
        self.auto_refresh_button.grid(row=1, column=0, padx=(0, 10), sticky="ew")
        
        self.python_capture_button = ttk.Button(controls_panel, text="🐍 Capturar Python", command=self.toggle_python_capture)
        self.python_capture_button.grid(row=1, column=1, padx=(0, 10), sticky="ew")
        
        # Estado de auto-actualización
        self.auto_status_var = tk.StringVar(value="❌ Auto-actualización: Desactivada")
        status_label = ttk.Label(controls_panel, textvariable=self.auto_status_var, 
                               font=('Segoe UI', 9))
        status_label.grid(row=1, column=2, columnspan=2, sticky="w", padx=(10, 0))
        
        # Panel de información de logs disponibles
        info_panel = ttk.LabelFrame(content_frame, text="ℹ️ Logs Disponibles", padding=10)
        info_panel.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        self.log_info_var = tk.StringVar(value="Conecte al servidor para detectar logs disponibles")
        info_label = ttk.Label(info_panel, textvariable=self.log_info_var, 
                              font=('Segoe UI', 9), wraplength=800)
        info_label.grid(row=0, column=0, sticky="w")
        
        # Panel de logs
        logs_panel = ttk.LabelFrame(content_frame, text="📊 Contenido de Logs", padding=10)
        logs_panel.grid(row=2, column=0, sticky="nsew")
        
        # Configurar expansión del logs_panel
        logs_panel.grid_rowconfigure(0, weight=1)
        logs_panel.grid_columnconfigure(0, weight=1)
        
        # Área de texto para logs con mejor fuente
        self.logs_text = scrolledtext.ScrolledText(logs_panel, height=25, 
                                                  font=('Consolas', 10), wrap=tk.WORD)
        self.logs_text.grid(row=0, column=0, sticky="nsew")
        
        # Configurar tags de colores para los logs
        self.logs_text.tag_configure("ERROR", foreground="#DC2626", font=('Consolas', 10, 'bold'))
        self.logs_text.tag_configure("WARNING", foreground="#F59E0B", font=('Consolas', 10, 'bold'))
        self.logs_text.tag_configure("INFO", foreground="#2563EB", font=('Consolas', 10))
        self.logs_text.tag_configure("SUCCESS", foreground="#059669", font=('Consolas', 10, 'bold'))
        self.logs_text.tag_configure("TIMESTAMP", foreground="#6B7280", font=('Consolas', 9))
        self.logs_text.tag_configure("FATAL", foreground="#991B1B", font=('Consolas', 10, 'bold'))
        self.logs_text.tag_configure("ACCESS", foreground="#7C3AED", font=('Consolas', 10))
        
        # Variables para el nuevo sistema de logs
        self.current_log_entries = []
        self.available_logs = {}
    
    def setup_config_tab(self):
        """Configurar pestaña de configuración"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="⚙️ Configuración")
        
        # Configurar expansión del frame principal
        self.config_frame.grid_rowconfigure(1, weight=1)
        self.config_frame.grid_columnconfigure(0, weight=1)
        
        # Título de la sección
        title_frame = ttk.Frame(self.config_frame)
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        
        title_label = ttk.Label(title_frame, text="⚙️ Configuración del Sistema", 
                               font=('Segoe UI', 14, 'bold'))
        title_label.grid(row=0, column=0, sticky="w")
        
        # Frame principal de contenido
        content_frame = ttk.Frame(self.config_frame)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        # Configurar expansión del content_frame
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Panel de configuración de WordPress
        wp_panel = ttk.LabelFrame(content_frame, text="🌐 Configuración de WordPress", padding=20)
        wp_panel.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar grid para wp_panel
        wp_panel.grid_columnconfigure(1, weight=1)
        
        # Ruta de WordPress
        ttk.Label(wp_panel, text="Ruta de WordPress:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        wp_path_frame = ttk.Frame(wp_panel)
        wp_path_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        wp_path_frame.grid_columnconfigure(0, weight=1)
        
        self.wp_path_var = tk.StringVar(value=self.config["wordpress"]["path"])
        wp_path_entry = ttk.Entry(wp_path_frame, textvariable=self.wp_path_var, font=('Consolas', 10))
        wp_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        ttk.Button(wp_path_frame, text="🔍 Detectar Auto", command=self.auto_configure_wordpress_path).grid(row=0, column=1)
        
        # URL del sitio
        ttk.Label(wp_panel, text="URL del sitio:", font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        self.wp_url_var = tk.StringVar(value=self.config["wordpress"]["url"])
        wp_url_entry = ttk.Entry(wp_panel, textvariable=self.wp_url_var, font=('Consolas', 10))
        wp_url_entry.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        
        # Ruta debug.log
        ttk.Label(wp_panel, text="Ruta debug.log:", font=('Segoe UI', 10, 'bold')).grid(row=4, column=0, sticky="w", pady=(0, 5))
        
        self.debug_path_var = tk.StringVar(value=self.config["wordpress"]["debug_log_path"])
        debug_path_entry = ttk.Entry(wp_panel, textvariable=self.debug_path_var, font=('Consolas', 10))
        debug_path_entry.grid(row=5, column=0, columnspan=3, sticky="ew")
        
        # Panel de configuración avanzada
        advanced_panel = ttk.LabelFrame(content_frame, text="🔧 Configuración Avanzada", padding=20)
        advanced_panel.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        # Configurar grid para advanced_panel
        advanced_panel.grid_columnconfigure(0, weight=1)
        
        # Captura de Python
        python_frame = ttk.Frame(advanced_panel)
        python_frame.grid(row=0, column=0, sticky="ew")
        
        ttk.Label(python_frame, text="🐍 Captura de Python:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.python_capture_enabled_var = tk.BooleanVar(value=self.config.get("python_capture", {}).get("enabled", True))
        python_check = ttk.Checkbutton(python_frame, text="Activar captura automática de salida Python", 
                                     variable=self.python_capture_enabled_var)
        python_check.grid(row=1, column=0, sticky="w")
        
        # Panel de acciones
        actions_panel = ttk.Frame(content_frame)
        actions_panel.grid(row=2, column=0, sticky="ew", pady=(15, 0))
        
        # Configurar grid para centrar botones
        actions_panel.grid_columnconfigure(0, weight=1)
        actions_panel.grid_columnconfigure(2, weight=1)
        
        # Botones de acción
        save_button = ttk.Button(actions_panel, text="💾 Guardar Configuración", 
                               command=self.save_current_config)
        save_button.grid(row=0, column=1, padx=10)
        
        # Estado de configuración
        self.config_status_var = tk.StringVar(value="✅ Configuración cargada correctamente")
        status_label = ttk.Label(content_frame, textvariable=self.config_status_var, 
                               font=('Segoe UI', 9), foreground="#059669")
        status_label.grid(row=3, column=0, pady=(10, 0))
    
    def setup_help_tab(self):
        """Configurar pestaña de ayuda"""
        self.help_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.help_frame, text="❓ Ayuda")
        
        # Configurar el frame principal para expansión completa
        self.help_frame.grid_rowconfigure(0, weight=1)
        self.help_frame.grid_columnconfigure(0, weight=1)
        
        # Frame principal de contenido
        main_content_frame = ttk.Frame(self.help_frame)
        main_content_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Configurar expansión del contenido principal
        main_content_frame.grid_rowconfigure(1, weight=1)
        main_content_frame.grid_columnconfigure(0, weight=1)
        
        # Título principal
        title_frame = ttk.Frame(main_content_frame)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        title_label = ttk.Label(title_frame, text="🚀 WordPress Plugin Manager - Guía de Uso", 
                               font=('Segoe UI', 16, 'bold'))
        title_label.grid(row=0, column=0, sticky="w")
        
        version_label = ttk.Label(title_frame, text="Versión 2.0 - Gestión Avanzada y Segura", 
                                 font=('Segoe UI', 10), foreground='#666')
        version_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # Botón "Acerca de"
        about_btn = ttk.Button(title_frame, text="ℹ️ Acerca de", command=self.show_about_dialog)
        about_btn.grid(row=2, column=0, sticky="w", pady=(10, 0))
        
        # Crear un canvas con scrollbar para el contenido scrolleable
        canvas_frame = ttk.Frame(main_content_frame)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        
        # Configurar expansión del canvas frame
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        help_canvas = tk.Canvas(canvas_frame, bg='#f8f9fa', highlightthickness=0)
        help_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=help_canvas.yview)
        help_scrollable_frame = ttk.Frame(help_canvas)
        
        # Función mejorada para actualizar el scrollregion
        def configure_scroll_region(event=None):
            help_canvas.configure(scrollregion=help_canvas.bbox("all"))
            # Asegurar que el frame interno se expanda al ancho del canvas
            canvas_width = help_canvas.winfo_width()
            if canvas_width > 1:
                help_canvas.itemconfig(canvas_window, width=canvas_width)
        
        help_scrollable_frame.bind("<Configure>", configure_scroll_region)
        help_canvas.bind("<Configure>", configure_scroll_region)
        
        canvas_window = help_canvas.create_window((0, 0), window=help_scrollable_frame, anchor="nw")
        help_canvas.configure(yscrollcommand=help_scrollbar.set)
        
        # Layout del canvas y scrollbar con grid
        help_canvas.grid(row=0, column=0, sticky="nsew")
        help_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Configurar el frame scrolleable para usar grid
        help_scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Actualizar el scroll region después de que se cargue todo
        self.root.after(100, configure_scroll_region)
        
        # Sección: Inicio Rápido
        self.create_help_section_grid(help_scrollable_frame, 0, "🚀 Inicio Rápido", [
            "1. Configura la conexión SSH en la pestaña 'Conexión SSH'",
            "2. Ingresa los datos de tu servidor (hostname, usuario, contraseña)",
            "3. Haz clic en 'Conectar' para establecer la conexión",
            "4. Ve a la pestaña 'Gestión de Plugins' y haz clic en 'Escanear Plugins'",
            "5. Selecciona los plugins que deseas gestionar usando los checkboxes",
            "6. Usa los botones de acción para activar, desactivar o probar plugins"
        ])
        
        # Sección: Características Principales v2.0
        self.create_help_section_grid(help_scrollable_frame, 1, "✨ Características Principales v2.0", [
            "🔲 Selección múltiple de plugins con checkboxes inteligentes",
            "⚡ Operaciones en lote optimizadas (activar/desactivar múltiples plugins)",
            "🧪 Testing automatizado con rollback de seguridad mejorado",
            "📊 Monitoreo de salud del sitio web en tiempo real",
            "📝 Análisis avanzado de logs de WordPress con filtrado",
            "🔄 Actualización masiva de plugins con verificaciones",
            "🗑️ Desinstalación segura con verificaciones de dependencias",
            "🛡️ Sistema de seguridad mejorado con validaciones",
            "💾 Backup automático antes de operaciones críticas",
            "🔧 Configuración simplificada y auto-detección de rutas"
        ])
        
        # Sección: Características de Seguridad v2.0
        self.create_help_section_grid(help_scrollable_frame, 2, "🛡️ Características de Seguridad v2.0", [
            "🔒 Validación de credenciales SSH mejorada",
            "🔍 Verificación de integridad antes de operaciones",
            "💾 Backup automático antes de cambios críticos",
            "🔄 Rollback inteligente en caso de errores",
            "⚠️ Alertas de seguridad para operaciones riesgosas",
            "🧪 Testing de seguridad antes de activar plugins",
            "📊 Monitoreo continuo de salud del sitio",
            "🚫 Prevención de operaciones en sitios comprometidos",
            "🔐 Manejo seguro de credenciales y configuraciones",
            "📝 Logging detallado de todas las operaciones"
        ])
        
        # Sección: Gestión de Plugins
        self.create_help_section_grid(help_scrollable_frame, 3, "🔌 Gestión de Plugins", [
            "• Escanear Plugins: Detecta automáticamente todos los plugins instalados",
            "• Seleccionar Todo: Marca/desmarca todos los plugins de una vez",
            "• Contador Dinámico: Muestra en tiempo real cuántos plugins están seleccionados",
            "• Activar Seleccionados: Activa todos los plugins marcados con verificaciones",
            "• Desactivar Seleccionados: Desactiva los plugins seleccionados de forma segura",
            "• Probar Seleccionados: Ejecuta tests automatizados en los plugins marcados",
            "• Actualizar Seleccionados: Actualiza múltiples plugins con backup automático",
            "• Desinstalar Seleccionados: Elimina plugins con verificación de dependencias",
            "• Auto-detección de rutas: Encuentra automáticamente la instalación de WordPress"
        ])
        
        # Sección: Testing Automatizado
        self.create_help_section_grid(help_scrollable_frame, 4, "🧪 Testing Automatizado", [
            "• Test Individual: Prueba un plugin específico con verificaciones completas",
            "• Test en Lote: Prueba múltiples plugins seleccionados de forma secuencial",
            "• Verificación de Salud: Comprueba que el sitio funcione correctamente",
            "• Rollback Automático: Revierte cambios automáticamente si se detectan errores",
            "• Reportes Detallados: Muestra resultados completos con logs de errores",
            "• Timeouts Configurables: Evita bloqueos en operaciones largas",
            "• Testing de Seguridad: Verifica que los plugins no comprometan el sitio",
            "• Monitoreo en Tiempo Real: Supervisa el estado del sitio durante las pruebas"
        ])
        
        # Sección: Backup y Rollback
        self.create_help_section_grid(help_scrollable_frame, 5, "💾 Backup y Rollback", [
            "• Backup Automático: Crea respaldos antes de operaciones críticas",
            "• Backup Manual: Permite crear respaldos cuando sea necesario",
            "• Rollback Inteligente: Restaura el estado anterior en caso de problemas",
            "• Verificación de Integridad: Comprueba que los backups sean válidos",
            "• Gestión de Backups: Lista y administra todos los respaldos creados",
            "• Restauración Selectiva: Permite restaurar plugins específicos",
            "• Limpieza Automática: Elimina backups antiguos para ahorrar espacio",
            "• Notificaciones: Informa sobre el estado de backups y restauraciones"
        ])
        
        # Sección: Configuración v2.0
        self.create_help_section_grid(help_scrollable_frame, 7, "⚙️ Configuración v2.0", [
            "🔧 Auto-detección de WordPress: Encuentra automáticamente la instalación",
            "📁 Configuración de rutas: Establece rutas personalizadas si es necesario",
            "⏱️ Timeouts configurables: Ajusta tiempos de espera según tu servidor",
            "🔒 Gestión de credenciales: Guarda de forma segura datos de conexión",
            "📊 Configuración de logs: Personaliza el nivel de detalle en logs",
            "🛡️ Configuración de seguridad: Ajusta niveles de verificación",
            "💾 Configuración de backups: Establece políticas de respaldo automático",
            "🔔 Configuración de alertas: Personaliza notificaciones y advertencias"
        ])
        
        # Sección: Consejos y Mejores Prácticas
        self.create_help_section_grid(help_scrollable_frame, 8, "💡 Consejos y Mejores Prácticas v2.0", [
            "⚠️ Siempre haz backup antes de operaciones masivas (ahora automático)",
            "🔍 Usa el testing automatizado antes de activar plugins en producción",
            "📊 Revisa los logs regularmente para detectar problemas",
            "🔄 Mantén los plugins actualizados para seguridad",
            "🎯 Usa la selección múltiple para operaciones eficientes",
            "⏱️ Configura timeouts apropiados para tu servidor",
            "🛡️ Verifica la salud del sitio después de cambios importantes",
            "💾 Aprovecha el sistema de backup automático para mayor seguridad",
            "🔒 Utiliza las nuevas validaciones de seguridad",
            "🚀 Usa la auto-detección para configuración más rápida"
        ])
        
        # Sección: Solución de Problemas
        self.create_help_section_grid(help_scrollable_frame, 9, "🔧 Solución de Problemas v2.0", [
            "❌ Error de conexión SSH: Verifica credenciales y conectividad",
            "⚠️ WP-CLI no encontrado: Instala WP-CLI o usa método tradicional",
            "🐌 Operaciones lentas: Ajusta timeouts en configuración",
            "🚫 Permisos denegados: Verifica permisos de archivos en el servidor",
            "💥 Error 500: Revisa logs de debug y desactiva plugins problemáticos",
            "🔄 Sitio no responde: Usa rollback automático para revertir cambios",
            "💾 Error en backup: Verifica espacio en disco y permisos",
            "🔒 Fallo de validación: Revisa configuración de seguridad",
            "🔍 Auto-detección falla: Configura rutas manualmente",
            "📊 Logs no se cargan: Verifica permisos del archivo debug.log",
            "🧪 Testing falla: Comprueba conectividad y estado del sitio",
            "⚡ Operaciones en lote fallan: Reduce número de plugins seleccionados"
        ])
        
        # Pie de página
        footer_frame = ttk.Frame(help_scrollable_frame)
        footer_frame.grid(row=10, column=0, sticky="ew", padx=20, pady=20)
        
        footer_label = ttk.Label(footer_frame, 
                               text="Para más información, consulta la documentación completa en GitHub",
                               font=('Segoe UI', 9), foreground='#666')
        footer_label.grid(row=0, column=0, sticky="w")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            help_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        help_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def create_help_section(self, parent, title, items):
        """Crear una sección de ayuda con título e items (versión pack - obsoleta)"""
        section_frame = ttk.LabelFrame(parent, text=title, padding=15)
        section_frame.pack(fill="x", padx=20, pady=10)
        
        for item in items:
            item_label = ttk.Label(section_frame, text=item, font=('Segoe UI', 9))
            item_label.pack(anchor="w", pady=2)
    
    def create_help_section_grid(self, parent, row, title, items):
        """Crear una sección de ayuda con título e items usando Grid layout"""
        section_frame = ttk.LabelFrame(parent, text=title, padding=15)
        section_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        
        # Configurar expansión del section_frame
        section_frame.grid_columnconfigure(0, weight=1)
        
        for i, item in enumerate(items):
            item_label = ttk.Label(section_frame, text=item, font=('Segoe UI', 9))
            item_label.grid(row=i, column=0, sticky="w", pady=2)
    
    def show_about_dialog(self):
        """Mostrar ventana 'Acerca de'"""
        about_window = tk.Toplevel(self.root)
        about_window.title("Acerca de WordPress Plugin Manager")
        about_window.geometry("500x400")
        about_window.resizable(False, False)
        about_window.configure(bg='#f8f9fa')
        
        # Centrar la ventana
        about_window.transient(self.root)
        about_window.grab_set()
        
        # Contenido principal
        main_frame = ttk.Frame(about_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Logo/Título
        title_label = ttk.Label(main_frame, text="🚀 WordPress Plugin Manager", 
                               font=('Segoe UI', 18, 'bold'))
        title_label.pack(pady=(0, 10))
        
        version_label = ttk.Label(main_frame, text="Versión 2.0.0", 
                                 font=('Segoe UI', 12), foreground='#666')
        version_label.pack()
        
        # Descripción
        desc_text = """Una aplicación profesional para gestionar plugins de WordPress
de forma segura a través de conexión SSH.

Características principales v2.0:
• Seguridad mejorada y código limpio
• Selección múltiple con checkboxes
• Operaciones en lote optimizadas
• Testing automatizado con rollback
• Interfaz moderna y intuitiva
• Monitoreo de salud del sitio
• Configuración simplificada"""
        
        desc_label = ttk.Label(main_frame, text=desc_text, 
                              font=('Segoe UI', 10), justify="center")
        desc_label.pack(pady=20)
        
        # Información del desarrollador
        dev_frame = ttk.LabelFrame(main_frame, text="Desarrollador", padding=15)
        dev_frame.pack(fill="x", pady=10)
        
        ttk.Label(dev_frame, text="👨‍💻 Desarrollado por: vrodasjj", font=('Segoe UI', 10)).pack(anchor="w")
        ttk.Label(dev_frame, text="📅 Fecha: Enero 2025", font=('Segoe UI', 10)).pack(anchor="w")
        ttk.Label(dev_frame, text="🐍 Python + Tkinter", font=('Segoe UI', 10)).pack(anchor="w")
        ttk.Label(dev_frame, text="📄 Licencia: MIT", font=('Segoe UI', 10)).pack(anchor="w")
        
        # Botón cerrar
        close_btn = ttk.Button(main_frame, text="Cerrar", command=about_window.destroy)
        close_btn.pack(pady=20)
    
    def connect_ssh(self):
        """Conectar al servidor via SSH"""
        try:
            hostname = self.hostname_var.get()
            username = self.username_var.get()
            port = int(self.port_var.get())
            
            self.global_log_message("INFO", f"Iniciando conexión SSH a {username}@{hostname}:{port}", "SSH")
            
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Actualizar configuración con valores actuales
            self.config["ssh"]["hostname"] = hostname
            self.config["ssh"]["username"] = username
            self.config["ssh"]["password"] = self.password_var.get()
            self.config["ssh"]["port"] = port
            
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
            
            # Inicializar WP-CLI Manager y Log Manager
            wp_path = self.config.get("wordpress", {}).get("path", "/var/www/html")
            self.wp_cli_manager = WPCLIManager(self.execute_ssh_command, wp_path)
            self.log_manager = LogManager(self.execute_ssh_command)
            
            self.save_config()
            self.global_log_message("SUCCESS", f"Conexión SSH establecida exitosamente a {hostname}", "SSH")
            messagebox.showinfo("Éxito", "Conexión SSH establecida correctamente")
            
        except Exception as e:
            self.is_connected = False
            self.conn_status_var.set("Error de conexión ✗")
            self.status_var.set("Desconectado")
            self.global_log_message("ERROR", f"Error al conectar SSH: {str(e)}", "SSH")
            messagebox.showerror("Error", f"Error al conectar: {str(e)}")
    
    def disconnect_ssh(self):
        """Desconectar del servidor SSH"""
        if self.ssh_client:
            hostname = self.config.get("ssh", {}).get("hostname", "servidor")
            self.global_log_message("INFO", f"Desconectando de {hostname}", "SSH")
            self.ssh_client.close()
            self.ssh_client = None
            self.global_log_message("SUCCESS", f"Desconectado exitosamente de {hostname}", "SSH")
        
        self.is_connected = False
        self.conn_status_var.set("Desconectado")
        self.status_var.set("Desconectado")
        messagebox.showinfo("Info", "Desconectado del servidor")
    
    def test_connection(self):
        """Probar la conexión SSH sin guardar"""
        try:
            hostname = self.hostname_var.get()
            username = self.username_var.get()
            port = int(self.port_var.get())
            
            self.global_log_message("INFO", f"Probando conexión SSH a {username}@{hostname}:{port}", "SSH")
            
            test_client = paramiko.SSHClient()
            test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            test_client.connect(
                hostname=hostname,
                username=username,
                password=self.password_var.get(),
                port=port,
                timeout=10
            )
            
            test_client.close()
            self.global_log_message("SUCCESS", f"Prueba de conexión SSH exitosa a {hostname}", "SSH")
            messagebox.showinfo("Éxito", "Conexión SSH probada correctamente")
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error en prueba de conexión SSH: {str(e)}", "SSH")
            messagebox.showerror("Error", f"Error en la prueba de conexión: {str(e)}")
    
    def execute_ssh_command(self, command, timeout=30):
        """Ejecutar comando SSH y devolver resultado con timeout"""
        if not self.is_connected or not self.ssh_client:
            raise Exception("No hay conexión SSH activa")
        
        try:
            print(f"DEBUG: Ejecutando comando SSH: {command[:100]}...")
            
            # Enviar comando a la consola global
            self.global_log_message("INFO", f"Ejecutando: {command[:80]}{'...' if len(command) > 80 else ''}", "SSH")
            
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
                    error_msg = f"Timeout de {timeout}s alcanzado para comando: {command[:50]}..."
                    self.global_log_message("ERROR", error_msg, "SSH")
                    raise Exception(error_msg)
                else:
                    error_msg = f"Error leyendo resultado SSH: {str(e)}"
                    self.global_log_message("ERROR", error_msg, "SSH")
                    raise Exception(error_msg)
            
            execution_time = time.time() - start_time
            print(f"DEBUG: Comando completado en {execution_time:.2f}s")
            
            # Enviar resultado a la consola global
            if output.strip():
                # Limitar la salida para evitar spam en la consola
                output_preview = output.strip()[:200] + "..." if len(output.strip()) > 200 else output.strip()
                self.global_log_message("SUCCESS", f"Salida ({execution_time:.1f}s): {output_preview}", "SSH")
            
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
                    error_msg = f"Error en comando SSH: {chr(10).join(real_errors)}"
                    self.global_log_message("ERROR", error_msg, "SSH")
                    raise Exception(error_msg)
                else:
                    print(f"DEBUG: Solo warnings de WordPress encontrados, ignorando")
                    if error.strip():
                        # Mostrar warnings como información en la consola global
                        warning_preview = error.strip()[:150] + "..." if len(error.strip()) > 150 else error.strip()
                        self.global_log_message("WARNING", f"Warnings WP: {warning_preview}", "SSH")
            
            return output
            
        except Exception as e:
            print(f"DEBUG: Excepción en execute_ssh_command: {e}")
            # Si no se ha enviado ya el error a la consola global, enviarlo ahora
            if not str(e).startswith("Timeout de") and not str(e).startswith("Error leyendo resultado SSH"):
                self.global_log_message("ERROR", f"Excepción SSH: {str(e)}", "SSH")
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
        
        # Evitar escaneos automáticos durante operaciones de plugins activas
        if hasattr(self, 'plugins_operation_active') and self.plugins_operation_active:
            print("DEBUG: Operación de plugins activa, posponiendo escaneo")
            return
        
        self.scanning_in_progress = True
        
        try:
            # Iniciar indicadores de progreso
            self.progress_var.set("Iniciando escaneo...")
            self.progress_bar.start(10)
            self.status_var.set("Escaneando plugins con WP-CLI...")
            self.root.update()  # Actualizar GUI
            
            # Limpiar lista actual y datos de plugins
            self.plugins_data = []
            self.all_plugins_data = []
            if hasattr(self, 'plugins_tree'):
                for item in self.plugins_tree.get_children():
                    self.plugins_tree.delete(item)
            
            # Inicializar lista de datos de plugins
            self.plugins_data = []
            self.all_plugins_data = []
            
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
            plugins = self.wp_cli_manager.list_plugins('all')
            
            if not plugins:
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
                
                # Obtener descripción (usar la que viene en la lista inicial)
                description = plugin.get('description', 'N/A')
                if not description or description == 'N/A':
                    description = "Sin descripción disponible"
                
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
                
                # Almacenar datos del plugin para la nueva visualización
                plugin_data = {
                    'name': plugin_name,
                    'status': status,
                    'version': version,
                    'description': description,
                    'status_display': status_display,
                    'update_available': False,  # Se actualizará después si es necesario
                    'directory': plugin.get('file', 'N/A'),
                    'test_status': 'untested'  # Estados: 'untested', 'approved', 'warning', 'failed'
                }
                self.plugins_data.append(plugin_data)
                self.all_plugins_data.append(plugin_data)
            
            # Finalizar progreso
            self.progress_bar.stop()
            self.progress_var.set(f"Completado: {len(plugins)} plugins encontrados")
            self.status_var.set(f"Escaneados {len(plugins)} plugins con WP-CLI")
            
            # Actualizar la visualización de plugins
            self.update_plugin_display()
            
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
            
            # Inicializar lista de datos de plugins
            self.plugins_data = []
            
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
                    
                    # Almacenar datos del plugin para la nueva visualización
                    plugin_data = {
                        'name': plugin_name,
                        'status': status.lower(),
                        'version': plugin_info.get('version', 'N/A'),
                        'description': plugin_info.get('description', 'N/A'),
                        'status_display': f"✓ {status}" if status == "Activo" else f"○ {status}",
                        'update_available': False,
                        'directory': plugin_dir,
                        'test_status': 'untested'  # Estados: 'untested', 'approved', 'warning', 'failed'
                    }
                    self.plugins_data.append(plugin_data)
                    self.all_plugins_data.append(plugin_data)
                    
                    # También agregar al TreeView para compatibilidad (si existe)
                    if hasattr(self, 'plugins_tree'):
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
            
            # Actualizar la nueva visualización con checkboxes
            self.update_plugin_display()
            
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
            
            # Headers para simular un navegador real y evitar bloqueos del servidor
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, timeout=10, headers=headers)
            
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
            
            # Analizar el contenido del debug.log
            analysis = self.analyze_debug_log(log_content)
            
            # Mostrar en el área de texto
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(tk.END, f"=== DEBUG.LOG (últimas 100 líneas) ===\n")
            self.logs_text.insert(tk.END, f"Archivo: {debug_path}\n")
            self.logs_text.insert(tk.END, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.logs_text.insert(tk.END, f"Total de líneas: {line_count}\n")
            self.logs_text.insert(tk.END, "="*50 + "\n\n")
            
            # Mostrar análisis de plugins problemáticos
            total_errors_shown = analysis['total_errors'] - analysis['filtered_errors']
            
            if analysis['total_errors'] > 0:
                self.logs_text.insert(tk.END, "🔍 === ANÁLISIS DE PLUGINS PROBLEMÁTICOS ===\n")
                self.logs_text.insert(tk.END, f"Total de errores encontrados: {analysis['total_errors']}\n")
                
                if analysis['filtered_errors'] > 0:
                    self.logs_text.insert(tk.END, f"Errores filtrados (plugins ya resueltos): {analysis['filtered_errors']}\n")
                    self.logs_text.insert(tk.END, f"Errores relevantes: {total_errors_shown}\n")
                
                self.logs_text.insert(tk.END, "\n")
                
                # Mostrar información sobre plugins filtrados
                if analysis['resolved_plugins_found']:
                    self.logs_text.insert(tk.END, "✅ PLUGINS YA RESUELTOS (errores filtrados):\n")
                    for plugin_name, data in analysis['resolved_plugins_found'].items():
                        self.logs_text.insert(tk.END, f"  • {plugin_name}: {data['filtered_count']} errores filtrados (estado: {data['status']})\n")
                    self.logs_text.insert(tk.END, "\n")
                
                # Mostrar plugins problemáticos
                if analysis['problematic_plugins']:
                    self.logs_text.insert(tk.END, "🚨 PLUGINS CON ERRORES ACTIVOS:\n")
                    for plugin_name, data in analysis['problematic_plugins'].items():
                        severity_icon = "🔥" if data['severity'] == 'high' else "⚠️" if data['severity'] == 'medium' else "ℹ️"
                        self.logs_text.insert(tk.END, f"{severity_icon} {plugin_name}: {data['error_count']} errores ({', '.join(data['error_types'])})\n")
                    self.logs_text.insert(tk.END, "\n")
                
                # Mostrar recomendaciones
                if analysis['recommendations']:
                    self.logs_text.insert(tk.END, "💡 RECOMENDACIONES:\n")
                    for recommendation in analysis['recommendations']:
                        self.logs_text.insert(tk.END, f"  • {recommendation}\n")
                    self.logs_text.insert(tk.END, "\n")
                
                # Mostrar tipos de errores
                if analysis['error_types']:
                    self.logs_text.insert(tk.END, "📊 TIPOS DE ERRORES:\n")
                    for error_type, count in analysis['error_types'].items():
                        self.logs_text.insert(tk.END, f"  • {error_type}: {count} ocurrencias\n")
                    self.logs_text.insert(tk.END, "\n")
                
                self.logs_text.insert(tk.END, "="*50 + "\n\n")
            else:
                self.logs_text.insert(tk.END, "✅ No se encontraron errores en el debug.log\n")
                self.logs_text.insert(tk.END, "="*50 + "\n\n")
            
            # Mostrar contenido original del log
            self.logs_text.insert(tk.END, "📄 CONTENIDO DEL LOG:\n")
            self.logs_text.insert(tk.END, log_content)
            
            # Actualizar estado con información del análisis
            if analysis['total_errors'] > 0:
                problematic_count = len(analysis['problematic_plugins'])
                self.status_var.set(f"Debug.log analizado: {analysis['total_errors']} errores, {problematic_count} plugins problemáticos")
            else:
                self.status_var.set("Debug.log leído correctamente - Sin errores")
            
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
    
    def auto_refresh_logs_function(self):
        """Función para actualizar automáticamente los logs en tiempo real"""
        if self.auto_refresh_logs and self.is_connected:
            try:
                # Evitar análisis durante operaciones críticas
                if not (getattr(self, 'plugins_operation_active', False) and 
                       getattr(self, 'avoid_log_analysis', False)):
                    self.read_debug_log()
            except Exception as e:
                print(f"Error en actualización automática del log: {e}")
            
            # Programar la próxima actualización
            if self.auto_refresh_logs:
                self.log_refresh_timer_id = self.root.after(
                    self.log_refresh_interval, 
                    self.auto_refresh_logs_function
                )
    
    def start_auto_refresh_logs(self):
        """Iniciar la actualización automática del log"""
        if not self.auto_refresh_logs:
            self.auto_refresh_logs = True
            self.auto_refresh_logs_function()
    
    def stop_auto_refresh_logs(self):
        """Detener la actualización automática del log"""
        self.auto_refresh_logs = False
        if self.log_refresh_timer_id:
            self.root.after_cancel(self.log_refresh_timer_id)
            self.log_refresh_timer_id = None
    
    def toggle_auto_refresh_logs(self):
        """Alternar la actualización automática del log"""
        if self.auto_refresh_logs:
            self.stop_auto_refresh_logs()
            # Actualizar ambos botones
            self.auto_refresh_button.config(text="⏱️ Auto-Actualizar", style='Success.TButton')
            self.testing_auto_refresh_button.config(text="⏱️ Auto-Debug", style='Success.TButton')
            messagebox.showinfo("Auto-Actualización", "Actualización automática del log desactivada")
        else:
            if not self.is_connected:
                messagebox.showwarning("Conexión", "Debe conectarse primero para activar la actualización automática")
                return
            self.start_auto_refresh_logs()
            # Actualizar ambos botones
            self.auto_refresh_button.config(text="⏹️ Detener Auto", style='Warning.TButton')
            self.testing_auto_refresh_button.config(text="⏹️ Detener Auto", style='Warning.TButton')
            messagebox.showinfo("Auto-Actualización", f"Actualización automática del log activada (cada {self.log_refresh_interval//1000} segundos)")
    
    def analyze_debug_log(self, log_content):
        """
        Analizar el contenido del debug.log para identificar plugins problemáticos
        
        Args:
            log_content (str): Contenido del debug.log
            
        Returns:
            dict: Análisis de plugins problemáticos
        """
        # Evitar análisis durante operaciones críticas de plugins para prevenir bucles
        # Pero permitir análisis durante visualización de logs
        if (getattr(self, 'plugins_operation_active', False) and 
            getattr(self, 'avoid_log_analysis', False)):
            return {
                'problematic_plugins': {},
                'error_types': {},
                'total_errors': 0,
                'recent_errors': [],
                'recommendations': [],
                'resolved_plugins_found': {},
                'filtered_errors': 0
            }
            
        analysis = {
            'problematic_plugins': {},
            'error_types': {},
            'total_errors': 0,
            'recent_errors': [],
            'recommendations': [],
            'resolved_plugins_found': {},
            'filtered_errors': 0
        }
        
        if not log_content or log_content.strip() == "":
            return analysis
        
        lines = log_content.split('\n')
        
        # Patrones comunes de errores en WordPress
        error_patterns = {
            'fatal_error': r'PHP Fatal error:',
            'parse_error': r'PHP Parse error:',
            'warning': r'PHP Warning:',
            'notice': r'PHP Notice:',
            'deprecated': r'PHP Deprecated:',
            'wp_error': r'WordPress database error',
            'plugin_error': r'Plugin.*error',
            'theme_error': r'Theme.*error'
        }
        
        # Patrones para identificar plugins en errores
        plugin_patterns = [
            r'/wp-content/plugins/([^/]+)/',
            r'in.*plugins/([^/]+)/',
            r'Plugin ([^:]+):',
            r'plugin.*?([a-zA-Z0-9_-]+)',
        ]
        
        for line in lines:
            if not line.strip():
                continue
                
            # Verificar si la línea contiene un error
            error_type = None
            for error_name, pattern in error_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    error_type = error_name
                    break
            
            if error_type:
                analysis['total_errors'] += 1
                
                # Contar tipos de errores
                if error_type not in analysis['error_types']:
                    analysis['error_types'][error_type] = 0
                analysis['error_types'][error_type] += 1
                
                # Agregar a errores recientes (últimos 10)
                if len(analysis['recent_errors']) < 10:
                    analysis['recent_errors'].append({
                        'type': error_type,
                        'message': line.strip(),
                        'timestamp': self._extract_timestamp(line)
                    })
                
                # Intentar identificar el plugin problemático
                plugin_name = self._extract_plugin_from_error(line, plugin_patterns)
                if plugin_name:
                    # Verificar si el plugin ya fue resuelto
                    if self.is_plugin_resolved(plugin_name):
                        # Verificar estado actual del plugin
                        current_status = self.get_current_plugin_status(plugin_name)
                        
                        # Si el plugin está inactivo y ya fue marcado como resuelto, filtrar el error
                        if current_status == 'inactive':
                            analysis['filtered_errors'] += 1
                            if plugin_name not in analysis['resolved_plugins_found']:
                                analysis['resolved_plugins_found'][plugin_name] = {
                                    'status': 'inactive',
                                    'filtered_count': 0
                                }
                            analysis['resolved_plugins_found'][plugin_name]['filtered_count'] += 1
                            continue  # Saltar este error
                        elif current_status == 'active':
                            # Si el plugin está activo pero marcado como resuelto, remover de resueltos
                            self.remove_resolved_plugin(plugin_name)
                    
                    if plugin_name not in analysis['problematic_plugins']:
                        analysis['problematic_plugins'][plugin_name] = {
                            'error_count': 0,
                            'error_types': [],
                            'last_error': '',
                            'severity': 'low'
                        }
                    
                    plugin_data = analysis['problematic_plugins'][plugin_name]
                    plugin_data['error_count'] += 1
                    plugin_data['last_error'] = line.strip()
                    
                    if error_type not in plugin_data['error_types']:
                        plugin_data['error_types'].append(error_type)
                    
                    # Determinar severidad
                    if error_type in ['fatal_error', 'parse_error']:
                        plugin_data['severity'] = 'high'
                    elif error_type in ['warning', 'wp_error']:
                        if plugin_data['severity'] != 'high':
                            plugin_data['severity'] = 'medium'
        
        # Generar recomendaciones
        analysis['recommendations'] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _extract_timestamp(self, line):
        """Extraer timestamp de una línea de log"""
        # Patrón típico: [DD-MMM-YYYY HH:MM:SS UTC]
        timestamp_pattern = r'\[(\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2}.*?)\]'
        match = re.search(timestamp_pattern, line)
        return match.group(1) if match else 'Unknown'
    
    def _extract_plugin_from_error(self, line, patterns):
        """Extraer nombre del plugin de una línea de error"""
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                plugin_name = match.group(1)
                # Limpiar el nombre del plugin
                plugin_name = re.sub(r'[^a-zA-Z0-9_-]', '', plugin_name)
                if len(plugin_name) > 2:  # Evitar matches muy cortos
                    return plugin_name
        return None
    
    def _generate_recommendations(self, analysis):
        """Generar recomendaciones basadas en el análisis"""
        recommendations = []
        
        if analysis['total_errors'] == 0:
            recommendations.append("✅ No se encontraron errores en el debug.log")
            return recommendations
        
        # Recomendaciones por plugins problemáticos
        for plugin_name, data in analysis['problematic_plugins'].items():
            if data['severity'] == 'high':
                recommendations.append(f"🚨 CRÍTICO: Desactivar inmediatamente el plugin '{plugin_name}' - {data['error_count']} errores fatales")
            elif data['severity'] == 'medium':
                recommendations.append(f"⚠️ ADVERTENCIA: Revisar el plugin '{plugin_name}' - {data['error_count']} errores")
            else:
                recommendations.append(f"ℹ️ INFO: Monitorear el plugin '{plugin_name}' - {data['error_count']} avisos menores")
        
        # Recomendaciones por tipos de errores
        if 'fatal_error' in analysis['error_types']:
            recommendations.append("🔥 Se detectaron errores fatales - Revisar inmediatamente")
        
        if 'deprecated' in analysis['error_types']:
            recommendations.append("📅 Se detectaron funciones obsoletas - Actualizar plugins/temas")
        
        if analysis['total_errors'] > 50:
            recommendations.append("📊 Alto volumen de errores - Considerar limpieza del debug.log")
        
        return recommendations
    
    def analyze_problematic_plugins(self):
        """Función dedicada para analizar plugins problemáticos desde debug.log"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        try:
            debug_path = self.debug_path_var.get()
            
            # Verificar si el archivo debug.log existe
            check_command = f"test -f {debug_path} && echo 'exists' || echo 'not_exists'"
            file_status = self.execute_ssh_command(check_command).strip()
            
            if file_status == 'not_exists':
                messagebox.showwarning("Advertencia", 
                    f"El archivo debug.log no existe en: {debug_path}\n"
                    f"Use 'Leer Debug.log' para crear el archivo primero.")
                return
            
            # Leer más líneas para un análisis más completo (últimas 500 líneas)
            command = f"tail -500 {debug_path}"
            log_content = self.execute_ssh_command(command)
            
            if not log_content or log_content.strip() == "":
                messagebox.showinfo("Información", "El debug.log está vacío. No hay errores para analizar.")
                return
            
            # Analizar el contenido
            analysis = self.analyze_debug_log(log_content)
            
            # Mostrar resultados en una ventana dedicada
            self.show_analysis_window(analysis)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al analizar debug.log: {str(e)}")
    
    def show_analysis_window(self, analysis):
        """Mostrar ventana dedicada con análisis de plugins problemáticos"""
        # Crear ventana de análisis
        analysis_window = tk.Toplevel(self.root)
        analysis_window.title("🔍 Análisis de Plugins Problemáticos")
        analysis_window.geometry("800x600")
        analysis_window.transient(self.root)
        analysis_window.grab_set()
        
        # Frame principal con scroll
        main_frame = ttk.Frame(analysis_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        title_label = ttk.Label(main_frame, text="🔍 Análisis de Plugins Problemáticos", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Área de texto con scroll
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        analysis_text = scrolledtext.ScrolledText(text_frame, height=25, wrap=tk.WORD)
        analysis_text.pack(fill=tk.BOTH, expand=True)
        
        # Generar contenido del análisis
        content = self.generate_analysis_report(analysis)
        analysis_text.insert(tk.END, content)
        analysis_text.config(state=tk.DISABLED)  # Solo lectura
        
        # Frame de botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Botón para desactivar plugins problemáticos
        if analysis['problematic_plugins']:
            ttk.Button(button_frame, text="⚠️ Desactivar Plugins Críticos", 
                      command=lambda: self.deactivate_critical_plugins(analysis, analysis_window),
                      style='Warning.TButton').pack(side=tk.LEFT, padx=5)
        
        # Botón para exportar reporte
        ttk.Button(button_frame, text="📄 Exportar Reporte", 
                  command=lambda: self.export_analysis_report(analysis),
                  style='Info.TButton').pack(side=tk.LEFT, padx=5)
        
        # Botón cerrar
        ttk.Button(button_frame, text="Cerrar", 
                  command=analysis_window.destroy,
                  style='Primary.TButton').pack(side=tk.RIGHT, padx=5)
    
    def generate_analysis_report(self, analysis):
        """Generar reporte detallado del análisis"""
        report = f"=== REPORTE DE ANÁLISIS DE DEBUG.LOG ===\n"
        report += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Total de errores encontrados: {analysis['total_errors']}\n\n"
        
        if analysis['total_errors'] == 0:
            report += "✅ ¡Excelente! No se encontraron errores en el debug.log.\n"
            report += "Su sitio WordPress parece estar funcionando correctamente.\n"
            return report
        
        # Resumen de plugins problemáticos
        if analysis['problematic_plugins']:
            report += f"🚨 PLUGINS PROBLEMÁTICOS DETECTADOS: {len(analysis['problematic_plugins'])}\n"
            report += "="*60 + "\n\n"
            
            for plugin_name, data in analysis['problematic_plugins'].items():
                severity_icon = "🔥" if data['severity'] == 'high' else "⚠️" if data['severity'] == 'medium' else "ℹ️"
                severity_text = "CRÍTICO" if data['severity'] == 'high' else "ADVERTENCIA" if data['severity'] == 'medium' else "INFORMACIÓN"
                
                report += f"{severity_icon} PLUGIN: {plugin_name}\n"
                report += f"   Severidad: {severity_text}\n"
                report += f"   Errores: {data['error_count']}\n"
                report += f"   Tipos: {', '.join(data['error_types'])}\n"
                report += f"   Último error: {data['last_error'][:100]}...\n\n"
        
        # Recomendaciones
        if analysis['recommendations']:
            report += "💡 RECOMENDACIONES:\n"
            report += "="*30 + "\n"
            for i, recommendation in enumerate(analysis['recommendations'], 1):
                report += f"{i}. {recommendation}\n"
            report += "\n"
        
        # Estadísticas de tipos de errores
        if analysis['error_types']:
            report += "📊 ESTADÍSTICAS DE ERRORES:\n"
            report += "="*35 + "\n"
            for error_type, count in sorted(analysis['error_types'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / analysis['total_errors']) * 100
                report += f"• {error_type}: {count} ({percentage:.1f}%)\n"
            report += "\n"
        
        # Errores recientes
        if analysis['recent_errors']:
            report += "🕒 ERRORES RECIENTES:\n"
            report += "="*25 + "\n"
            for error in analysis['recent_errors'][-5:]:  # Últimos 5 errores
                report += f"[{error['timestamp']}] {error['type']}: {error['message'][:80]}...\n"
        
        return report
    
    def deactivate_critical_plugins(self, analysis, parent_window):
        """Desactivar plugins con errores críticos"""
        critical_plugins = [name for name, data in analysis['problematic_plugins'].items() 
                           if data['severity'] == 'high']
        
        if not critical_plugins:
            messagebox.showinfo("Información", "No se encontraron plugins con errores críticos.")
            return
        
        # Confirmar acción
        plugin_list = '\n'.join(f"• {plugin}" for plugin in critical_plugins)
        if messagebox.askyesno("Confirmar Desactivación", 
                              f"¿Desea desactivar los siguientes plugins críticos?\n\n{plugin_list}\n\n"
                              f"Esta acción puede ayudar a estabilizar su sitio."):
            
            try:
                if not self.wp_cli_manager:
                    messagebox.showerror("Error", "WP-CLI no está disponible para desactivar plugins.")
                    return
                
                success_count = 0
                error_count = 0
                
                for plugin in critical_plugins:
                    try:
                        # Intentar desactivar el plugin
                        result = self.wp_cli_manager.deactivate_plugin(plugin)
                        if result:
                            success_count += 1
                            # Marcar el plugin como resuelto automáticamente
                            self.save_resolved_plugin(
                                plugin, 
                                "Plugin crítico desactivado automáticamente",
                                f"Plugin desactivado por errores críticos detectados en debug.log"
                            )
                        else:
                            error_count += 1
                    except Exception as e:
                        print(f"Error desactivando {plugin}: {e}")
                        error_count += 1
                
                # Mostrar resultado
                messagebox.showinfo("Resultado", 
                                  f"Desactivación completada:\n"
                                  f"✅ Exitosos: {success_count}\n"
                                  f"❌ Errores: {error_count}")
                
                # Actualizar lista de plugins si hubo éxitos
                if success_count > 0:
                    self.scan_plugins()
                
                parent_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error durante la desactivación: {str(e)}")
    
    def export_analysis_report(self, analysis):
        """Exportar reporte de análisis a archivo"""
        try:
            from tkinter import filedialog
            
            # Generar nombre de archivo con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"debug_analysis_{timestamp}.txt"
            
            # Solicitar ubicación de guardado
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
                initialname=default_filename,
                title="Guardar Reporte de Análisis"
            )
            
            if file_path:
                # Generar y guardar reporte
                report_content = self.generate_analysis_report(analysis)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                messagebox.showinfo("Éxito", f"Reporte exportado correctamente:\n{file_path}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar reporte: {str(e)}")
    
    def toggle_python_capture(self):
        """Activar/desactivar captura de salida Python"""
        if not self.python_capture_active:
            # Inicializar captura si no existe
            if not self.python_capture:
                self.python_capture = PythonOutputCapture(self.log_to_global_area)
            
            # Activar captura
            self.python_capture.start_capture()
            self.python_capture_active = True
            self.python_capture_button.configure(text="🐍 Detener Python", style='Warning.TButton')
            
            # Mensaje informativo
            self.log_to_global_area("=== CAPTURA DE SALIDA PYTHON ACTIVADA ===", "SUCCESS")
            self.log_to_global_area("Todos los print() de Python ahora aparecerán en los logs globales", "INFO")
            
            # Ejemplo de funcionamiento
            print("¡Captura de salida Python activada! Este mensaje aparece en los logs.")
            
        else:
            # Desactivar captura
            if self.python_capture:
                self.python_capture.stop_capture()
            
            self.python_capture_active = False
            self.python_capture_button.configure(text="🐍 Capturar Python", style='Success.TButton')
            
            # Mensaje informativo
            self.log_to_global_area("=== CAPTURA DE SALIDA PYTHON DESACTIVADA ===", "WARNING")
            self.log_to_global_area("Los print() de Python vuelven a la consola normal", "INFO")
    
    def save_current_config(self):
        """Guardar configuración actual"""
        self.config["wordpress"]["path"] = self.wp_path_var.get()
        self.config["wordpress"]["url"] = self.wp_url_var.get()
        self.config["wordpress"]["debug_log_path"] = self.debug_path_var.get()
        
        # Guardar configuración de captura de Python
        if "python_capture" not in self.config:
            self.config["python_capture"] = {}
        self.config["python_capture"]["enabled"] = self.python_capture_enabled_var.get()
        
        # Aplicar cambio inmediatamente
        if self.config["python_capture"]["enabled"] and not self.python_capture_active:
            self.toggle_python_capture()
        elif not self.config["python_capture"]["enabled"] and self.python_capture_active:
            self.toggle_python_capture()
        
        self.save_config()
        messagebox.showinfo("Éxito", "Configuración guardada correctamente")
    
    def log_to_global_area(self, message, level="INFO"):
        """Enviar mensaje al área de logs globales"""
        self.global_log_message(message, level)
    
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
                # Marcar el plugin como resuelto automáticamente
                self.save_resolved_plugin(
                    plugin_name, 
                    "Plugin desactivado por el usuario",
                    "Plugin desactivado manualmente desde la interfaz"
                )
                
                messagebox.showinfo("Éxito", f"{message}\n\nEl plugin ha sido marcado como resuelto y sus errores futuros en debug.log serán filtrados.")
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
            # Inicializar sistema de logging
            self.testing_active = True
            self.start_test_timer()
            self.log_message("INFO", f"Iniciando test individual del plugin: {plugin_name}")
            
            # Limpiar logs anteriores
            self.testing_results.delete(1.0, tk.END)
            
            # Fase 1: Preparación
            self.update_test_phase("Preparando test", plugin_name)
            self.testing_progress_var.set(f"Probando plugin: {plugin_name}")
            
            # Fase 2: Activación
            self.update_test_phase("Activando plugin", plugin_name)
            url = self.test_url_var.get().strip() or None
            
            self.log_message("INFO", f"Ejecutando test de activación...", plugin_name)
            result = self.wp_cli_manager.test_plugin_activation(plugin_name, url)
            
            if result[0]:
                test_data = result[1]
                
                # Fase 3: Análisis de resultados
                self.update_test_phase("Analizando resultados", plugin_name)
                
                # Log detallado de cada verificación
                self.log_message("INFO", f"Activación: {'exitosa' if test_data['activation_successful'] else 'falló'}", plugin_name)
                self.log_message("INFO", f"Sitio accesible: {'sí' if test_data['site_accessible'] else 'no'}", plugin_name)
                self.log_message("INFO", f"Tiempo de respuesta: {test_data['response_time']}s", plugin_name)
                self.log_message("INFO", f"Código de estado HTTP: {test_data['status_code']}", plugin_name)
                
                if test_data['has_errors']:
                    self.log_message("WARNING", f"Se detectaron errores durante el test", plugin_name)
                    for error in test_data['error_details']:
                        self.log_message("ERROR", f"Error: {error}", plugin_name)
                else:
                    self.log_message("SUCCESS", "No se detectaron errores", plugin_name)
                
                # Resultado final
                if test_data['test_passed']:
                    self.show_test_result(plugin_name, True)
                    self.testing_progress_var.set("✅ Plugin aprobado")
                    self.update_test_phase("Completado exitosamente", plugin_name)
                    # Actualizar estado de testing a aprobado
                    self.update_plugin_test_status(plugin_name, 'approved')
                else:
                    error_details = test_data['error_details'] if test_data['error_details'] else ["Falló verificaciones básicas"]
                    self.show_test_result(plugin_name, False, error_details)
                    self.testing_progress_var.set("❌ Plugin con problemas")
                    self.update_test_phase("Completado con errores", plugin_name)
                    
                    # Determinar si es warning o failed basado en la severidad
                    if test_data['has_errors'] and not test_data['site_accessible']:
                        # Plugin rompe la web - estado failed
                        self.update_plugin_test_status(plugin_name, 'failed')
                    else:
                        # Plugin funciona pero con advertencias - estado warning
                        self.update_plugin_test_status(plugin_name, 'warning')
                    
                    # Preguntar si desactivar el plugin
                    if messagebox.askyesno("Plugin Problemático", 
                                         f"El plugin '{plugin_name}' causa problemas. ¿Desactivarlo?"):
                        self.log_message("INFO", "Desactivando plugin problemático...", plugin_name)
                        self.wp_cli_manager.deactivate_plugin(plugin_name)
                        self.log_message("SUCCESS", "Plugin desactivado exitosamente", plugin_name)
                        self.testing_progress_var.set("🔄 Plugin desactivado")
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.log_message("ERROR", f"Error al ejecutar test: {error_msg}", plugin_name)
                self.show_test_result(plugin_name, False, [error_msg])
                self.testing_progress_var.set("❌ Error en test")
                self.update_test_phase("Error en ejecución", plugin_name)
                # Marcar como fallido si hay error en la ejecución
                self.update_plugin_test_status(plugin_name, 'failed')
                
        except Exception as e:
            self.log_message("ERROR", f"Excepción durante el test: {str(e)}", plugin_name)
            messagebox.showerror("Error", f"Error al probar plugin: {str(e)}")
            self.testing_progress_var.set("❌ Error")
            self.update_test_phase("Error crítico", plugin_name)
            # Marcar como fallido si hay excepción
            self.update_plugin_test_status(plugin_name, 'failed')
        finally:
            self.testing_active = False
    
    def test_all_plugins(self):
        """Probar todos los plugins"""
        if not self.wp_cli_manager:
            messagebox.showerror("Error", "WP-CLI no está disponible. Conecte primero.")
            return
        
        try:
            # Obtener lista de plugins
            self.log_message("INFO", "Obteniendo lista completa de plugins")
            self.update_test_phase("Obteniendo lista de plugins")
            
            all_plugins = self.wp_cli_manager.list_plugins('all')
            if not all_plugins:
                messagebox.showerror("Error", "No se pudo obtener la lista de plugins.")
                return
            
            # Filtrar plugins según configuración
            if self.test_inactive_only_var.get():
                plugins_to_test = [p['name'] for p in all_plugins if p.get('status') == 'inactive']
                self.log_message("INFO", f"Filtrando solo plugins inactivos: {len(plugins_to_test)} encontrados")
            else:
                plugins_to_test = [p['name'] for p in all_plugins]
                self.log_message("INFO", f"Testing de todos los plugins: {len(plugins_to_test)} encontrados")
            
            if not plugins_to_test:
                messagebox.showinfo("Info", "No hay plugins para probar.")
                return
            
            # Confirmar testing
            if not messagebox.askyesno("Confirmar Testing", 
                                     f"¿Probar {len(plugins_to_test)} plugins?\n"
                                     f"Rollback automático: {'Sí' if self.auto_rollback_var.get() else 'No'}"):
                return
            
            # Inicializar sistema de logging para testing completo
            self.testing_active = True
            self.start_test_timer()
            self.testing_progress['maximum'] = len(plugins_to_test)
            self.testing_progress['value'] = 0
            self.testing_results.delete(1.0, tk.END)
            
            self.log_message("INFO", f"Iniciando testing completo de {len(plugins_to_test)} plugins")
            self.update_test_phase("Preparando testing completo")
            
            # Ejecutar testing por lotes
            url = self.test_url_var.get().strip() or None
            auto_rollback = self.auto_rollback_var.get()
            
            self.log_message("INFO", f"URL de prueba: {url if url else 'No especificada'}")
            self.log_message("INFO", f"Rollback automático: {'Habilitado' if auto_rollback else 'Deshabilitado'}")
            self.log_message("INFO", f"Solo plugins inactivos: {'Sí' if self.test_inactive_only_var.get() else 'No'}")
            
            self.update_test_phase("Ejecutando testing completo")
            result = self.wp_cli_manager.test_plugin_batch(plugins_to_test, url, auto_rollback)
            
            if result[0]:
                batch_data = result[1]
                
                # Log de resumen
                self.update_test_phase("Procesando resultados completos")
                self.log_message("INFO", f"Testing completo finalizado - Total: {batch_data['total_tested']}")
                self.log_message("SUCCESS", f"Tests exitosos: {batch_data['successful_tests']}")
                
                if batch_data['problematic_plugins']:
                    self.log_message("WARNING", f"Plugins problemáticos encontrados: {len(batch_data['problematic_plugins'])}")
                    for plugin in batch_data['problematic_plugins']:
                        self.log_message("ERROR", f"Plugin problemático: {plugin}", plugin)
                
                # Log detallado de cada plugin
                successful_count = 0
                for i, test_result in enumerate(batch_data['detailed_results']):
                    plugin_name = test_result['plugin_name']
                    self.testing_progress['value'] = i + 1
                    
                    if test_result.get('test_passed', False):
                        successful_count += 1
                        self.show_test_result(plugin_name, True)
                        # Actualizar estado a aprobado
                        self.update_plugin_test_status(plugin_name, 'approved')
                    else:
                        error_details = test_result.get('error_details', ['Test falló'])
                        self.show_test_result(plugin_name, False, error_details)
                        
                        # Determinar si es warning o failed basado en los detalles del error
                        if test_result.get('site_accessible', True):
                            # El sitio sigue accesible, pero hay errores - warning
                            self.update_plugin_test_status(plugin_name, 'warning')
                        else:
                            # El sitio no es accesible - failed
                            self.update_plugin_test_status(plugin_name, 'failed')
                
                # Resultado final
                self.testing_progress['value'] = len(plugins_to_test)
                self.testing_progress_var.set(f"✅ Testing completo: {successful_count}/{len(plugins_to_test)} exitosos")
                self.update_test_phase("Testing completo finalizado")
                self.log_message("SUCCESS", f"Testing completo terminado - {successful_count}/{len(plugins_to_test)} plugins aprobados")
                
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.log_message("ERROR", f"Error en testing completo: {error_msg}")
                self.testing_progress_var.set("❌ Error en testing completo")
                self.update_test_phase("Error en testing completo")
            
            self.testing_active = False
            
        except Exception as e:
            self.log_message("ERROR", f"Excepción durante testing completo: {str(e)}")
            messagebox.showerror("Error", f"Error en testing por lotes: {str(e)}")
            self.testing_progress_var.set("❌ Error")
            self.update_test_phase("Error crítico")
            self.testing_active = False
    
    def test_selected_plugins(self):
        """Probar plugins seleccionados en la lista principal (ENHANCED in 1.1)"""
        # Usar la nueva función para obtener plugins seleccionados
        selected_plugins = self.get_selected_plugins()
        if not selected_plugins:
            messagebox.showinfo("Info", "Seleccione plugins usando los checkboxes en la pestaña de Plugins.")
            return
        
        try:
            # Obtener nombres de plugins seleccionados
            plugins_to_test = [plugin['name'] for plugin in selected_plugins]
            
            if not plugins_to_test:
                return
            
            # Confirmar testing
            if not messagebox.askyesno("Confirmar Testing", 
                                     f"¿Probar {len(plugins_to_test)} plugins seleccionados?\n"
                                     f"Rollback automático: {'Sí' if self.auto_rollback_var.get() else 'No'}"):
                return
            
            # Inicializar sistema de logging para batch
            self.testing_active = True
            self.start_test_timer()
            self.testing_progress['maximum'] = len(plugins_to_test)
            self.testing_progress['value'] = 0
            self.testing_results.delete(1.0, tk.END)
            
            self.log_message("INFO", f"Iniciando testing por lotes de {len(plugins_to_test)} plugins")
            self.update_test_phase("Preparando testing por lotes")
            
            # Ejecutar testing
            url = self.test_url_var.get().strip() or None
            auto_rollback = self.auto_rollback_var.get()
            
            if not self.wp_cli_manager:
                messagebox.showerror("Error", "No hay conexión SSH activa. Conecte primero desde la pestaña 'Conexión SSH'.")
                self.testing_active = False
                return
            
            self.log_message("INFO", f"URL de prueba: {url if url else 'No especificada'}")
            self.log_message("INFO", f"Rollback automático: {'Habilitado' if auto_rollback else 'Deshabilitado'}")
            
            # Ejecutar testing por lotes con logging detallado
            self.update_test_phase("Ejecutando tests")
            result = self.wp_cli_manager.test_plugin_batch(plugins_to_test, url, auto_rollback)
            
            if result[0]:
                batch_data = result[1]
                
                # Log de resumen
                self.update_test_phase("Procesando resultados")
                self.log_message("INFO", f"Testing completado - Total: {batch_data['total_tested']}")
                self.log_message("SUCCESS", f"Tests exitosos: {batch_data['successful_tests']}")
                
                if batch_data['problematic_plugins']:
                    self.log_message("WARNING", f"Plugins problemáticos: {len(batch_data['problematic_plugins'])}")
                    for plugin in batch_data['problematic_plugins']:
                        self.log_message("ERROR", f"Plugin problemático: {plugin}", plugin)
                
                # Log detallado de cada plugin
                successful_count = 0
                for i, test_result in enumerate(batch_data['detailed_results']):
                    plugin_name = test_result['plugin_name']
                    self.testing_progress['value'] = i + 1
                    
                    if test_result.get('test_passed', False):
                        successful_count += 1
                        self.show_test_result(plugin_name, True)
                    else:
                        error_details = test_result.get('error_details', ['Test falló'])
                        self.show_test_result(plugin_name, False, error_details)
                
                # Resultado final
                self.testing_progress['value'] = len(plugins_to_test)
                self.testing_progress_var.set(f"✅ Testing completado: {successful_count}/{len(plugins_to_test)} exitosos")
                self.update_test_phase("Completado exitosamente")
                self.log_message("SUCCESS", f"Testing por lotes finalizado - {successful_count}/{len(plugins_to_test)} plugins aprobados")
                
            else:
                error_msg = result[1].get('error', 'Error desconocido')
                self.log_message("ERROR", f"Error en testing por lotes: {error_msg}")
                self.testing_progress_var.set("❌ Error en testing")
                self.update_test_phase("Error en ejecución")
            
            self.testing_active = False
            
        except Exception as e:
            self.log_message("ERROR", f"Excepción durante testing por lotes: {str(e)}")
            messagebox.showerror("Error", f"Error en testing: {str(e)}")
            self.testing_progress_var.set("❌ Error")
            self.update_test_phase("Error crítico")
            self.testing_active = False
    
    def stop_testing(self):
        """Detener el testing en curso"""
        self.testing_active = False
        self.testing_progress_var.set("🛑 Testing detenido")
        self.log_message("WARNING", "Testing detenido por el usuario")
    
    # === SISTEMA DE LOGGING MEJORADO ===
    
    def log_message(self, level, message, plugin_name=None):
        """Agregar mensaje al log con timestamp y formato"""
        if self.log_paused:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Formatear mensaje
        if plugin_name:
            formatted_msg = f"[{timestamp}] [{level}] [{plugin_name}] {message}"
        else:
            formatted_msg = f"[{timestamp}] [{level}] {message}"
        
        # Almacenar en lista completa
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'plugin_name': plugin_name,
            'formatted': formatted_msg
        }
        self.all_logs.append(log_entry)
        
        # Mostrar si pasa el filtro
        if self.should_show_log(level):
            self.display_log_message(formatted_msg, level)
        
        # También enviar al sistema de logs global
        if plugin_name:
            source = f"Testing - {plugin_name}"
        else:
            source = "System"
        self.global_log_message(level, message, source)
    
    def should_show_log(self, level):
        """Verificar si el log debe mostrarse según el filtro actual"""
        filter_level = self.log_level_var.get()
        if filter_level == "ALL":
            return True
        return filter_level == level
    
    def display_log_message(self, message, level):
        """Mostrar mensaje en el área de logs con formato"""
        if not hasattr(self, 'testing_results'):
            return
            
        # Insertar mensaje con tag de color
        self.testing_results.insert(tk.END, message + "\n", level)
        
        # Auto-scroll si está habilitado
        if self.auto_scroll_var.get():
            self.testing_results.see(tk.END)
    
    def update_test_phase(self, phase, plugin_name=None):
        """Actualizar la fase actual del test"""
        self.current_test_phase = phase
        self.current_phase_var.set(phase)
        
        if plugin_name:
            self.current_plugin_var.set(plugin_name)
            self.log_message("PHASE", f"Iniciando fase: {phase}", plugin_name)
        else:
            self.log_message("PHASE", f"Fase: {phase}")
    
    def start_test_timer(self):
        """Iniciar el cronómetro del test"""
        self.test_start_time = time.time()
        self.update_elapsed_time()
    
    def update_elapsed_time(self):
        """Actualizar el tiempo transcurrido"""
        if self.test_start_time and self.testing_active:
            elapsed = time.time() - self.test_start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.elapsed_time_var.set(f"{minutes:02d}:{seconds:02d}")
            
            # Programar próxima actualización
            self.root.after(1000, self.update_elapsed_time)
    
    def clear_logs(self):
        """Limpiar el área de logs"""
        self.testing_results.delete(1.0, tk.END)
        self.all_logs.clear()
        self.log_message("INFO", "Logs limpiados")
    
    def filter_logs(self, event=None):
        """Filtrar logs según el nivel seleccionado"""
        self.testing_results.delete(1.0, tk.END)
        
        filter_level = self.log_level_var.get()
        for log_entry in self.all_logs:
            if filter_level == "ALL" or log_entry['level'] == filter_level:
                self.display_log_message(log_entry['formatted'], log_entry['level'])
    
    def toggle_log_pause(self):
        """Pausar/reanudar el logging"""
        self.log_paused = not self.log_paused
        status = "pausado" if self.log_paused else "reanudado"
        if not self.log_paused:  # Solo mostrar si no está pausado
            self.log_message("INFO", f"Logging {status}")
    
    def export_logs(self):
        """Exportar logs a archivo"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
                title="Exportar logs"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("=== LOGS DE TESTING DE PLUGINS ===\n")
                    f.write(f"Exportado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    for log_entry in self.all_logs:
                        f.write(log_entry['formatted'] + "\n")
                
                self.log_message("SUCCESS", f"Logs exportados a: {filename}")
                messagebox.showinfo("Éxito", f"Logs exportados exitosamente a:\n{filename}")
                
        except Exception as e:
            self.log_message("ERROR", f"Error al exportar logs: {str(e)}")
            messagebox.showerror("Error", f"Error al exportar logs: {str(e)}")
    
    def show_test_result(self, plugin_name, success, details=None):
        """Mostrar resultado final del test con recomendaciones"""
        if success:
            self.log_message("SUCCESS", f"✅ Plugin '{plugin_name}' aprobó todas las pruebas", plugin_name)
            self.log_message("INFO", f"Recomendación: Plugin '{plugin_name}' es seguro para activar", plugin_name)
        else:
            self.log_message("ERROR", f"❌ Plugin '{plugin_name}' falló las pruebas", plugin_name)
            self.log_message("WARNING", f"Recomendación: NO activar '{plugin_name}' en producción", plugin_name)
            
            if details:
                for detail in details:
                    self.log_message("ERROR", f"  - {detail}", plugin_name)
    
    # === MÉTODOS DE LOGGING PARA PESTAÑA DE PLUGINS ===
    
    def plugins_log_message(self, level, message, plugin_name=None):
        """Registrar mensaje con formato y timestamp para pestaña de plugins"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Formatear mensaje
        if plugin_name:
            formatted_message = f"[{timestamp}] [{level}] [{plugin_name}] {message}"
        else:
            formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # Almacenar en lista completa
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'plugin_name': plugin_name,
            'formatted': formatted_message
        }
        self.plugins_all_logs.append(log_entry)
        
        # Mostrar si no está pausado y pasa el filtro
        if not self.plugins_log_paused and self.plugins_should_show_log(log_entry):
            self.plugins_display_log_message(formatted_message, level)
        
        # También enviar al sistema de logs global
        if plugin_name:
            source = f"Plugin Manager - {plugin_name}"
        else:
            source = "Plugin Manager"
        self.global_log_message(level, message, source)
    
    def plugins_should_show_log(self, log_entry):
        """Determinar si mostrar el log basado en filtros para pestaña de plugins"""
        if not hasattr(self, 'plugins_log_level_combo'):
            return True
            
        selected_level = self.plugins_log_level_combo.get()
        if selected_level == "TODOS":
            return True
        return log_entry['level'] == selected_level
    
    def plugins_display_log_message(self, message, level):
        """Mostrar mensaje en el área de logs con colores para pestaña de plugins"""
        if not hasattr(self, 'plugins_log_text'):
            return
            
        self.plugins_log_text.insert(tk.END, message + "\n", level)
        self.plugins_log_text.see(tk.END)  # Auto-scroll
    
    def plugins_update_phase(self, phase):
        """Actualizar fase actual del proceso para pestaña de plugins"""
        self.plugins_current_phase = phase
        if hasattr(self, 'plugins_current_phase_var'):
            self.plugins_current_phase_var.set(phase)
        self.plugins_log_message("INFO", f"Fase: {phase}")
    
    def plugins_start_timer(self):
        """Iniciar temporizador para pestaña de plugins"""
        self.plugins_start_time = time.time()
        self.plugins_operation_active = True
        self.plugins_timer_stopped = False
        self.plugins_update_elapsed_time()
    
    def plugins_stop_timer(self):
        """Detener temporizador para pestaña de plugins"""
        self.plugins_operation_active = False
        self.plugins_timer_stopped = True
    
    def plugins_update_elapsed_time(self):
        """Actualizar tiempo transcurrido para pestaña de plugins"""
        if self.plugins_start_time and hasattr(self, 'plugins_elapsed_time_var'):
            elapsed = time.time() - self.plugins_start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            self.plugins_elapsed_time_var.set(time_str)
            
            # Programar próxima actualización SOLO si hay operación activa
            # Agregar condiciones de parada para evitar bucles infinitos
            if (hasattr(self, 'plugins_frame') and 
                hasattr(self, 'plugins_operation_active') and 
                self.plugins_operation_active and
                not getattr(self, 'plugins_timer_stopped', False)):
                self.plugins_frame.after(1000, self.plugins_update_elapsed_time)
    
    def clear_plugins_logs(self):
        """Limpiar área de logs para pestaña de plugins"""
        if hasattr(self, 'plugins_log_text'):
            self.plugins_log_text.delete(1.0, tk.END)
        self.plugins_all_logs.clear()
        self.plugins_log_message("INFO", "Logs limpiados")
    
    def filter_plugins_logs(self, event=None):
        """Filtrar logs por nivel para pestaña de plugins"""
        if not hasattr(self, 'plugins_log_text'):
            return
            
        # Limpiar área de logs
        self.plugins_log_text.delete(1.0, tk.END)
        
        # Mostrar logs filtrados
        for log_entry in self.plugins_all_logs:
            if self.plugins_should_show_log(log_entry):
                self.plugins_display_log_message(log_entry['formatted'], log_entry['level'])
    
    def toggle_plugins_log_pause(self):
        """Alternar pausa de logs para pestaña de plugins"""
        self.plugins_log_paused = not self.plugins_log_paused
        if hasattr(self, 'plugins_pause_btn'):
            if self.plugins_log_paused:
                self.plugins_pause_btn.config(text="Reanudar")
                self.plugins_log_message("WARNING", "Logs pausados")
            else:
                self.plugins_pause_btn.config(text="Pausar")
                self.plugins_log_message("INFO", "Logs reanudados")
    
    def export_plugins_logs(self):
        """Exportar logs a archivo para pestaña de plugins"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plugins_logs_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=== LOGS DE GESTIÓN DE PLUGINS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
                for log_entry in self.plugins_all_logs:
                    f.write(log_entry['formatted'] + '\n')
            
            self.plugins_log_message("SUCCESS", f"Logs exportados a: {filename}")
            messagebox.showinfo("Exportación Exitosa", f"Logs guardados en:\n{filename}")
            
        except Exception as e:
            self.plugins_log_message("ERROR", f"Error al exportar logs: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron exportar los logs:\n{str(e)}")
    
    def plugins_show_result(self, plugin_name, success, details=None):
        """Mostrar resultado final de operación con recomendaciones para pestaña de plugins"""
        if success:
            self.plugins_log_message("SUCCESS", f"✅ Operación exitosa en plugin '{plugin_name}'", plugin_name)
        else:
            self.plugins_log_message("ERROR", f"❌ Error en operación del plugin '{plugin_name}'", plugin_name)
            
            if details:
                for detail in details:
                    self.plugins_log_message("ERROR", f"  - {detail}", plugin_name)
    
    # === MÉTODOS DEL SISTEMA DE LOGS GLOBAL ===
    
    def global_log_message(self, level, message, source=None):
        """Añadir mensaje al sistema de logs global"""
        if self.global_log_paused:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        source_prefix = f"[{source}] " if source else ""
        formatted_message = f"[{timestamp}] {level}: {source_prefix}{message}"
        
        # Guardar en lista de todos los logs
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'source': source,
            'formatted': formatted_message
        }
        self.global_all_logs.append(log_entry)
        
        # Mostrar en la interfaz si debe mostrarse
        if self.global_should_show_log(level, source):
            self.global_display_log_message(formatted_message, level)
        
        # Actualizar contador
        self.global_log_count_var.set(f"{len(self.global_all_logs)}")
        
        # Mantener solo los últimos 1000 logs para evitar problemas de memoria
        if len(self.global_all_logs) > 1000:
            self.global_all_logs = self.global_all_logs[-1000:]
    
    def global_should_show_log(self, level, source=""):
        """Determinar si un log debe mostrarse según los filtros actuales"""
        # Filtro por nivel
        filter_level = self.global_log_level_var.get()
        level_match = filter_level == "TODOS" or level == filter_level
        
        # Filtro por fuente
        filter_source = self.global_log_source_var.get()
        source_match = filter_source == "TODAS" or source == filter_source
        
        return level_match and source_match
    
    def global_display_log_message(self, message, level):
        """Mostrar mensaje en el área de logs global"""
        try:
            self.global_logs_text.config(state=tk.NORMAL)
            
            # Añadir el mensaje con el color correspondiente
            if level in ["INFO", "SUCCESS", "WARNING", "ERROR", "PYTHON"]:
                self.global_logs_text.insert(tk.END, message + "\n", level)
            else:
                self.global_logs_text.insert(tk.END, message + "\n")
            
            # Auto-scroll al final
            self.global_logs_text.see(tk.END)
            self.global_logs_text.config(state=tk.DISABLED)
            
            # Actualizar la interfaz
            self.root.update_idletasks()
            
        except Exception as e:
            print(f"Error al mostrar log global: {e}")
    
    def clear_global_logs(self):
        """Limpiar todos los logs globales"""
        try:
            self.global_logs_text.config(state=tk.NORMAL)
            self.global_logs_text.delete(1.0, tk.END)
            self.global_logs_text.config(state=tk.DISABLED)
            
            self.global_all_logs.clear()
            self.global_log_count_var.set("0")
            
            self.global_log_message("INFO", "Logs globales limpiados")
            
        except Exception as e:
            print(f"Error al limpiar logs globales: {e}")
    
    def filter_global_logs(self, event=None):
        """Filtrar logs globales por nivel y fuente"""
        try:
            self.global_logs_text.config(state=tk.NORMAL)
            self.global_logs_text.delete(1.0, tk.END)
            
            filter_level = self.global_log_level_var.get()
            filter_source = self.global_log_source_var.get()
            
            for log_entry in self.global_all_logs:
                # Verificar filtro de nivel
                level_match = filter_level == "TODOS" or log_entry['level'] == filter_level
                
                # Verificar filtro de fuente
                source_match = filter_source == "TODAS" or log_entry.get('source') == filter_source
                
                if level_match and source_match:
                    level = log_entry['level']
                    if level in ["INFO", "SUCCESS", "WARNING", "ERROR", "PYTHON"]:
                        self.global_logs_text.insert(tk.END, log_entry['formatted'] + "\n", level)
                    else:
                        self.global_logs_text.insert(tk.END, log_entry['formatted'] + "\n")
            
            self.global_logs_text.see(tk.END)
            self.global_logs_text.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"Error al filtrar logs globales: {e}")
    
    def toggle_global_log_pause(self):
        """Alternar pausa de logs globales"""
        self.global_log_paused = not self.global_log_paused
        if self.global_log_paused:
            self.global_log_pause_var.set("▶️")
            self.global_pause_btn.config(bg='#10b981')  # Verde
        else:
            self.global_log_pause_var.set("⏸️")
            self.global_pause_btn.config(bg='#f59e0b')  # Amarillo
    
    def export_global_logs(self):
        """Exportar logs globales a archivo"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"global_logs_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=== LOGS GLOBALES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
                for log_entry in self.global_all_logs:
                    f.write(log_entry['formatted'] + '\n')
            
            self.global_log_message("SUCCESS", f"Logs exportados a: {filename}")
            messagebox.showinfo("Exportación Exitosa", f"Logs guardados en:\n{filename}")
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al exportar logs: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron exportar los logs:\n{str(e)}")

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
    
    # === MÉTODOS PARA SELECCIÓN MÚLTIPLE (NEW in 1.1) ===
    

    
    def update_plugin_display(self, apply_states=True):
        """Actualizar la visualización de plugins usando Treeview (ENHANCED in 1.1)"""
        # Evitar actualizaciones durante operaciones de plugins activas
        if hasattr(self, 'plugins_operation_active') and self.plugins_operation_active:
            print("DEBUG: Operación de plugins activa, posponiendo actualización de display")
            return
        
        # Cargar automáticamente los estados guardados de badges solo si se especifica
        if apply_states:
            self.apply_saved_test_states()
        
        # Usar el nuevo sistema de Treeview
        self.populate_plugins_tree()
        self.update_selection_count()
    
    def update_single_plugin_display(self, plugin_name, test_status):
        """Actualizar solo la visualización de un plugin específico para evitar redibujado completo"""
        try:
            # Buscar el plugin en la interfaz actual y actualizar solo su badge
            # Esto evita el redibujado completo que causa el comportamiento errático
            
            # Encontrar el plugin en los datos
            plugin_data = None
            for plugin in self.all_plugins_data:
                if plugin['name'] == plugin_name:
                    plugin_data = plugin
                    break
            
            if not plugin_data:
                return
            
            # Buscar el frame del plugin en la interfaz
            for widget in self.plugins_scrollable_frame.winfo_children():
                if hasattr(widget, 'winfo_children'):
                    # Buscar el label que contiene el nombre del plugin
                    for child in widget.winfo_children():
                        if hasattr(child, 'winfo_children'):
                            for subchild in child.winfo_children():
                                if (hasattr(subchild, 'cget') and 
                                    hasattr(subchild, 'configure') and
                                    plugin_name in str(subchild.cget('text'))):
                                    
                                    # Actualizar el texto del label con el nuevo badge
                                    status_icon = "🟢" if plugin_data.get('status') == 'active' else "🔴"
                                    test_badge = self.get_test_status_badge(test_status)
                                    new_text = f"{status_icon} {plugin_name} {test_badge}"
                                    subchild.configure(text=new_text)
                                    
                                    # Forzar actualización visual
                                    subchild.update_idletasks()
                                    return
            
            # Si no se encontró el widget específico, hacer un refresh mínimo
            # solo del área visible sin cambiar el scroll
            current_scroll_top = self.plugins_canvas.canvasy(0)
            self.populate_plugins_tree()
            self.plugins_canvas.yview_moveto(current_scroll_top / self.plugins_canvas.bbox("all")[3] if self.plugins_canvas.bbox("all") else 0)
            
        except Exception as e:
            # En caso de error, hacer el refresh completo como fallback
            self.global_log_message("DEBUG", f"Error en actualización específica de plugin, usando fallback: {str(e)}")
            self.update_plugin_display()
    
    def toggle_select_all(self):
        """Seleccionar o deseleccionar todos los plugins"""
        select_all = self.select_all_var.get()
        
        if select_all:
            # Seleccionar todos los plugins filtrados
            filtered_plugins = self.get_filtered_plugins()
            for plugin in filtered_plugins:
                plugin_name = plugin['name']
                self.selected_plugins.add(plugin_name)
                # Actualizar checkbox individual
                if plugin_name in self.plugin_vars:
                    self.plugin_vars[plugin_name].set(True)
        else:
            # Deseleccionar todos
            self.selected_plugins.clear()
            # Actualizar todos los checkboxes individuales
            for var in self.plugin_vars.values():
                var.set(False)
        
        self.update_selection_count()
    
    def clear_selection(self):
        """Limpiar toda la selección"""
        self.select_all_var.set(False)
        self.selected_plugins.clear()
        
        # Actualizar todos los checkboxes individuales
        for var in self.plugin_vars.values():
            var.set(False)
        
        self.update_selection_count()
    
    def get_selected_plugins(self):
        """Obtener lista de plugins seleccionados"""
        selected_plugins = []
        
        for plugin in self.all_plugins_data:
            if plugin['name'] in self.selected_plugins:
                selected_plugins.append(plugin)
        
        return selected_plugins
    
    def activate_selected_plugins(self):
        """Activar todos los plugins seleccionados"""
        selected_plugins = self.get_selected_plugins()
        
        if not selected_plugins:
            messagebox.showwarning("Advertencia", "No hay plugins seleccionados.")
            return
        
        if not messagebox.askyesno("Confirmar", 
                                 f"¿Activar {len(selected_plugins)} plugin(s) seleccionado(s)?"):
            return
        
        # Ejecutar en hilo separado para no bloquear la interfaz
        def activate_process():
            # Inicializar sistema de logging
            self.plugins_start_timer()
            self.plugins_update_phase("Iniciando activación de plugins")
            self.plugins_log_message("INFO", f"Iniciando activación de {len(selected_plugins)} plugins seleccionados")
            
            self.progress_var.set("Activando plugins seleccionados...")
            self.progress_bar.start()
            
            success_count = 0
            error_count = 0
            
            try:
                for i, plugin in enumerate(selected_plugins, 1):
                    plugin_name = plugin['name']
                    self.plugins_update_phase(f"Activando plugin {i}/{len(selected_plugins)}: {plugin_name}")
                    self.plugins_log_message("INFO", f"Activando plugin: {plugin_name}", plugin_name)
                    
                    # Actualizar progreso en tiempo real
                    self.root.after(0, lambda: self.progress_var.set(f"Activando {plugin_name}... ({i}/{len(selected_plugins)})"))
                    
                    try:
                        # Usar WPCLIManager para mejor manejo de errores
                        success, message = self.wp_cli_manager.activate_plugin(plugin_name)
                        
                        if success:
                            success_count += 1
                            self.plugins_log_message("SUCCESS", f"Plugin activado exitosamente: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, True)
                        else:
                            error_count += 1
                            self.plugins_log_message("ERROR", f"Error al activar plugin: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, False, [message])
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = str(e)
                        self.plugins_log_message("ERROR", f"Excepción al activar plugin: {error_msg}", plugin_name)
                        self.plugins_show_result(plugin_name, False, [error_msg])
                
                # Resumen final
                self.plugins_update_phase("Completado")
                self.plugins_log_message("INFO", f"Activación completada - Exitosos: {success_count}, Errores: {error_count}")
                
            except Exception as e:
                self.plugins_log_message("ERROR", f"Error general en activación: {str(e)}")
                self.plugins_update_phase("Error")
            
            finally:
                # Ejecutar en el hilo principal
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.plugins_stop_timer())
                self.root.after(0, lambda: self.progress_var.set("Listo"))
                
                # Actualizar la lista de plugins
                self.root.after(0, lambda: self.scan_plugins())
                
                # Mostrar resultado final
                self.root.after(0, lambda: messagebox.showinfo("Resultado", 
                                  f"Activación completada:\n"
                                  f"✅ Exitosos: {success_count}\n"
                                  f"❌ Errores: {error_count}"))
        
        # Iniciar el proceso en un hilo separado
        threading.Thread(target=activate_process, daemon=True).start()
    
    def deactivate_selected_plugins(self):
        """Desactivar todos los plugins seleccionados"""
        selected_plugins = self.get_selected_plugins()
        
        if not selected_plugins:
            messagebox.showwarning("Advertencia", "No hay plugins seleccionados.")
            return
        
        if not messagebox.askyesno("Confirmar", 
                                 f"¿Desactivar {len(selected_plugins)} plugin(s) seleccionado(s)?"):
            return
        
        # Ejecutar en hilo separado para no bloquear la interfaz
        def deactivate_process():
            # Inicializar sistema de logging
            self.plugins_start_timer()
            self.plugins_update_phase("Iniciando desactivación de plugins")
            self.plugins_log_message("INFO", f"Iniciando desactivación de {len(selected_plugins)} plugins seleccionados")
            
            self.progress_var.set("Desactivando plugins seleccionados...")
            self.progress_bar.start()
            
            success_count = 0
            error_count = 0
            
            try:
                for i, plugin in enumerate(selected_plugins, 1):
                    plugin_name = plugin['name']
                    self.plugins_update_phase(f"Desactivando plugin {i}/{len(selected_plugins)}: {plugin_name}")
                    self.plugins_log_message("INFO", f"Desactivando plugin: {plugin_name}", plugin_name)
                    
                    # Actualizar progreso en tiempo real
                    self.root.after(0, lambda: self.progress_var.set(f"Desactivando {plugin_name}... ({i}/{len(selected_plugins)})"))
                    
                    try:
                        # Usar WPCLIManager para mejor manejo de errores
                        success, message = self.wp_cli_manager.deactivate_plugin(plugin_name)
                        
                        if success:
                            success_count += 1
                            self.plugins_log_message("SUCCESS", f"Plugin desactivado exitosamente: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, True)
                        else:
                            error_count += 1
                            self.plugins_log_message("ERROR", f"Error al desactivar plugin: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, False, [message])
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = str(e)
                        self.plugins_log_message("ERROR", f"Excepción al desactivar plugin: {error_msg}", plugin_name)
                        self.plugins_show_result(plugin_name, False, [error_msg])
                
                # Resumen final
                self.plugins_update_phase("Completado")
                self.plugins_log_message("INFO", f"Desactivación completada - Exitosos: {success_count}, Errores: {error_count}")
                
            except Exception as e:
                self.plugins_log_message("ERROR", f"Error general en desactivación: {str(e)}")
                self.plugins_update_phase("Error")
            
            finally:
                # Ejecutar en el hilo principal
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.plugins_stop_timer())
                self.root.after(0, lambda: self.progress_var.set("Listo"))
                
                # Actualizar la lista de plugins
                self.root.after(0, lambda: self.scan_plugins())
                
                # Mostrar resultado final
                self.root.after(0, lambda: messagebox.showinfo("Resultado", 
                                  f"Desactivación completada:\n"
                                  f"✅ Exitosos: {success_count}\n"
                                  f"❌ Errores: {error_count}"))
        
        # Iniciar el proceso en un hilo separado
        threading.Thread(target=deactivate_process, daemon=True).start()
    
    def update_selected_plugins(self):
        """Actualizar todos los plugins seleccionados"""
        selected_plugins = self.get_selected_plugins()
        
        if not selected_plugins:
            messagebox.showwarning("Advertencia", "No hay plugins seleccionados.")
            return
        
        if not messagebox.askyesno("Confirmar", 
                                 f"¿Actualizar {len(selected_plugins)} plugin(s) seleccionado(s)?"):
            return
        
        # Ejecutar en hilo separado para no bloquear la interfaz
        def update_process():
            # Inicializar sistema de logging
            self.plugins_start_timer()
            self.plugins_update_phase("Iniciando actualización de plugins")
            self.plugins_log_message("INFO", f"Iniciando actualización de {len(selected_plugins)} plugins seleccionados")
            
            self.progress_var.set("Actualizando plugins seleccionados...")
            self.progress_bar.start()
            
            success_count = 0
            error_count = 0
            
            try:
                for i, plugin in enumerate(selected_plugins, 1):
                    plugin_name = plugin['name']
                    self.plugins_update_phase(f"Actualizando plugin {i}/{len(selected_plugins)}: {plugin_name}")
                    self.plugins_log_message("INFO", f"Actualizando plugin: {plugin_name}", plugin_name)
                    
                    # Actualizar progreso en tiempo real
                    self.root.after(0, lambda: self.progress_var.set(f"Actualizando {plugin_name}... ({i}/{len(selected_plugins)})"))
                    
                    try:
                        # Usar WPCLIManager para mejor manejo de errores
                        success, message = self.wp_cli_manager.update_plugin(plugin_name)
                        
                        if success:
                            success_count += 1
                            self.plugins_log_message("SUCCESS", f"Plugin actualizado exitosamente: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, True)
                        else:
                            error_count += 1
                            self.plugins_log_message("ERROR", f"Error al actualizar plugin: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, False, [message])
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = str(e)
                        self.plugins_log_message("ERROR", f"Excepción al actualizar plugin: {error_msg}", plugin_name)
                        self.plugins_show_result(plugin_name, False, [error_msg])
                
                # Resumen final
                self.plugins_update_phase("Completado")
                self.plugins_log_message("INFO", f"Actualización completada - Exitosos: {success_count}, Errores: {error_count}")
                
            except Exception as e:
                self.plugins_log_message("ERROR", f"Error general en actualización: {str(e)}")
                self.plugins_update_phase("Error")
            
            finally:
                # Ejecutar en el hilo principal
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.plugins_stop_timer())
                self.root.after(0, lambda: self.progress_var.set("Listo"))
                
                # Actualizar la lista de plugins
                self.root.after(0, lambda: self.scan_plugins())
                
                # Mostrar resultado final
                self.root.after(0, lambda: messagebox.showinfo("Resultado", 
                                  f"Actualización completada:\n"
                                  f"✅ Exitosos: {success_count}\n"
                                  f"❌ Errores: {error_count}"))
        
        # Iniciar el proceso en un hilo separado
        threading.Thread(target=update_process, daemon=True).start()
    
    def uninstall_selected_plugins(self):
        """Desinstalar todos los plugins seleccionados"""
        selected_plugins = self.get_selected_plugins()
        
        if not selected_plugins:
            messagebox.showwarning("Advertencia", "No hay plugins seleccionados.")
            return
        
        if not messagebox.askyesno("Confirmar", 
                                 f"⚠️ ¿DESINSTALAR {len(selected_plugins)} plugin(s) seleccionado(s)?\n\n"
                                 f"Esta acción NO se puede deshacer."):
            return
        
        # Ejecutar en hilo separado para no bloquear la interfaz
        def uninstall_process():
            # Inicializar sistema de logging
            self.plugins_start_timer()
            self.plugins_update_phase("Iniciando desinstalación de plugins")
            self.plugins_log_message("WARNING", f"Iniciando desinstalación de {len(selected_plugins)} plugins seleccionados - ACCIÓN IRREVERSIBLE")
            
            self.progress_var.set("Desinstalando plugins seleccionados...")
            self.progress_bar.start()
            
            success_count = 0
            error_count = 0
            
            try:
                for i, plugin in enumerate(selected_plugins, 1):
                    plugin_name = plugin['name']
                    self.plugins_update_phase(f"Desinstalando plugin {i}/{len(selected_plugins)}: {plugin_name}")
                    self.plugins_log_message("WARNING", f"Desinstalando plugin: {plugin_name}", plugin_name)
                    
                    # Actualizar progreso en tiempo real
                    self.root.after(0, lambda: self.progress_var.set(f"Desinstalando {plugin_name}... ({i}/{len(selected_plugins)})"))
                    
                    try:
                        # Usar WPCLIManager para mejor manejo de errores (incluye desactivación automática)
                        success, message = self.wp_cli_manager.uninstall_plugin(plugin_name, deactivate_first=True)
                        
                        if success:
                            success_count += 1
                            self.plugins_log_message("SUCCESS", f"Plugin desinstalado exitosamente: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, True)
                        else:
                            error_count += 1
                            self.plugins_log_message("ERROR", f"Error al desinstalar plugin: {message}", plugin_name)
                            self.plugins_show_result(plugin_name, False, [message])
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = str(e)
                        self.plugins_log_message("ERROR", f"Excepción al desinstalar plugin: {error_msg}", plugin_name)
                        self.plugins_show_result(plugin_name, False, [error_msg])
                
                # Resumen final
                self.plugins_update_phase("Completado")
                self.plugins_log_message("INFO", f"Desinstalación completada - Exitosos: {success_count}, Errores: {error_count}")
                
            except Exception as e:
                self.plugins_log_message("ERROR", f"Error general en desinstalación: {str(e)}")
                self.plugins_update_phase("Error")
            
            finally:
                # Ejecutar en el hilo principal
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.plugins_stop_timer())
                self.root.after(0, lambda: self.progress_var.set("Listo"))
                
                # Actualizar la lista de plugins
                self.root.after(0, lambda: self.scan_plugins())
                
                # Mostrar resultado final
                self.root.after(0, lambda: messagebox.showinfo("Resultado", 
                                  f"Desinstalación completada:\n"
                                  f"✅ Exitosos: {success_count}\n"
                                  f"❌ Errores: {error_count}"))
        
        # Iniciar el proceso en un hilo separado
        threading.Thread(target=uninstall_process, daemon=True).start()

    def populate_plugins_tree(self):
        """Poblar la lista de plugins con checkboxes nativos"""
        if not hasattr(self, 'plugins_scrollable_frame'):
            return
            
        # Limpiar widgets existentes
        for widget in self.plugins_scrollable_frame.winfo_children():
            widget.destroy()
        
        # Limpiar variables de checkbox
        self.plugin_vars.clear()
        
        # Obtener datos filtrados
        filtered_plugins = self.get_filtered_plugins()
        
        if not filtered_plugins:
            # Mostrar mensaje cuando no hay plugins
            no_plugins_frame = ttk.Frame(self.plugins_scrollable_frame)
            no_plugins_frame.pack(fill=tk.X, pady=20)
            
            ttk.Label(no_plugins_frame, text="📭 No se encontraron plugins", 
                     font=('Segoe UI', 12, 'bold')).pack()
            ttk.Label(no_plugins_frame, text="Haz clic en 'Escanear Plugins' para cargar la lista", 
                     font=('Segoe UI', 10)).pack()
            return
        
        # Crear widgets para cada plugin
        for i, plugin in enumerate(filtered_plugins):
            plugin_name = plugin['name']
            
            # Frame principal del plugin
            plugin_frame = ttk.Frame(self.plugins_scrollable_frame, style='Card.TFrame')
            plugin_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Configurar grid del frame
            plugin_frame.grid_columnconfigure(1, weight=1)
            
            # Variable para el checkbox
            var = tk.BooleanVar()
            var.set(plugin_name in self.selected_plugins)
            self.plugin_vars[plugin_name] = var
            
            # Checkbox
            checkbox = ttk.Checkbutton(plugin_frame, variable=var, 
                                     command=lambda pn=plugin_name: self.on_plugin_checkbox_change(pn))
            checkbox.grid(row=0, column=0, padx=(10, 5), pady=8, sticky='n')
            
            # Frame para información del plugin
            info_frame = ttk.Frame(plugin_frame)
            info_frame.grid(row=0, column=1, sticky='ew', padx=(0, 10), pady=5)
            info_frame.grid_columnconfigure(0, weight=1)
            
            # Nombre del plugin con icono de estado
            status = plugin.get('status', 'unknown')
            if status == 'active':
                status_icon = "🟢"
                status_color = '#10b981'
            elif status == 'inactive':
                status_icon = "⚪"
                status_color = '#6b7280'
            elif status == 'must-use':
                status_icon = "🔵"
                status_color = '#3b82f6'
            else:
                status_icon = "🔴"
                status_color = '#ef4444'
            
            # Frame para el header del plugin
            header_frame = ttk.Frame(info_frame)
            header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 2))
            header_frame.grid_columnconfigure(0, weight=1)
            
            # Obtener insignia de testing
            test_status = plugin.get('test_status', 'untested')
            test_badge = self.get_test_status_badge(test_status)
            
            # Verificar si el plugin está resuelto
            resolved_badge = ""
            if self.is_plugin_resolved(plugin_name):
                resolved_badge = " 🔒"
            
            # Nombre y estado con insignia de testing y resolución
            name_label = ttk.Label(header_frame, text=f"{status_icon} {plugin_name} {test_badge}{resolved_badge}", 
                                  font=('Segoe UI', 11, 'bold'))
            name_label.grid(row=0, column=0, sticky='w')
            
            # Versión y actualización
            version_text = plugin.get('version', 'N/A')
            if plugin.get('update_available', False):
                version_text += " ⬆️ Actualización disponible"
                version_color = '#f59e0b'
            else:
                version_color = '#6b7280'
            
            version_label = ttk.Label(header_frame, text=f"v{version_text}", 
                                    font=('Segoe UI', 9))
            version_label.grid(row=0, column=1, sticky='e', padx=(10, 0))
            
            # Descripción
            description = plugin.get('description', 'Sin descripción disponible')
            if len(description) > 100:
                description = description[:97] + "..."
            
            desc_label = ttk.Label(info_frame, text=description, 
                                 font=('Segoe UI', 9), foreground='#6b7280')
            desc_label.grid(row=1, column=0, sticky='ew', pady=(0, 2))
            
            # Estado de testing
            test_status_names = {
                'approved': '✅ Plugin aprobado - Funciona correctamente',
                'warning': '⚠️ Plugin con advertencias - Funciona con problemas menores',
                'failed': '❌ Plugin fallido - Causa errores o rompe la web',
                'untested': '❓ Plugin no probado'
            }
            test_status_text = test_status_names.get(test_status, '❓ Estado desconocido')
            test_color = self.get_test_status_color(test_status)
            
            test_label = ttk.Label(info_frame, text=test_status_text, 
                                 font=('Segoe UI', 8, 'italic'), foreground=test_color)
            test_label.grid(row=2, column=0, sticky='ew', pady=(0, 2))
            
            # Frame para acciones rápidas
            actions_frame = ttk.Frame(info_frame)
            actions_frame.grid(row=3, column=0, sticky='ew', pady=(2, 0))
            
            # Botones de acción rápida
            if status == 'active':
                ttk.Button(actions_frame, text="❌ Desactivar", 
                          command=lambda pn=plugin_name: self.quick_deactivate_plugin(pn),
                          style='Warning.TButton').pack(side=tk.LEFT, padx=(0, 5))
            else:
                ttk.Button(actions_frame, text="✅ Activar", 
                          command=lambda pn=plugin_name: self.quick_activate_plugin(pn),
                          style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
            
            if plugin.get('update_available', False):
                ttk.Button(actions_frame, text="🔄 Actualizar", 
                          command=lambda pn=plugin_name: self.quick_update_plugin(pn),
                          style='Info.TButton').pack(side=tk.LEFT, padx=(0, 5))
            
            # Botones para cambiar estado de testing
            ttk.Button(actions_frame, text="✅", 
                      command=lambda pn=plugin_name: self.update_plugin_test_status(pn, 'approved'),
                      style='Success.TButton').pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(actions_frame, text="⚠️", 
                      command=lambda pn=plugin_name: self.update_plugin_test_status(pn, 'warning'),
                      style='Warning.TButton').pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(actions_frame, text="❌", 
                      command=lambda pn=plugin_name: self.update_plugin_test_status(pn, 'failed'),
                      style='Danger.TButton').pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(actions_frame, text="❓", 
                      command=lambda pn=plugin_name: self.update_plugin_test_status(pn, 'untested'),
                      style='Secondary.TButton').pack(side=tk.LEFT, padx=(0, 5))
            
            # Agregar menú contextual al frame del plugin
            self.add_plugin_context_menu(plugin_frame, plugin_name)
            
            # Separador visual
            if i < len(filtered_plugins) - 1:
                separator = ttk.Separator(self.plugins_scrollable_frame, orient='horizontal')
                separator.pack(fill=tk.X, padx=10, pady=1)
        
        # Actualizar el scroll region
        self.plugins_scrollable_frame.update_idletasks()
        self.plugins_canvas.configure(scrollregion=self.plugins_canvas.bbox("all"))
        
        # Aplicar binding del mousewheel recursivamente a todos los widgets
        self._bind_mousewheel_recursive(self.plugins_scrollable_frame)
        
        # Actualizar contador
        self.update_selection_count()
    
    def get_filtered_plugins(self):
        """Obtener plugins filtrados según criterios de búsqueda"""
        if not hasattr(self, 'all_plugins_data'):
            return []
        if not self.all_plugins_data:
            return []
        
        filtered = self.all_plugins_data.copy()
        
        # Filtrar por texto de búsqueda (mejorado)
        search_text = self.search_var.get().lower().strip()
        if search_text and search_text != self.search_placeholder.lower():
            filtered = [p for p in filtered if 
                       search_text in p['name'].lower() or 
                       search_text in p.get('description', '').lower() or
                       search_text in p.get('author', '').lower() or
                       search_text in p.get('version', '').lower() or
                       search_text in p.get('directory', '').lower()]
        
        # Filtrar por estado
        status_filter = self.status_filter_var.get()
        if status_filter != "Todos":
            if status_filter == "Activos":
                filtered = [p for p in filtered if p.get('status') == 'active']
            elif status_filter == "Inactivos":
                filtered = [p for p in filtered if p.get('status') == 'inactive']
            elif status_filter == "Con Actualizaciones":
                filtered = [p for p in filtered if p.get('update_available', False)]
        
        return filtered
    
    def filter_plugins(self, event=None):
        """Filtrar plugins en tiempo real"""
        self.populate_plugins_tree()
    
    def on_plugin_checkbox_change(self, plugin_name):
        """Manejar cambio en checkbox de plugin"""
        var = self.plugin_vars.get(plugin_name)
        if not var:
            return
        
        if var.get():
            self.selected_plugins.add(plugin_name)
        else:
            self.selected_plugins.discard(plugin_name)
        
        self.update_selection_count()
        self.update_select_all_checkbox()
    
    def update_select_all_checkbox(self):
        """Actualizar estado del checkbox 'Seleccionar Todos'"""
        if not hasattr(self, 'plugin_vars') or not self.plugin_vars:
            self.select_all_var.set(False)
            return
        
        total_plugins = len(self.plugin_vars)
        selected_plugins = len(self.selected_plugins)
        
        if selected_plugins == 0:
            self.select_all_var.set(False)
        elif selected_plugins == total_plugins:
            self.select_all_var.set(True)
        else:
            # Estado intermedio - podríamos usar un checkbox tristate aquí
            self.select_all_var.set(False)
    
    def quick_activate_plugin(self, plugin_name):
        """Activar plugin rápidamente"""
        self.progress_var.set(f"Activando {plugin_name}...")
        self.progress_bar.start()
        
        def activate():
            try:
                result = self.run_wp_cli_command(f"plugin activate {plugin_name}")
                if result and "Success:" in result:
                    self.show_message("Éxito", f"Plugin '{plugin_name}' activado correctamente", "info")
                    # Refrescar la lista
                    self.scan_plugins()
                else:
                    self.show_message("Error", f"No se pudo activar el plugin '{plugin_name}'", "error")
            except Exception as e:
                self.show_message("Error", f"Error al activar plugin: {str(e)}", "error")
            finally:
                self.progress_bar.stop()
                self.progress_var.set("Listo")
        
        threading.Thread(target=activate, daemon=True).start()
    
    def quick_deactivate_plugin(self, plugin_name):
        """Desactivar plugin rápidamente"""
        self.progress_var.set(f"Desactivando {plugin_name}...")
        self.progress_bar.start()
        
        def deactivate():
            try:
                result = self.run_wp_cli_command(f"plugin deactivate {plugin_name}")
                if result and "Success:" in result:
                    self.show_message("Éxito", f"Plugin '{plugin_name}' desactivado correctamente", "info")
                    # Refrescar la lista
                    self.scan_plugins()
                else:
                    self.show_message("Error", f"No se pudo desactivar el plugin '{plugin_name}'", "error")
            except Exception as e:
                self.show_message("Error", f"Error al desactivar plugin: {str(e)}", "error")
            finally:
                self.progress_bar.stop()
                self.progress_var.set("Listo")
        
        threading.Thread(target=deactivate, daemon=True).start()
    
    def quick_update_plugin(self, plugin_name):
        """Actualizar plugin rápidamente"""
        self.progress_var.set(f"Actualizando {plugin_name}...")
        self.progress_bar.start()
        
        def update():
            try:
                result = self.run_wp_cli_command(f"plugin update {plugin_name}")
                if result and ("Success:" in result or "Updated" in result):
                    self.show_message("Éxito", f"Plugin '{plugin_name}' actualizado correctamente", "info")
                    # Refrescar la lista
                    self.scan_plugins()
                else:
                    self.show_message("Error", f"No se pudo actualizar el plugin '{plugin_name}'", "error")
            except Exception as e:
                self.show_message("Error", f"Error al actualizar plugin: {str(e)}", "error")
            finally:
                self.progress_bar.stop()
                self.progress_var.set("Listo")
        
        threading.Thread(target=update, daemon=True).start()
    
    def _on_canvas_configure(self, event):
        """Manejar redimensionamiento del canvas"""
        # Configurar el ancho del frame scrollable para que coincida con el canvas
        canvas_width = event.width
        if hasattr(self, 'plugins_scrollable_frame'):
            # Buscar la ventana del canvas y configurar su ancho
            for item in self.plugins_canvas.find_all():
                if self.plugins_canvas.type(item) == "window":
                    self.plugins_canvas.itemconfig(item, width=canvas_width)
                    break
    
    def _on_mousewheel(self, event):
        """Manejar scroll con rueda del mouse - mejorado"""
        try:
            # Verificar que el canvas existe y es scrollable
            if hasattr(self, 'plugins_canvas') and self.plugins_canvas.winfo_exists():
                # Calcular el scroll basado en el delta del evento
                delta = int(-1 * (event.delta / 120))
                self.plugins_canvas.yview_scroll(delta, "units")
        except Exception as e:
            # Silenciosamente manejar cualquier error de scroll
            pass
    
    def _bind_mousewheel_recursive(self, widget):
        """Hacer binding del mousewheel recursivamente a todos los widgets hijos"""
        try:
            widget.bind('<MouseWheel>', self._on_mousewheel)
            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child)
        except Exception:
            pass
    
    def _on_search_focus_in(self, event):
        """Manejar cuando el campo de búsqueda recibe el foco"""
        if self.search_entry.get() == self.search_placeholder:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(foreground='black')
    
    def _on_search_focus_out(self, event):
        """Manejar cuando el campo de búsqueda pierde el foco"""
        if not self.search_entry.get():
            self.search_entry.insert(0, self.search_placeholder)
            self.search_entry.config(foreground='gray')
    

    
    def on_plugin_double_click(self, event):
        """Manejar doble clic para mostrar información detallada"""
        item = self.plugins_tree.selection()[0] if self.plugins_tree.selection() else None
        if not item:
            return
        
        plugin_name = self.plugins_tree.item(item, 'values')[0]
        
        # Buscar información completa del plugin
        plugin_info = None
        for plugin in self.all_plugins_data:
            if plugin['name'] == plugin_name:
                plugin_info = plugin
                break
        
        if plugin_info:
            info_text = f"""
📦 Plugin: {plugin_info['name']}
🔄 Estado: {plugin_info.get('status', 'N/A')}
📊 Versión: {plugin_info.get('version', 'N/A')}
📝 Descripción: {plugin_info.get('description', 'N/A')}
📁 Directorio: {plugin_info.get('directory', 'N/A')}
            """
            messagebox.showinfo(f"Información de {plugin_name}", info_text.strip())
    
    def update_selection_count(self):
        """Actualizar contador de plugins seleccionados"""
        count = len(self.selected_plugins)
        total = len(self.all_plugins_data) if hasattr(self, 'all_plugins_data') else 0
        if hasattr(self, 'selected_count_var'):
            self.selected_count_var.set(f"{count} de {total} plugins seleccionados")

    def update_console_font(self):
        """Actualizar el tamaño de fuente de la consola global"""
        try:
            new_size = self.console_font_size.get()
            if hasattr(self, 'global_logs_text'):
                current_font = self.global_logs_text.cget("font")
                # Extraer familia de fuente actual
                if isinstance(current_font, tuple):
                    font_family = current_font[0]
                else:
                    font_family = "Consolas"
                
                # Aplicar nueva fuente
                new_font = (font_family, new_size)
                self.global_logs_text.configure(font=new_font)
                
                # Log del cambio
                self.global_log_message("INFO", f"Tamaño de fuente cambiado a {new_size}px")
        except Exception as e:
            print(f"Error al actualizar fuente: {e}")

    def get_test_status_badge(self, test_status):
        """Obtener la insignia visual para el estado de testing"""
        badges = {
            'approved': '✅',     # Plugin aprobado - funciona correctamente
            'warning': '⚠️',      # Plugin con advertencias - funciona pero con problemas menores
            'failed': '❌',       # Plugin falla - rompe la web o causa errores críticos
            'untested': '❓'      # Plugin no probado aún
        }
        return badges.get(test_status, '❓')
    
    def get_test_status_color(self, test_status):
        """Obtener el color para el estado de testing"""
        colors = {
            'approved': '#10b981',   # Verde
            'warning': '#f59e0b',    # Amarillo/Naranja
            'failed': '#ef4444',     # Rojo
            'untested': '#6b7280'    # Gris
        }
        return colors.get(test_status, '#6b7280')
    
    def update_plugin_test_status(self, plugin_name, test_status):
        """Actualizar el estado de testing de un plugin"""
        # Actualizar en all_plugins_data
        for plugin in self.all_plugins_data:
            if plugin['name'] == plugin_name:
                plugin['test_status'] = test_status
                break
        
        # Actualizar en plugins_data si existe
        if hasattr(self, 'plugins_data'):
            for plugin in self.plugins_data:
                if plugin['name'] == plugin_name:
                    plugin['test_status'] = test_status
                    break
        
        # Actualizar solo el elemento específico en lugar de redibujar todo
        self.update_single_plugin_display(plugin_name, test_status)
        
        # Log del cambio
        status_names = {
            'approved': 'Aprobado',
            'warning': 'Con advertencias', 
            'failed': 'Fallido',
            'untested': 'No probado'
        }
        self.global_log_message("INFO", f"Estado de testing actualizado para '{plugin_name}': {status_names.get(test_status, test_status)}")
        
        # Guardar estado automáticamente
        self.save_plugin_test_states()

    # === SISTEMA DE PERSISTENCIA DE BADGES ===
    
    def get_badges_file_path(self):
        """Obtener la ruta del archivo de estados de badges"""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugin_test_states.json')
    
    def get_resolved_plugins_file_path(self):
        """Obtener la ruta del archivo de plugins resueltos/desactivados"""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resolved_plugins.json')
    
    def save_resolved_plugin(self, plugin_name, reason='deactivated', error_details=None):
        """
        Marcar un plugin como resuelto/desactivado
        
        Args:
            plugin_name (str): Nombre del plugin
            reason (str): Razón de la resolución ('deactivated', 'fixed', 'updated')
            error_details (list): Detalles de los errores que causaron la desactivación
        """
        try:
            resolved_file = self.get_resolved_plugins_file_path()
            
            # Cargar datos existentes
            resolved_data = {}
            if os.path.exists(resolved_file):
                with open(resolved_file, 'r', encoding='utf-8') as f:
                    resolved_data = json.load(f)
            
            # Agregar o actualizar el plugin resuelto
            resolved_data[plugin_name] = {
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'error_details': error_details or [],
                'status': 'resolved'
            }
            
            # Guardar datos actualizados
            with open(resolved_file, 'w', encoding='utf-8') as f:
                json.dump(resolved_data, f, indent=2, ensure_ascii=False)
            
            self.global_log_message("INFO", f"Plugin '{plugin_name}' marcado como resuelto: {reason}")
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al guardar plugin resuelto: {str(e)}")
    
    def load_resolved_plugins(self):
        """
        Cargar la lista de plugins resueltos/desactivados
        
        Returns:
            dict: Diccionario con plugins resueltos
        """
        try:
            resolved_file = self.get_resolved_plugins_file_path()
            
            if not os.path.exists(resolved_file):
                return {}
            
            with open(resolved_file, 'r', encoding='utf-8') as f:
                resolved_data = json.load(f)
            
            return resolved_data
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al cargar plugins resueltos: {str(e)}")
            return {}
    
    def is_plugin_resolved(self, plugin_name):
        """
        Verificar si un plugin está marcado como resuelto
        
        Args:
            plugin_name (str): Nombre del plugin
            
        Returns:
            bool: True si el plugin está resuelto
        """
        resolved_plugins = self.load_resolved_plugins()
        return plugin_name in resolved_plugins
    
    def remove_resolved_plugin(self, plugin_name):
        """
        Remover un plugin de la lista de resueltos (por ejemplo, si se reactiva)
        
        Args:
            plugin_name (str): Nombre del plugin
        """
        try:
            resolved_file = self.get_resolved_plugins_file_path()
            
            if not os.path.exists(resolved_file):
                return
            
            with open(resolved_file, 'r', encoding='utf-8') as f:
                resolved_data = json.load(f)
            
            if plugin_name in resolved_data:
                del resolved_data[plugin_name]
                
                with open(resolved_file, 'w', encoding='utf-8') as f:
                    json.dump(resolved_data, f, indent=2, ensure_ascii=False)
                
                self.global_log_message("INFO", f"Plugin '{plugin_name}' removido de la lista de resueltos")
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al remover plugin resuelto: {str(e)}")
    
    def get_current_plugin_status(self, plugin_name):
        """
        Obtener el estado actual de un plugin (activo/inactivo)
        
        Args:
            plugin_name (str): Nombre del plugin
            
        Returns:
            str: 'active', 'inactive', o 'unknown'
        """
        # Evitar llamadas durante operaciones activas para prevenir bucles
        if getattr(self, 'plugins_operation_active', False):
            return 'unknown'
            
        try:
            if not self.wp_cli_manager:
                return 'unknown'
            
            # Obtener lista de plugins activos
            active_plugins = self.wp_cli_manager.list_plugins('active')
            if active_plugins:
                active_names = [p['name'] for p in active_plugins]
                if plugin_name in active_names:
                    return 'active'
            
            # Obtener lista de plugins inactivos
            inactive_plugins = self.wp_cli_manager.list_plugins('inactive')
            if inactive_plugins:
                inactive_names = [p['name'] for p in inactive_plugins]
                if plugin_name in inactive_names:
                    return 'inactive'
            
            return 'unknown'
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al verificar estado del plugin {plugin_name}: {str(e)}")
            return 'unknown'
    
    def save_plugin_test_states(self):
        """Guardar los estados de testing de plugins en un archivo JSON"""
        try:
            badges_file = self.get_badges_file_path()
            
            # Crear diccionario con estados actuales
            states = {}
            for plugin in self.all_plugins_data:
                plugin_name = plugin.get('name', '')
                test_status = plugin.get('test_status', 'untested')
                if plugin_name:
                    states[plugin_name] = {
                        'test_status': test_status,
                        'last_updated': datetime.now().isoformat(),
                        'version': plugin.get('version', ''),
                        'directory': plugin.get('directory', '')
                    }
            
            # Guardar en archivo JSON
            with open(badges_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=2, ensure_ascii=False)
                
            self.global_log_message("DEBUG", f"Estados de badges guardados: {len(states)} plugins")
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al guardar estados de badges: {str(e)}")
    
    def load_plugin_test_states(self):
        """Cargar los estados de testing guardados desde archivo JSON"""
        try:
            badges_file = self.get_badges_file_path()
            
            if not os.path.exists(badges_file):
                self.global_log_message("DEBUG", "No existe archivo de estados previos, iniciando con estados limpios")
                return {}
            
            with open(badges_file, 'r', encoding='utf-8') as f:
                states = json.load(f)
            
            self.global_log_message("INFO", f"Estados de badges cargados: {len(states)} plugins")
            return states
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al cargar estados de badges: {str(e)}")
            return {}
    
    def apply_saved_test_states(self):
        """Aplicar los estados guardados a los plugins actuales"""
        try:
            saved_states = self.load_plugin_test_states()
            
            if not saved_states:
                return
            
            applied_count = 0
            
            # Aplicar a all_plugins_data
            for plugin in self.all_plugins_data:
                plugin_name = plugin.get('name', '')
                if plugin_name in saved_states:
                    saved_state = saved_states[plugin_name]
                    plugin['test_status'] = saved_state.get('test_status', 'untested')
                    applied_count += 1
            
            # Aplicar a plugins_data si existe
            if hasattr(self, 'plugins_data'):
                for plugin in self.plugins_data:
                    plugin_name = plugin.get('name', '')
                    if plugin_name in saved_states:
                        saved_state = saved_states[plugin_name]
                        plugin['test_status'] = saved_state.get('test_status', 'untested')
            
            if applied_count > 0:
                self.global_log_message("SUCCESS", f"Estados de testing aplicados a {applied_count} plugins")
                # Refrescar la visualización sin aplicar estados nuevamente
                self.update_plugin_display(apply_states=False)
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al aplicar estados guardados: {str(e)}")

    def add_plugin_context_menu(self, widget, plugin_name):
        """Agregar menú contextual a un widget de plugin"""
        try:
            # Crear menú contextual
            context_menu = tk.Menu(self.root, tearoff=0)
            
            # Verificar si el plugin está resuelto
            is_resolved = self.is_plugin_resolved(plugin_name)
            
            if is_resolved:
                context_menu.add_command(
                    label="🔄 Quitar de resueltos",
                    command=lambda: self.remove_from_resolved(plugin_name)
                )
                context_menu.add_command(
                    label="📝 Ver detalles de resolución",
                    command=lambda: self.show_resolution_details(plugin_name)
                )
            else:
                context_menu.add_command(
                    label="✅ Marcar como resuelto",
                    command=lambda: self.mark_as_resolved_manual(plugin_name)
                )
            
            context_menu.add_separator()
            context_menu.add_command(
                label="📋 Ver todos los resueltos",
                command=self.show_all_resolved_plugins
            )
            
            # Función para mostrar el menú
            def show_context_menu(event):
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
            
            # Bind del clic derecho al widget y sus hijos
            widget.bind("<Button-3>", show_context_menu)
            for child in widget.winfo_children():
                child.bind("<Button-3>", show_context_menu)
                # Bind recursivo para widgets anidados
                for grandchild in child.winfo_children():
                    grandchild.bind("<Button-3>", show_context_menu)
                    
        except Exception as e:
            self.global_log_message("ERROR", f"Error al crear menú contextual para {plugin_name}: {str(e)}")

    def mark_as_resolved_manual(self, plugin_name):
        """Marcar un plugin como resuelto manualmente"""
        try:
            # Crear ventana de diálogo para obtener detalles
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Marcar como resuelto: {plugin_name}")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar la ventana
            dialog.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            # Frame principal
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            ttk.Label(main_frame, text=f"Marcar '{plugin_name}' como resuelto", 
                     font=('Segoe UI', 12, 'bold')).pack(pady=(0, 15))
            
            # Razón
            ttk.Label(main_frame, text="Razón de la resolución:").pack(anchor='w')
            reason_var = tk.StringVar(value="Resuelto manualmente por el usuario")
            reason_entry = ttk.Entry(main_frame, textvariable=reason_var, width=60)
            reason_entry.pack(fill=tk.X, pady=(5, 15))
            
            # Mensaje
            ttk.Label(main_frame, text="Mensaje adicional:").pack(anchor='w')
            message_text = tk.Text(main_frame, height=6, width=60)
            message_text.pack(fill=tk.BOTH, expand=True, pady=(5, 15))
            message_text.insert('1.0', f"El plugin '{plugin_name}' ha sido marcado como resuelto manualmente.\nLos errores futuros de este plugin en debug.log serán filtrados.")
            
            # Frame de botones
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def save_resolution():
                reason = reason_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()
                
                if not reason:
                    messagebox.showerror("Error", "Debe proporcionar una razón")
                    return
                
                # Guardar como resuelto
                self.save_resolved_plugin(plugin_name, reason, message)
                self.global_log_message("SUCCESS", f"Plugin '{plugin_name}' marcado como resuelto manualmente")
                
                # Actualizar la visualización
                self.update_plugin_display()
                
                dialog.destroy()
            
            def cancel():
                dialog.destroy()
            
            ttk.Button(button_frame, text="Cancelar", command=cancel).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Guardar", command=save_resolution).pack(side=tk.RIGHT)
            
            # Focus en el entry de razón
            reason_entry.focus()
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al marcar plugin como resuelto: {str(e)}")

    def remove_from_resolved(self, plugin_name):
        """Quitar un plugin de la lista de resueltos"""
        try:
            result = messagebox.askyesno(
                "Confirmar",
                f"¿Está seguro de que desea quitar '{plugin_name}' de la lista de plugins resueltos?\n\n"
                "Los errores de este plugin volverán a aparecer en el análisis de debug.log."
            )
            
            if result:
                resolved_file = os.path.join(self.get_data_dir(), 'resolved_plugins.json')
                
                if os.path.exists(resolved_file):
                    with open(resolved_file, 'r', encoding='utf-8') as f:
                        resolved_plugins = json.load(f)
                    
                    if plugin_name in resolved_plugins:
                        del resolved_plugins[plugin_name]
                        
                        with open(resolved_file, 'w', encoding='utf-8') as f:
                            json.dump(resolved_plugins, f, indent=2, ensure_ascii=False)
                        
                        self.global_log_message("SUCCESS", f"Plugin '{plugin_name}' quitado de la lista de resueltos")
                        
                        # Actualizar la visualización
                        self.update_plugin_display()
                    else:
                        self.global_log_message("WARNING", f"Plugin '{plugin_name}' no estaba en la lista de resueltos")
                else:
                    self.global_log_message("WARNING", "No existe archivo de plugins resueltos")
                    
        except Exception as e:
            self.global_log_message("ERROR", f"Error al quitar plugin de resueltos: {str(e)}")

    def show_resolution_details(self, plugin_name):
        """Mostrar detalles de la resolución de un plugin"""
        try:
            resolved_file = os.path.join(self.get_data_dir(), 'resolved_plugins.json')
            
            if not os.path.exists(resolved_file):
                messagebox.showinfo("Información", "No hay plugins resueltos registrados")
                return
            
            with open(resolved_file, 'r', encoding='utf-8') as f:
                resolved_plugins = json.load(f)
            
            if plugin_name not in resolved_plugins:
                messagebox.showinfo("Información", f"El plugin '{plugin_name}' no está en la lista de resueltos")
                return
            
            plugin_data = resolved_plugins[plugin_name]
            
            # Crear ventana de detalles
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Detalles de resolución: {plugin_name}")
            details_window.geometry("600x400")
            details_window.transient(self.root)
            
            # Centrar la ventana
            details_window.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            # Frame principal con scroll
            main_frame = ttk.Frame(details_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            ttk.Label(main_frame, text=f"Detalles de resolución: {plugin_name}", 
                     font=('Segoe UI', 14, 'bold')).pack(pady=(0, 20))
            
            # Información
            info_text = tk.Text(main_frame, wrap=tk.WORD, height=15)
            info_text.pack(fill=tk.BOTH, expand=True)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(info_text)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            info_text.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=info_text.yview)
            
            # Contenido
            content = f"""Plugin: {plugin_name}
Fecha de resolución: {plugin_data.get('timestamp', 'No disponible')}
Razón: {plugin_data.get('reason', 'No especificada')}

Mensaje:
{plugin_data.get('message', 'Sin mensaje adicional')}

Estado: ✅ Resuelto - Los errores de este plugin son filtrados en el análisis de debug.log
"""
            
            info_text.insert('1.0', content)
            info_text.config(state=tk.DISABLED)
            
            # Botón cerrar
            ttk.Button(main_frame, text="Cerrar", 
                      command=details_window.destroy).pack(pady=(10, 0))
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al mostrar detalles de resolución: {str(e)}")

    def show_all_resolved_plugins(self):
        """Mostrar todos los plugins resueltos"""
        try:
            resolved_file = os.path.join(self.get_data_dir(), 'resolved_plugins.json')
            
            if not os.path.exists(resolved_file):
                messagebox.showinfo("Información", "No hay plugins resueltos registrados")
                return
            
            with open(resolved_file, 'r', encoding='utf-8') as f:
                resolved_plugins = json.load(f)
            
            if not resolved_plugins:
                messagebox.showinfo("Información", "No hay plugins resueltos registrados")
                return
            
            # Crear ventana de lista
            list_window = tk.Toplevel(self.root)
            list_window.title("Plugins Resueltos")
            list_window.geometry("800x500")
            list_window.transient(self.root)
            
            # Centrar la ventana
            list_window.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            # Frame principal
            main_frame = ttk.Frame(list_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            ttk.Label(main_frame, text=f"Plugins Resueltos ({len(resolved_plugins)})", 
                     font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))
            
            # Frame para la lista
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Treeview para mostrar los plugins
            columns = ('plugin', 'fecha', 'razon')
            tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
            
            # Configurar columnas
            tree.heading('plugin', text='Plugin')
            tree.heading('fecha', text='Fecha de Resolución')
            tree.heading('razon', text='Razón')
            
            tree.column('plugin', width=250)
            tree.column('fecha', width=150)
            tree.column('razon', width=300)
            
            # Scrollbars
            v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
            h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=tree.xview)
            tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack del treeview y scrollbars
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Llenar con datos
            for plugin_name, data in resolved_plugins.items():
                timestamp = data.get('timestamp', 'No disponible')
                reason = data.get('reason', 'No especificada')
                tree.insert('', tk.END, values=(plugin_name, timestamp, reason))
            
            # Frame de botones
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(15, 0))
            
            def remove_selected():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("Advertencia", "Seleccione un plugin para quitar")
                    return
                
                item = tree.item(selection[0])
                plugin_name = item['values'][0]
                
                result = messagebox.askyesno(
                    "Confirmar",
                    f"¿Está seguro de que desea quitar '{plugin_name}' de la lista de resueltos?"
                )
                
                if result:
                    self.remove_from_resolved(plugin_name)
                    tree.delete(selection[0])
            
            def show_details():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("Advertencia", "Seleccione un plugin para ver detalles")
                    return
                
                item = tree.item(selection[0])
                plugin_name = item['values'][0]
                self.show_resolution_details(plugin_name)
            
            ttk.Button(button_frame, text="Cerrar", 
                      command=list_window.destroy).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Quitar seleccionado", 
                      command=remove_selected).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Ver detalles", 
                      command=show_details).pack(side=tk.RIGHT, padx=(10, 0))
            
        except Exception as e:
            self.global_log_message("ERROR", f"Error al mostrar plugins resueltos: {str(e)}")



    def on_panel_resize(self, event=None):
        """Manejar el redimensionamiento del panel para texto adaptativo en pestañas"""
        # Permitir ejecución sin evento (llamada inicial) o con evento del panel correcto
        if event is None or (event and event.widget == self.left_panel):
            try:
                # Obtener el ancho actual del panel
                panel_width = self.left_panel.winfo_width()
                
                # Determinar qué conjunto de textos usar basado en el ancho
                if panel_width > 600:
                    texts = self.tab_texts['full']
                elif panel_width > 400:
                    texts = self.tab_texts['medium']
                else:
                    texts = self.tab_texts['short']
                
                # Actualizar los textos de las pestañas
                for i, text in enumerate(texts):
                    if i < self.notebook.index('end'):
                        self.notebook.tab(i, text=text)
                        
            except (tk.TclError, AttributeError):
                # Ignorar errores durante la inicialización
                pass

    def on_closing(self):
        """Manejar el cierre de la aplicación"""
        # Restaurar stdout si está siendo capturado
        if self.python_capture_active and self.python_capture:
            self.python_capture.stop_capture()
            print("Captura de Python restaurada al cerrar la aplicación")
        
        # Cerrar conexión SSH si existe
        if self.ssh_client:
            self.ssh_client.close()
        
        # Cerrar la aplicación
        self.root.destroy()

    # ==========================================
    # NUEVOS MÉTODOS PARA GESTIÓN DE MÚLTIPLES LOGS
    # ==========================================
    
    def on_log_type_change(self):
        """Manejar cambio de tipo de log seleccionado"""
        log_type = self.log_type_var.get()
        self.log_info_var.set(f"Tipo de log seleccionado: {log_type.upper()}")
        
        # Limpiar el área de texto
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.insert(tk.END, f"Seleccionado: {log_type.upper()}\n")
        self.logs_text.insert(tk.END, "Haga clic en 'Leer Log' para cargar el contenido.\n")
    
    def detect_available_logs(self):
        """Detectar logs disponibles en el servidor"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        if not self.log_manager:
            messagebox.showerror("Error", "LogManager no está inicializado")
            return
        
        try:
            self.status_var.set("Detectando logs disponibles...")
            
            # Detectar logs usando LogManager
            available_logs = self.log_manager.detect_log_files(self.wp_path_var.get())
            self.available_logs = available_logs
            
            # Crear mensaje informativo
            info_text = "Logs detectados:\n"
            for log_type, logs in available_logs.items():
                if logs:
                    info_text += f"• {log_type.upper()}: {len(logs)} archivo(s)\n"
                    for log_path in logs[:3]:  # Mostrar máximo 3 rutas
                        info_text += f"  - {log_path}\n"
                    if len(logs) > 3:
                        info_text += f"  ... y {len(logs) - 3} más\n"
                else:
                    info_text += f"• {log_type.upper()}: No encontrado\n"
            
            self.log_info_var.set(info_text)
            self.status_var.set("Detección de logs completada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al detectar logs: {str(e)}")
            self.status_var.set("Error en detección de logs")
    
    def read_selected_log(self):
        """Leer el log del tipo seleccionado"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        if not self.log_manager:
            messagebox.showerror("Error", "LogManager no está inicializado")
            return
        
        log_type = self.log_type_var.get()
        
        try:
            self.status_var.set(f"Leyendo {log_type} log...")
            
            # Obtener el tipo de log enum
            from log_manager import LogType
            log_type_enum = getattr(LogType, log_type.upper())
            
            # Primero detectar logs disponibles
            wp_path = self.wp_path_var.get()
            available_logs = self.log_manager.detect_log_files(wp_path)
            
            # Obtener archivos de log para el tipo seleccionado
            log_files = available_logs.get(log_type_enum, [])
            
            if not log_files:
                self.logs_text.delete(1.0, tk.END)
                self.logs_text.insert(tk.END, f"No se encontraron archivos de {log_type} log.\n")
                self.status_var.set(f"No se encontraron archivos de {log_type} log")
                return
            
            # Leer el primer archivo de log encontrado
            log_path = log_files[0]
            log_entries = self.log_manager.read_log(log_path, log_type_enum)
            self.current_log_entries = log_entries
            
            # Mostrar en el área de texto
            self.logs_text.delete(1.0, tk.END)
            
            if not log_entries:
                self.logs_text.insert(tk.END, f"No se encontraron entradas en {log_type} log.\n")
                self.logs_text.insert(tk.END, "Esto puede significar:\n")
                self.logs_text.insert(tk.END, "• El archivo no existe\n")
                self.logs_text.insert(tk.END, "• El archivo está vacío\n")
                self.logs_text.insert(tk.END, "• No hay permisos de lectura\n")
            else:
                # Mostrar entradas formateadas
                for entry in log_entries[-100:]:  # Últimas 100 entradas
                    formatted_entry = self.log_manager.format_log_entry(entry)
                    
                    # Insertar con colores según el nivel
                    if entry.level == 'ERROR' or entry.level == 'FATAL':
                        self.logs_text.insert(tk.END, formatted_entry, "ERROR")
                    elif entry.level == 'WARNING':
                        self.logs_text.insert(tk.END, formatted_entry, "WARNING")
                    elif entry.level == 'INFO':
                        self.logs_text.insert(tk.END, formatted_entry, "INFO")
                    else:
                        self.logs_text.insert(tk.END, formatted_entry)
                    
                    self.logs_text.insert(tk.END, "\n")
                
                # Scroll al final
                self.logs_text.see(tk.END)
            
            self.status_var.set(f"{log_type} log cargado - {len(log_entries)} entradas")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer {log_type} log: {str(e)}")
            self.status_var.set("Error al leer log")
    
    def analyze_current_log(self):
        """Analizar el log actualmente cargado"""
        if not self.current_log_entries:
            messagebox.showwarning("Advertencia", "Primero debe cargar un log")
            return
        
        if not self.log_manager:
            messagebox.showerror("Error", "LogManager no está inicializado")
            return
        
        try:
            self.status_var.set("Analizando log...")
            
            # Analizar usando LogManager
            analysis = self.log_manager.analyze_logs(self.current_log_entries)
            
            # Mostrar análisis en una ventana separada
            self.show_log_analysis(analysis)
            
            self.status_var.set("Análisis completado")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al analizar log: {str(e)}")
            self.status_var.set("Error en análisis")
    
    def show_log_analysis(self, analysis):
        """Mostrar análisis de logs en una ventana separada"""
        dialog = tk.Toplevel(self.root)
        dialog.title("📊 Análisis de Logs")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Crear área de texto con scroll
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        analysis_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Consolas', 10))
        analysis_text.pack(fill=tk.BOTH, expand=True)
        
        # Formatear análisis
        content = f"📊 ANÁLISIS DE LOGS\n"
        content += f"{'='*50}\n\n"
        content += f"📈 RESUMEN GENERAL\n"
        content += f"Total de entradas: {analysis.total_entries}\n"
        content += f"Errores: {analysis.error_count}\n"
        content += f"Advertencias: {analysis.warning_count}\n"
        content += f"Información: {analysis.info_count}\n"
        content += f"Período: {analysis.time_range}\n\n"
        
        if analysis.top_errors:
            content += f"🚨 ERRORES MÁS FRECUENTES\n"
            for i, (error, count) in enumerate(analysis.top_errors[:10], 1):
                content += f"{i}. {error} ({count} veces)\n"
            content += "\n"
        
        if analysis.affected_plugins:
            content += f"🔌 PLUGINS AFECTADOS\n"
            for plugin in analysis.affected_plugins[:10]:
                content += f"• {plugin}\n"
            content += "\n"
        
        if analysis.recommendations:
            content += f"💡 RECOMENDACIONES\n"
            for rec in analysis.recommendations:
                content += f"• {rec}\n"
            content += "\n"
        
        content += f"📋 RESUMEN\n"
        content += analysis.summary
        
        analysis_text.insert(tk.END, content)
        analysis_text.config(state=tk.DISABLED)
        
        # Botón cerrar
        ttk.Button(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)
    
    def clear_selected_log(self):
        """Limpiar el log del tipo seleccionado"""
        if not self.is_connected:
            messagebox.showerror("Error", "Debe conectarse al servidor primero")
            return
        
        log_type = self.log_type_var.get()
        
        if not messagebox.askyesno("Confirmar", 
                                  f"¿Está seguro de que desea limpiar el {log_type} log?\n"
                                  f"Esta acción no se puede deshacer."):
            return
        
        try:
            self.status_var.set(f"Limpiando {log_type} log...")
            
            # Para debug log, usar el método existente
            if log_type == "debug":
                self.clear_debug_log()
                return
            
            # Para otros logs, implementar limpieza básica
            if log_type == "error":
                # Limpiar error.log del servidor
                cmd = f"cd {self.wp_path_var.get()} && echo '' > ../logs/error.log 2>/dev/null || echo '' > error.log 2>/dev/null || echo 'Log no encontrado'"
            elif log_type == "access":
                # Limpiar access.log
                cmd = f"cd {self.wp_path_var.get()} && echo '' > ../logs/access.log 2>/dev/null || echo 'Log no encontrado'"
            else:
                messagebox.showwarning("Advertencia", f"Limpieza de {log_type} log no implementada")
                return
            
            result = self.execute_ssh_command(cmd)
            
            if "no encontrado" not in result.lower():
                self.logs_text.delete(1.0, tk.END)
                self.logs_text.insert(tk.END, f"{log_type} log limpiado exitosamente.\n")
                self.current_log_entries = []
                messagebox.showinfo("Éxito", f"{log_type} log limpiado correctamente")
            else:
                messagebox.showwarning("Advertencia", f"No se pudo encontrar o limpiar el {log_type} log")
            
            self.status_var.set(f"{log_type} log limpiado")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al limpiar {log_type} log: {str(e)}")
            self.status_var.set("Error al limpiar log")

    def run(self):
        """Ejecutar la aplicación"""
        self.root.mainloop()

if __name__ == "__main__":
    app = WordPressPluginManager()
    app.run()