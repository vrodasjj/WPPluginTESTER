#!/usr/bin/env python3
"""
WP-CLI Manager
Clase especializada para gestionar WordPress usando WP-CLI de forma eficiente
"""

import json
import time
import requests
from typing import List, Dict, Optional, Tuple


class WPCLIManager:
    """Gestor de operaciones WP-CLI para WordPress"""
    
    def __init__(self, ssh_executor, wp_path: str):
        """
        Inicializar el gestor WP-CLI
        
        Args:
            ssh_executor: Función para ejecutar comandos SSH
            wp_path: Ruta del directorio WordPress
        """
        self.execute_ssh_command = ssh_executor
        self.wp_path = wp_path
        self.wp_cli_available = None
        
    def check_wp_cli_availability(self) -> bool:
        """
        Verificar si WP-CLI está disponible y funcionando
        
        Returns:
            bool: True si WP-CLI está disponible y funciona correctamente
        """
        print("DEBUG: Iniciando verificación de WP-CLI...")
        
        try:
            # Verificar conexión SSH
            if not hasattr(self, 'execute_ssh_command') or not self.execute_ssh_command:
                print("DEBUG: No hay método execute_ssh_command disponible")
                return False
            
            # Verificar si WP-CLI está instalado
            print("DEBUG: Verificando si WP-CLI está instalado...")
            which_result = self.execute_ssh_command("which wp").strip()
            print(f"DEBUG: Resultado de 'which wp': '{which_result}'")
            
            if not which_result or 'not found' in which_result.lower():
                print("DEBUG: WP-CLI no encontrado en el sistema")
                return False
            
            # Verificar si WP-CLI funciona correctamente
            try:
                print(f"DEBUG: Verificando funcionalidad de WP-CLI en ruta: {self.wp_path}")
                version_cmd = f"cd {self.wp_path} && wp core version"
                print(f"DEBUG: Ejecutando comando: {version_cmd}")
                version_result = self.execute_ssh_command(version_cmd).strip()
                print(f"DEBUG: Resultado de 'wp core version': '{version_result}'")
                
                if version_result and not any(error in version_result.lower() for error in ['error', 'warning', 'not found', 'permission denied']):
                    print("DEBUG: WP-CLI funciona correctamente")
                    self.wp_cli_available = True
                    return True
                else:
                    print(f"DEBUG: WP-CLI no funciona correctamente. Errores detectados en: {version_result}")
                    self.wp_cli_available = False
                    return False
            except Exception as e:
                print(f"DEBUG: Excepción al verificar funcionalidad de WP-CLI: {e}")
                self.wp_cli_available = False
                return False
                
        except Exception as e:
            print(f"DEBUG: Excepción general en check_wp_cli_availability: {e}")
            self.wp_cli_available = False
            return False
    
    def get_wordpress_info(self) -> Dict[str, str]:
        """
        Obtener información básica de WordPress
        
        Returns:
            Dict con información de WordPress
        """
        if not self.check_wp_cli_availability():
            return {}
            
        try:
            info = {}
            
            # Versión de WordPress
            version_cmd = f"cd {self.wp_path} && wp core version"
            info['wp_version'] = self.execute_ssh_command(version_cmd).strip()
            
            # URL del sitio
            url_cmd = f"cd {self.wp_path} && wp option get siteurl"
            info['site_url'] = self.execute_ssh_command(url_cmd).strip()
            
            # Título del sitio
            title_cmd = f"cd {self.wp_path} && wp option get blogname"
            info['site_title'] = self.execute_ssh_command(title_cmd).strip()
            
            # Estado de debug
            debug_cmd = f"cd {self.wp_path} && wp config get WP_DEBUG"
            info['debug_enabled'] = self.execute_ssh_command(debug_cmd).strip()
            
            return info
            
        except Exception as e:
            return {'error': str(e)}
    
    def list_plugins(self, status: str = 'all') -> List[Dict[str, str]]:
        """
        Listar plugins usando WP-CLI con timeout y mejor manejo de errores
        
        Args:
            status: 'all', 'active', 'inactive', 'must-use'
            
        Returns:
            Lista de diccionarios con información de plugins
        """
        print(f"DEBUG: list_plugins llamado con status='{status}'")
        
        if not self.check_wp_cli_availability():
            print("DEBUG: WP-CLI no disponible en list_plugins")
            return []
            
        try:
            # Comando WP-CLI para listar plugins
            if status == 'all':
                cmd = f"cd {self.wp_path} && wp plugin list --format=json"
            else:
                cmd = f"cd {self.wp_path} && wp plugin list --status={status} --format=json"
                
            print(f"DEBUG: Ejecutando comando: {cmd}")
            
            # Usar timeout específico para listado de plugins (puede tardar en sitios grandes)
            try:
                result = self.execute_ssh_command(cmd, timeout=45)
                print(f"DEBUG: Resultado del comando (primeros 200 chars): {result[:200]}")
                print(f"DEBUG: Longitud del resultado: {len(result)}")
            except Exception as timeout_error:
                if "timeout" in str(timeout_error).lower():
                    print(f"DEBUG: Timeout en list_plugins, intentando con formato tabla")
                    # Fallback: usar formato tabla que es más rápido
                    cmd_table = f"cd {self.wp_path} && wp plugin list --status={status}"
                    try:
                        result = self.execute_ssh_command(cmd_table, timeout=30)
                        return self._parse_plugin_table_output(status, result)
                    except Exception as e:
                        print(f"DEBUG: Error en fallback tabla: {e}")
                        return []
                else:
                    raise timeout_error
            
            if result.strip():
                try:
                    plugins = json.loads(result)
                    print(f"DEBUG: JSON parseado exitosamente, {len(plugins)} plugins encontrados")
                    return plugins
                except json.JSONDecodeError as e:
                    print(f"DEBUG: Error al parsear JSON: {e}")
                    print(f"DEBUG: Contenido que causó el error: {result[:500]}")
                    # Fallback: parsear salida de tabla
                    print("DEBUG: Intentando fallback con formato tabla")
                    try:
                        cmd_table = f"cd {self.wp_path} && wp plugin list --status={status}"
                        table_result = self.execute_ssh_command(cmd_table, timeout=30)
                        return self._parse_plugin_table_output(status, table_result)
                    except Exception as fallback_error:
                        print(f"DEBUG: Error en fallback: {fallback_error}")
                        return []
            else:
                print("DEBUG: Resultado vacío del comando WP-CLI")
                return []
                
        except Exception as e:
            print(f"DEBUG: Excepción en list_plugins: {e}")
            # Último intento con comando básico
            try:
                print("DEBUG: Último intento con comando básico")
                basic_cmd = f"cd {self.wp_path} && wp plugin list"
                basic_result = self.execute_ssh_command(basic_cmd, timeout=20)
                return self._parse_plugin_table_output(status, basic_result)
            except Exception as final_error:
                print(f"DEBUG: Error en último intento: {final_error}")
                return []
    
    def _parse_plugin_table_output(self, status: str = 'all', result: str = None) -> List[Dict[str, str]]:
        """
        Parsear salida de tabla cuando JSON no está disponible
        
        Args:
            status: Estado de plugins a listar
            result: Resultado del comando (opcional, si no se proporciona se ejecuta el comando)
            
        Returns:
            Lista de plugins parseados
        """
        try:
            if result is None:
                if status == 'all':
                    cmd = f"cd {self.wp_path} && wp plugin list"
                else:
                    cmd = f"cd {self.wp_path} && wp plugin list --status={status}"
                    
                result = self.execute_ssh_command(cmd, timeout=30)
            
            lines = result.strip().split('\n')
            
            plugins = []
            for line in lines[1:]:  # Saltar header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        plugins.append({
                            'name': parts[0],
                            'status': parts[1],
                            'update': parts[2] if len(parts) > 2 else 'none',
                            'version': parts[3] if len(parts) > 3 else 'unknown'
                        })
            
            return plugins
            
        except Exception:
            return []
    
    def activate_plugin(self, plugin_name: str) -> Tuple[bool, str]:
        """
        Activar un plugin específico
        
        Args:
            plugin_name: Nombre del plugin a activar
            
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            cmd = f"cd {self.wp_path} && wp plugin activate {plugin_name}"
            result = self.execute_ssh_command(cmd)
            
            if "Success:" in result or "already active" in result.lower():
                return True, f"Plugin '{plugin_name}' activado correctamente"
            else:
                return False, f"Error al activar plugin: {result}"
                
        except Exception as e:
            return False, f"Excepción al activar plugin: {str(e)}"
    
    def deactivate_plugin(self, plugin_name: str) -> Tuple[bool, str]:
        """
        Desactivar un plugin específico
        
        Args:
            plugin_name: Nombre del plugin a desactivar
            
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            cmd = f"cd {self.wp_path} && wp plugin deactivate {plugin_name}"
            result = self.execute_ssh_command(cmd)
            
            if "Success:" in result or "already inactive" in result.lower():
                return True, f"Plugin '{plugin_name}' desactivado correctamente"
            else:
                return False, f"Error al desactivar plugin: {result}"
                
        except Exception as e:
            return False, f"Excepción al desactivar plugin: {str(e)}"
    
    def install_plugin(self, plugin_slug: str, activate: bool = False) -> Tuple[bool, str]:
        """
        Instalar un plugin desde el repositorio de WordPress
        
        Args:
            plugin_slug: Slug del plugin en el repositorio
            activate: Si activar el plugin después de instalarlo
            
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            # Comando de instalación
            if activate:
                cmd = f"cd {self.wp_path} && wp plugin install {plugin_slug} --activate"
            else:
                cmd = f"cd {self.wp_path} && wp plugin install {plugin_slug}"
                
            result = self.execute_ssh_command(cmd)
            
            if "Success:" in result:
                action = "instalado y activado" if activate else "instalado"
                return True, f"Plugin '{plugin_slug}' {action} correctamente"
            else:
                return False, f"Error al instalar plugin: {result}"
                
        except Exception as e:
            return False, f"Excepción al instalar plugin: {str(e)}"
    
    def uninstall_plugin(self, plugin_name: str, deactivate_first: bool = True) -> Tuple[bool, str]:
        """
        Desinstalar un plugin completamente
        
        Args:
            plugin_name: Nombre del plugin a desinstalar
            deactivate_first: Si desactivar antes de desinstalar
            
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            # Desactivar primero si está solicitado
            if deactivate_first:
                self.deactivate_plugin(plugin_name)
            
            # Desinstalar
            cmd = f"cd {self.wp_path} && wp plugin uninstall {plugin_name}"
            result = self.execute_ssh_command(cmd)
            
            if "Success:" in result:
                return True, f"Plugin '{plugin_name}' desinstalado correctamente"
            else:
                return False, f"Error al desinstalar plugin: {result}"
                
        except Exception as e:
            return False, f"Excepción al desinstalar plugin: {str(e)}"
    
    def update_plugin(self, plugin_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Actualizar plugins
        
        Args:
            plugin_name: Nombre específico del plugin (None para todos)
            
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            if plugin_name:
                cmd = f"cd {self.wp_path} && wp plugin update {plugin_name}"
            else:
                cmd = f"cd {self.wp_path} && wp plugin update --all"
                
            result = self.execute_ssh_command(cmd)
            
            if "Success:" in result or "already up-to-date" in result.lower():
                target = plugin_name if plugin_name else "todos los plugins"
                return True, f"Actualización de {target} completada"
            else:
                return False, f"Error en actualización: {result}"
                
        except Exception as e:
            return False, f"Excepción en actualización: {str(e)}"
    
    def search_plugins(self, search_term: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Buscar plugins en el repositorio de WordPress
        
        Args:
            search_term: Término de búsqueda
            limit: Límite de resultados
            
        Returns:
            Lista de plugins encontrados
        """
        if not self.check_wp_cli_availability():
            return []
            
        try:
            cmd = f"cd {self.wp_path} && wp plugin search {search_term} --per-page={limit} --format=json"
            result = self.execute_ssh_command(cmd)
            
            if result.strip():
                plugins = json.loads(result)
                return plugins
            else:
                return []
                
        except json.JSONDecodeError:
            # Fallback: parsear salida de tabla
            return self._parse_search_table_output(search_term, limit)
        except Exception:
            return []
    
    def _parse_search_table_output(self, search_term: str, limit: int) -> List[Dict[str, str]]:
        """
        Parsear salida de búsqueda cuando JSON no está disponible
        
        Args:
            search_term: Término de búsqueda
            limit: Límite de resultados
            
        Returns:
            Lista de plugins parseados
        """
        try:
            cmd = f"cd {self.wp_path} && wp plugin search {search_term} --per-page={limit}"
            result = self.execute_ssh_command(cmd)
            lines = result.strip().split('\n')
            
            plugins = []
            for line in lines[1:]:  # Saltar header
                if line.strip() and len(plugins) < limit:
                    parts = line.split('\t')  # Separado por tabs
                    if len(parts) >= 2:
                        plugins.append({
                            'name': parts[0].strip(),
                            'slug': parts[0].strip(),
                            'rating': parts[1].strip() if len(parts) > 1 else 'N/A',
                            'description': parts[2].strip() if len(parts) > 2 else 'N/A'
                        })
            
            return plugins
            
        except Exception:
            return []
    
    def get_plugin_info(self, plugin_name: str) -> Dict[str, str]:
        """
        Obtener información detallada de un plugin
        
        Args:
            plugin_name: Nombre del plugin
            
        Returns:
            Diccionario con información del plugin
        """
        if not self.check_wp_cli_availability():
            return {}
            
        try:
            cmd = f"cd {self.wp_path} && wp plugin get {plugin_name} --format=json"
            result = self.execute_ssh_command(cmd)
            
            if result.strip():
                plugin_info = json.loads(result)
                return plugin_info
            else:
                return {}
                
        except json.JSONDecodeError:
            # Fallback: información básica
            return {'name': plugin_name, 'status': 'unknown'}
        except Exception:
            return {}
    
    def check_plugin_updates(self) -> List[Dict[str, str]]:
        """
        Verificar qué plugins tienen actualizaciones disponibles
        
        Returns:
            Lista de plugins con actualizaciones
        """
        if not self.check_wp_cli_availability():
            return []
            
        try:
            cmd = f"cd {self.wp_path} && wp plugin list --update=available --format=json"
            result = self.execute_ssh_command(cmd)
            
            if result.strip():
                plugins = json.loads(result)
                return plugins
            else:
                return []
                
        except json.JSONDecodeError:
            return []
        except Exception:
            return []
    
    def flush_cache(self) -> Tuple[bool, str]:
        """
        Limpiar caché de WordPress
        
        Returns:
            Tuple (éxito, mensaje)
        """
        if not self.check_wp_cli_availability():
            return False, "WP-CLI no está disponible"
            
        try:
            # Limpiar caché de objetos
            cmd1 = f"cd {self.wp_path} && wp cache flush"
            result1 = self.execute_ssh_command(cmd1)
            
            # Limpiar rewrite rules
            cmd2 = f"cd {self.wp_path} && wp rewrite flush"
            result2 = self.execute_ssh_command(cmd2)
            
            if "Success:" in result1 and "Success:" in result2:
                return True, "Caché limpiado correctamente"
            else:
                return False, f"Error al limpiar caché: {result1} {result2}"
                
        except Exception as e:
            return False, f"Excepción al limpiar caché: {str(e)}"
    
    # ===== FUNCIONES DE TESTING AUTOMATIZADO =====
    
    def check_site_health(self, url: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Verificar el estado de salud del sitio web
        
        Args:
            url: URL del sitio a verificar (opcional)
            
        Returns:
            Tuple (éxito, datos de salud)
        """
        try:
            # Obtener URL del sitio si no se proporciona
            if not url:
                wp_info = self.get_wordpress_info()
                if not wp_info or 'site_url' not in wp_info:
                    return False, {"error": "No se pudo obtener la URL del sitio"}
                url = wp_info['site_url']
            
            # Verificar que el sitio responda
            start_time = time.time()
            try:
                print(f"DEBUG: Verificando URL: {url}")
                response = requests.get(url, timeout=30, allow_redirects=True, verify=False)
                response_time = time.time() - start_time
                
                print(f"DEBUG: Status code: {response.status_code}, Response time: {response_time}")
                
                health_data = {
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': round(response_time, 2),
                    'accessible': response.status_code in [200, 301, 302],
                    'has_errors': response.status_code >= 400,
                    'error_details': []
                }
                
                # Agregar detalles específicos del error HTTP
                if response.status_code >= 400:
                    if response.status_code == 500:
                        health_data['error_details'].append("Error interno del servidor (500)")
                    elif response.status_code == 404:
                        health_data['error_details'].append("Página no encontrada (404)")
                    elif response.status_code == 403:
                        health_data['error_details'].append("Acceso prohibido (403)")
                    else:
                        health_data['error_details'].append(f"Error HTTP {response.status_code}")
                
                # Verificar errores comunes en el contenido
                content = response.text.lower()
                error_indicators = [
                    'fatal error', 'parse error', 'syntax error',
                    'database connection error', 'white screen of death',
                    'internal server error', 'memory limit exceeded',
                    'plugin could not be activated', 'plugin generated'
                ]
                
                for indicator in error_indicators:
                    if indicator in content:
                        health_data['has_errors'] = True
                        health_data['error_details'].append(indicator)
                
                # Verificar logs de error de WordPress
                error_log_check = self.check_error_logs()
                if error_log_check['has_recent_errors']:
                    health_data['has_errors'] = True
                    health_data['error_details'].extend(error_log_check['recent_errors'])
                
                return True, health_data
                
            except Exception as e:
                return False, {"error": f"Error al acceder al sitio: {str(e)}"}
                
        except Exception as e:
            return False, {"error": f"Error en verificación de salud: {str(e)}"}
    
    def check_error_logs(self) -> Dict:
        """
        Verificar logs de error recientes
        
        Returns:
            Diccionario con información de errores
        """
        try:
            # Verificar error.log de WordPress
            debug_log_path = f"{self.wp_path}/wp-content/debug.log"
            
            # Obtener últimas 20 líneas del log
            cmd = f"tail -20 {debug_log_path} 2>/dev/null || echo 'No log file found'"
            log_content = self.execute_ssh_command(cmd)
            
            recent_errors = []
            has_recent_errors = False
            
            if log_content and log_content != "No log file found":
                lines = log_content.split('\n')
                for line in lines:
                    if any(keyword in line.lower() for keyword in ['fatal', 'error', 'warning']):
                        recent_errors.append(line.strip())
                        has_recent_errors = True
            
            return {
                'has_recent_errors': has_recent_errors,
                'recent_errors': recent_errors[-10:],  # Últimos 10 errores
                'log_path': debug_log_path
            }
            
        except Exception as e:
            return {
                'has_recent_errors': False,
                'recent_errors': [],
                'error': str(e)
            }
    
    def test_plugin_activation(self, plugin_name: str, test_url: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Probar la activación de un plugin y verificar si causa problemas
        
        Args:
            plugin_name: Nombre del plugin a probar
            test_url: URL para verificar el sitio
            
        Returns:
            Tuple (éxito, resultado del test)
        """
        try:
            # 1. Verificar estado inicial del sitio
            initial_health = self.check_site_health(test_url)
            if not initial_health[0]:
                return False, {"error": f"Sitio no accesible antes de la prueba: {initial_health[1]}"}
            
            if initial_health[1].get('has_errors', False):
                return False, {"error": f"Sitio tiene errores antes de la prueba: {initial_health[1]['error_details']}"}
            
            # 2. Activar el plugin
            activation_result = self.activate_plugin(plugin_name)
            if not activation_result[0]:
                return False, {"error": f"No se pudo activar el plugin: {activation_result[1]}"}
            
            # 3. Limpiar cache
            self.flush_cache()
            
            # 4. Esperar un momento para que los cambios tomen efecto
            time.sleep(3)
            
            # 5. Verificar estado del sitio después de la activación
            post_activation_health = self.check_site_health(test_url)
            if not post_activation_health[0]:
                return False, {"error": f"Error al verificar sitio después de activación: {post_activation_health[1]}"}
            
            health_data = post_activation_health[1]
            
            # 6. Analizar resultados
            test_result = {
                'plugin_name': plugin_name,
                'activation_successful': True,
                'site_accessible': health_data['accessible'],
                'response_time': health_data['response_time'],
                'has_errors': health_data['has_errors'],
                'error_details': health_data['error_details'],
                'status_code': health_data['status_code'],
                'test_passed': health_data['accessible'] and not health_data['has_errors']
            }
            
            return True, test_result
            
        except Exception as e:
            return False, {"error": f"Error durante el test del plugin: {str(e)}"}
    
    def test_plugin_batch(self, plugin_list: List[str], test_url: Optional[str] = None, auto_rollback: bool = True) -> Tuple[bool, Dict]:
        """
        Probar múltiples plugins en lote
        
        Args:
            plugin_list: Lista de nombres de plugins
            test_url: URL para verificar el sitio
            auto_rollback: Si desactivar automáticamente plugins problemáticos
            
        Returns:
            Tuple (éxito, resultados del batch)
        """
        try:
            results = []
            problematic_plugins = []
            
            # Obtener estado inicial de todos los plugins
            initial_plugins = self.list_plugins('all')
            if not initial_plugins:
                return False, {"error": "No se pudo obtener lista inicial de plugins"}
            
            initial_active_plugins = [p['name'] for p in initial_plugins if p.get('status') == 'active']
            
            for plugin_name in plugin_list:
                # Probar activación del plugin
                test_result = self.test_plugin_activation(plugin_name, test_url)
                
                if test_result[0]:
                    result_data = test_result[1]
                    results.append(result_data)
                    
                    # Si el plugin causa problemas y auto_rollback está habilitado
                    if not result_data['test_passed'] and auto_rollback:
                        self.deactivate_plugin(plugin_name)
                        problematic_plugins.append(plugin_name)
                        
                        # Verificar que el sitio se recuperó
                        recovery_check = self.check_site_health(test_url)
                        if recovery_check[0] and not recovery_check[1].get('has_errors', False):
                            result_data['auto_rollback_successful'] = True
                        else:
                            result_data['auto_rollback_successful'] = False
                            # Si no se recupera, intentar desactivar todos los plugins problemáticos
                            for prob_plugin in problematic_plugins:
                                self.deactivate_plugin(prob_plugin)
                else:
                    # Error en el test
                    results.append({
                        'plugin_name': plugin_name,
                        'test_error': test_result[1],
                        'test_passed': False
                    })
                    problematic_plugins.append(plugin_name)
            
            return True, {
                'total_tested': len(plugin_list),
                'successful_tests': len([r for r in results if r.get('test_passed', False)]),
                'problematic_plugins': problematic_plugins,
                'detailed_results': results,
                'initial_active_plugins': initial_active_plugins
            }
            
        except Exception as e:
            return False, {"error": f"Error en testing por lotes: {str(e)}"}
    
    def create_backup_state(self) -> Tuple[bool, Dict]:
        """
        Crear un backup del estado actual de plugins
        
        Returns:
            Tuple (éxito, estado del backup)
        """
        try:
            plugins = self.list_plugins('all')
            if not plugins:
                return False, {"error": "No se pudo obtener lista de plugins"}
            
            backup_state = {
                'timestamp': time.time(),
                'active_plugins': [p['name'] for p in plugins if p.get('status') == 'active'],
                'inactive_plugins': [p['name'] for p in plugins if p.get('status') == 'inactive']
            }
            
            return True, backup_state
            
        except Exception as e:
            return False, {"error": f"Error al crear backup: {str(e)}"}
    
    def restore_backup_state(self, backup_state: Dict) -> Tuple[bool, str]:
        """
        Restaurar el estado de plugins desde un backup
        
        Args:
            backup_state: Estado del backup a restaurar
            
        Returns:
            Tuple (éxito, mensaje)
        """
        try:
            if not backup_state or 'active_plugins' not in backup_state:
                return False, "Estado de backup inválido"
            
            # Desactivar todos los plugins primero
            all_plugins = self.list_plugins('active')
            if all_plugins:
                for plugin in all_plugins:
                    self.deactivate_plugin(plugin['name'])
            
            # Activar solo los plugins que estaban activos en el backup
            for plugin_name in backup_state['active_plugins']:
                activation_result = self.activate_plugin(plugin_name)
                if not activation_result[0]:
                    print(f"Advertencia: No se pudo reactivar {plugin_name}: {activation_result[1]}")
            
            return True, "Estado restaurado exitosamente"
            
        except Exception as e:
            return False, f"Error al restaurar estado: {str(e)}"