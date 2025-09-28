"""
WordPress Log Manager
Gestiona la lectura e interpretación de diferentes tipos de logs de WordPress
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class LogType(Enum):
    """Tipos de logs soportados"""
    DEBUG = "debug"
    ERROR = "error" 
    ACCESS = "access"
    CACHE = "cache"
    PLUGIN = "plugin"

@dataclass
class LogEntry:
    """Entrada de log estructurada"""
    timestamp: Optional[datetime]
    level: str
    message: str
    file: Optional[str]
    line: Optional[int]
    raw_line: str
    log_type: LogType

@dataclass
class LogAnalysis:
    """Resultado del análisis de logs"""
    total_entries: int
    error_count: int
    warning_count: int
    fatal_count: int
    info_count: int
    time_range: str
    recent_errors: List[LogEntry]
    most_common_errors: List[tuple]
    top_errors: List[tuple]
    affected_plugins: List[str]
    recommendations: List[str]
    file_with_most_errors: Optional[str]
    summary: str

class LogManager:
    """Gestor de logs de WordPress"""
    
    def __init__(self, ssh_executor=None):
        self.ssh_executor = ssh_executor
        self.log_patterns = self._init_patterns()
        
    def _init_patterns(self) -> Dict:
        """Inicializar patrones de regex para diferentes tipos de logs"""
        return {
            LogType.DEBUG: {
                # [DD-MMM-YYYY HH:MM:SS UTC] PHP Fatal error: ...
                'wordpress': re.compile(r'\[(\d{2}-\w{3}-\d{4} \d{2}:\d{2}:\d{2} \w+)\] PHP (Fatal error|Warning|Notice|Parse error): (.+) in (.+) on line (\d+)'),
                # [timestamp] WordPress database error ...
                'db_error': re.compile(r'\[([^\]]+)\] WordPress database error (.+)'),
                # [timestamp] PHP message: ...
                'php_message': re.compile(r'\[([^\]]+)\] PHP (.+): (.+)'),
            },
            LogType.ERROR: {
                # [timestamp] [error] [client IP] message
                'apache': re.compile(r'\[([^\]]+)\] \[([^\]]+)\] \[client ([^\]]+)\] (.+)'),
                # timestamp [error] message
                'nginx': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[([^\]]+)\] (.+)'),
                # Generic error format
                'generic': re.compile(r'\[([^\]]+)\] (.+)'),
            },
            LogType.ACCESS: {
                # Common Log Format: IP - - [timestamp] "method path protocol" status size
                'common': re.compile(r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\S+)'),
                # Combined Log Format (includes user agent and referer)
                'combined': re.compile(r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\S+) "([^"]*)" "([^"]*)"'),
            },
            LogType.CACHE: {
                # Cache performance logs
                'performance': re.compile(r'\[([^\]]+)\] Cache (.+): (.+)'),
                # Kinsta cache logs
                'kinsta': re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+)'),
            }
        }
    
    def detect_log_files(self, wp_path: str) -> Dict[LogType, List[str]]:
        """Detectar archivos de log disponibles"""
        if not self.ssh_executor:
            return {}
            
        log_files = {log_type: [] for log_type in LogType}
        
        try:
            # Buscar debug.log
            debug_paths = [
                f"{wp_path}/wp-content/debug.log",
                f"{wp_path}/wp-content/uploads/debug.log"
            ]
            
            for path in debug_paths:
                if self._file_exists(path):
                    log_files[LogType.DEBUG].append(path)
            
            # Buscar error.log (servidor)
            error_paths = [
                f"{wp_path}/logs/error.log",
                f"{wp_path}/../logs/error.log",
                "/var/log/apache2/error.log",
                "/var/log/nginx/error.log",
                f"{wp_path}/error.log"
            ]
            
            for path in error_paths:
                if self._file_exists(path):
                    log_files[LogType.ERROR].append(path)
            
            # Buscar access.log
            access_paths = [
                f"{wp_path}/logs/access.log",
                f"{wp_path}/../logs/access.log",
                "/var/log/apache2/access.log",
                "/var/log/nginx/access.log"
            ]
            
            for path in access_paths:
                if self._file_exists(path):
                    log_files[LogType.ACCESS].append(path)
            
            # Buscar logs de cache
            cache_paths = [
                f"{wp_path}/logs/kinsta-cache-perf.log",
                f"{wp_path}/../logs/kinsta-cache-perf.log",
                f"{wp_path}/wp-content/cache/cache.log"
            ]
            
            for path in cache_paths:
                if self._file_exists(path):
                    log_files[LogType.CACHE].append(path)
            
            # Buscar logs de plugins específicos
            plugin_log_cmd = f"find {wp_path}/wp-content -name '*.log' -type f 2>/dev/null | head -10"
            plugin_logs = self.ssh_executor(plugin_log_cmd).strip()
            
            if plugin_logs:
                for log_path in plugin_logs.split('\n'):
                    if log_path and 'debug.log' not in log_path:
                        log_files[LogType.PLUGIN].append(log_path.strip())
            
        except Exception as e:
            print(f"Error detectando logs: {e}")
        
        return log_files
    
    def _file_exists(self, path: str) -> bool:
        """Verificar si un archivo existe"""
        try:
            result = self.ssh_executor(f"test -f {path} && echo 'exists' || echo 'not_exists'")
            return result.strip() == 'exists'
        except:
            return False
    
    def read_log(self, log_path: str, log_type: LogType, lines: int = 100) -> List[LogEntry]:
        """Leer y parsear un archivo de log"""
        if not self.ssh_executor:
            return []
        
        try:
            # Leer últimas N líneas del log
            command = f"tail -{lines} {log_path} 2>/dev/null || echo 'Error reading log'"
            content = self.ssh_executor(command)
            
            if content == 'Error reading log' or not content.strip():
                return []
            
            return self._parse_log_content(content, log_type)
            
        except Exception as e:
            print(f"Error leyendo log {log_path}: {e}")
            return []
    
    def _parse_log_content(self, content: str, log_type: LogType) -> List[LogEntry]:
        """Parsear contenido de log según su tipo"""
        entries = []
        lines = content.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            entry = self._parse_log_line(line, log_type)
            if entry:
                entries.append(entry)
        
        return entries
    
    def _parse_log_line(self, line: str, log_type: LogType) -> Optional[LogEntry]:
        """Parsear una línea de log específica"""
        patterns = self.log_patterns.get(log_type, {})
        
        for pattern_name, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                return self._create_log_entry(match, line, log_type, pattern_name)
        
        # Si no coincide con ningún patrón, crear entrada genérica
        return LogEntry(
            timestamp=None,
            level="UNKNOWN",
            message=line,
            file=None,
            line=None,
            raw_line=line,
            log_type=log_type
        )
    
    def _create_log_entry(self, match, raw_line: str, log_type: LogType, pattern_name: str) -> LogEntry:
        """Crear entrada de log desde match de regex"""
        groups = match.groups()
        
        if log_type == LogType.DEBUG:
            if pattern_name == 'wordpress':
                return LogEntry(
                    timestamp=self._parse_timestamp(groups[0]),
                    level=groups[1],
                    message=groups[2],
                    file=groups[3],
                    line=int(groups[4]) if groups[4].isdigit() else None,
                    raw_line=raw_line,
                    log_type=log_type
                )
            elif pattern_name == 'db_error':
                return LogEntry(
                    timestamp=self._parse_timestamp(groups[0]),
                    level="DATABASE ERROR",
                    message=groups[1],
                    file=None,
                    line=None,
                    raw_line=raw_line,
                    log_type=log_type
                )
        
        elif log_type == LogType.ERROR:
            if pattern_name == 'apache':
                return LogEntry(
                    timestamp=self._parse_timestamp(groups[0]),
                    level=groups[1],
                    message=groups[3],
                    file=None,
                    line=None,
                    raw_line=raw_line,
                    log_type=log_type
                )
            elif pattern_name == 'nginx':
                return LogEntry(
                    timestamp=self._parse_timestamp(groups[0]),
                    level=groups[1],
                    message=groups[2],
                    file=None,
                    line=None,
                    raw_line=raw_line,
                    log_type=log_type
                )
        
        elif log_type == LogType.ACCESS:
            if pattern_name in ['common', 'combined']:
                return LogEntry(
                    timestamp=self._parse_timestamp(groups[1]),
                    level="ACCESS",
                    message=f"{groups[2]} {groups[3]} - Status: {groups[5]}",
                    file=None,
                    line=None,
                    raw_line=raw_line,
                    log_type=log_type
                )
        
        # Entrada genérica para patrones no específicos
        return LogEntry(
            timestamp=self._parse_timestamp(groups[0]) if groups else None,
            level="INFO",
            message=groups[-1] if groups else raw_line,
            file=None,
            line=None,
            raw_line=raw_line,
            log_type=log_type
        )
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parsear timestamp de diferentes formatos"""
        formats = [
            "%d-%b-%Y %H:%M:%S %Z",  # WordPress: 26-Jan-2024 10:30:45 UTC
            "%Y/%m/%d %H:%M:%S",     # Nginx: 2024/01/26 10:30:45
            "%d/%b/%Y:%H:%M:%S %z",  # Apache: 26/Jan/2024:10:30:45 +0000
            "%Y-%m-%d %H:%M:%S",     # Generic: 2024-01-26 10:30:45
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def analyze_logs(self, entries: List[LogEntry]) -> LogAnalysis:
        """Analizar entradas de log y generar resumen"""
        if not entries:
            return LogAnalysis(
                total_entries=0,
                error_count=0,
                warning_count=0,
                fatal_count=0,
                info_count=0,
                time_range="Sin datos",
                recent_errors=[],
                most_common_errors=[],
                top_errors=[],
                affected_plugins=[],
                recommendations=[],
                file_with_most_errors=None,
                summary="No hay entradas de log para analizar."
            )
        
        # Contadores
        error_count = 0
        warning_count = 0
        fatal_count = 0
        info_count = 0
        
        # Errores recientes (últimos 10)
        recent_errors = []
        
        # Conteo de errores por mensaje
        error_messages = {}
        
        # Conteo de errores por archivo
        file_errors = {}
        
        # Plugins afectados
        affected_plugins = set()
        
        # Timestamps para rango de tiempo
        timestamps = []
        
        for entry in entries:
            level = entry.level.lower()
            
            # Agregar timestamp si existe
            if entry.timestamp:
                timestamps.append(entry.timestamp)
            
            if 'fatal' in level or 'error' in level:
                error_count += 1
                recent_errors.append(entry)
                
                # Contar mensaje de error
                error_key = entry.message[:100]  # Primeros 100 caracteres
                error_messages[error_key] = error_messages.get(error_key, 0) + 1
                
                # Contar por archivo
                if entry.file:
                    file_errors[entry.file] = file_errors.get(entry.file, 0) + 1
                
                # Detectar plugins afectados
                if 'plugin' in entry.message.lower() or '/plugins/' in entry.message:
                    # Extraer nombre del plugin del mensaje o ruta
                    import re
                    plugin_match = re.search(r'/plugins/([^/]+)/', entry.message)
                    if plugin_match:
                        affected_plugins.add(plugin_match.group(1))
                
                if 'fatal' in level:
                    fatal_count += 1
            
            elif 'warning' in level or 'notice' in level:
                warning_count += 1
            
            elif 'info' in level:
                info_count += 1
        
        # Errores más comunes
        most_common_errors = sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:5]
        top_errors = most_common_errors  # Alias para compatibilidad
        
        # Archivo con más errores
        file_with_most_errors = max(file_errors.items(), key=lambda x: x[1])[0] if file_errors else None
        
        # Errores recientes (últimos 10)
        recent_errors = recent_errors[-10:]
        
        # Calcular rango de tiempo
        time_range = "Sin timestamps"
        if timestamps:
            timestamps.sort()
            start_time = timestamps[0].strftime("%Y-%m-%d %H:%M:%S")
            end_time = timestamps[-1].strftime("%Y-%m-%d %H:%M:%S")
            if start_time == end_time:
                time_range = start_time
            else:
                time_range = f"{start_time} - {end_time}"
        
        # Generar recomendaciones
        recommendations = self._generate_recommendations(error_count, warning_count, fatal_count, affected_plugins)
        
        # Generar resumen
        summary = self._generate_summary(len(entries), error_count, warning_count, fatal_count)
        
        return LogAnalysis(
            total_entries=len(entries),
            error_count=error_count,
            warning_count=warning_count,
            fatal_count=fatal_count,
            info_count=info_count,
            time_range=time_range,
            recent_errors=recent_errors,
            most_common_errors=most_common_errors,
            top_errors=top_errors,
            affected_plugins=list(affected_plugins),
            recommendations=recommendations,
            file_with_most_errors=file_with_most_errors,
            summary=summary
        )
    
    def _generate_summary(self, total: int, errors: int, warnings: int, fatals: int) -> str:
        """Generar resumen del análisis"""
        if total == 0:
            return "No hay entradas de log."
        
        summary = f"Análisis de {total} entradas de log:\n"
        
        if fatals > 0:
            summary += f"🔴 {fatals} errores fatales encontrados\n"
        
        if errors > 0:
            summary += f"🟠 {errors} errores totales\n"
        
        if warnings > 0:
            summary += f"🟡 {warnings} advertencias\n"
        
        if errors == 0 and warnings == 0:
            summary += "✅ No se encontraron errores o advertencias"
        
        return summary
    
    def _generate_recommendations(self, errors: int, warnings: int, fatals: int, affected_plugins: set) -> List[str]:
        """Generar recomendaciones basadas en el análisis"""
        recommendations = []
        
        if fatals > 0:
            recommendations.append("🚨 Errores fatales detectados - Revisar inmediatamente")
            recommendations.append("Considerar desactivar plugins problemáticos temporalmente")
        
        if errors > 10:
            recommendations.append("Alto número de errores - Revisar configuración del sitio")
            recommendations.append("Verificar compatibilidad entre plugins activos")
        
        if warnings > 20:
            recommendations.append("Muchas advertencias - Considerar actualizar plugins y temas")
        
        if affected_plugins:
            recommendations.append(f"Plugins con problemas detectados: {', '.join(list(affected_plugins)[:3])}")
            recommendations.append("Revisar documentación de plugins problemáticos")
        
        if errors == 0 and warnings == 0:
            recommendations.append("✅ El sitio parece estar funcionando correctamente")
        
        if not recommendations:
            recommendations.append("Continuar monitoreando los logs regularmente")
        
        return recommendations
    
    def format_log_entry(self, entry: LogEntry) -> str:
        """Formatear entrada de log para mostrar"""
        timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "Sin timestamp"
        
        formatted = f"[{timestamp}] {entry.level}: {entry.message}"
        
        if entry.file and entry.line:
            formatted += f"\n  📁 Archivo: {entry.file}:{entry.line}"
        elif entry.file:
            formatted += f"\n  📁 Archivo: {entry.file}"
        
        return formatted