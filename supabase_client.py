"""
Módulo de gestión de base de datos para Pulse usando Cliente de Supabase
Reemplaza psycopg2 con el cliente oficial de Supabase
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseManager:
    """Gestor de base de datos usando Cliente de Supabase"""
    
    def __init__(self):
        self.client: Client = None
        self._connect()
    
    def _connect(self):
        """Establece conexión con Supabase usando el cliente oficial"""
        try:
            url = os.getenv('SUPABASE_URL')
            service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            
            if not url or not service_key:
                raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos")
            
            self.client = create_client(url, service_key)
            logger.info("✅ Conexión a Supabase establecida con cliente oficial")
            
        except Exception as e:
            logger.error(f"❌ Error conectando a Supabase: {e}")
            raise
    
    def save_message(self, message_id: str, user_id: str, text: str, timestamp: float, 
                    thread_ts: str = None, reply_count: int = 0) -> bool:
        """Guarda un mensaje en la base de datos"""
        try:
            # Convertir timestamp a datetime
            message_datetime = datetime.fromtimestamp(timestamp)
            
            data = {
                "message_id": message_id,
                "channel_id": os.getenv('PROJECT_CHANNEL_ID'),
                "user_id": user_id,
                "text": text,
                "timestamp": message_datetime.isoformat(),
                "thread_ts": thread_ts,
                "reply_count": reply_count,
                "message_type": "message",
                "is_update": False,  # Se detectará después
                "contains_decision": False,
                "contains_blocker": False
            }
            
            # Insertar usando upsert para evitar duplicados
            result = self.client.table("slack-channel-project-update").upsert(
                data, 
                on_conflict="message_id"
            ).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error guardando mensaje {message_id}: {e}")
            return False
    
    def save_messages_batch(self, messages: List[Dict[str, Any]]) -> int:
        """Guarda múltiples mensajes en lote"""
        try:
            saved_count = 0
            batch_data = []
            
            for msg in messages:
                if 'user' in msg:  # Solo mensajes de usuarios reales
                    message_datetime = datetime.fromtimestamp(float(msg['ts']))
                    
                    data = {
                        "message_id": msg['ts'],
                        "channel_id": os.getenv('PROJECT_CHANNEL_ID'),
                        "user_id": msg['user'],
                        "text": msg.get('text', ''),
                        "timestamp": message_datetime.isoformat(),
                        "thread_ts": msg.get('thread_ts'),
                        "reply_count": msg.get('reply_count', 0),
                        "message_type": "message",
                        "is_update": False,
                        "contains_decision": False,
                        "contains_blocker": False
                    }
                    batch_data.append(data)
            
            if batch_data:
                # Insertar en lote usando upsert
                result = self.client.table("slack-channel-project-update").upsert(
                    batch_data,
                    on_conflict="message_id"
                ).execute()
                
                saved_count = len(result.data)
            
            logger.info(f"💾 Guardados {saved_count} mensajes en Supabase")
            return saved_count
            
        except Exception as e:
            logger.error(f"❌ Error guardando mensajes en lote: {e}")
            return 0
    
    def get_messages(self, channel_id: str, days: int = 10) -> List[Dict[str, Any]]:
        """Obtiene mensajes de los últimos N días hábiles"""
        try:
            # Calcular fecha de inicio
            current_date = datetime.now()
            business_days_count = 0
            
            while business_days_count < days:
                current_date -= timedelta(days=1)
                if current_date.weekday() < 5:  # Lunes a viernes
                    business_days_count += 1
            
            start_datetime = current_date.isoformat()
            
            # Consultar mensajes usando el cliente de Supabase
            result = self.client.table("slack-channel-project-update").select(
                "message_id, user_id, text, timestamp, thread_ts, reply_count"
            ).eq("channel_id", channel_id).gte("timestamp", start_datetime).order(
                "timestamp", desc=True
            ).execute()
            
            # Convertir a formato esperado por el resto del código
            messages = []
            for row in result.data:
                # Convertir timestamp de vuelta a formato Slack
                timestamp_dt = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                timestamp_float = timestamp_dt.timestamp()
                
                messages.append({
                    'ts': row['message_id'],
                    'user': row['user_id'],
                    'text': row['text'] or '',
                    'timestamp': timestamp_float,
                    'thread_ts': row.get('thread_ts'),
                    'reply_count': row.get('reply_count', 0)
                })
            
            logger.info(f"📨 Obtenidos {len(messages)} mensajes de los últimos {days} días hábiles")
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo mensajes: {e}")
            return []
    
    def save_analysis_report(self, channel_id: str, report_data: Dict[str, Any]) -> bool:
        """Guarda un reporte de análisis"""
        try:
            data = {
                "channel_id": channel_id,
                "analysis_date": datetime.now().date().isoformat(),
                "total_messages": report_data.get('total_messages', 0),
                "active_users": report_data.get('active_users', 0),
                "updates_count": report_data.get('updates_count', 0),
                "decisions_count": report_data.get('decisions_count', 0),
                "blockers_count": report_data.get('blockers_count', 0),
                "sentiment_score": report_data.get('sentiment_score'),
                "team_health_score": report_data.get('team_health_score'),
                "urgency_score": report_data.get('urgency_score'),
                "report_content": report_data.get('report_content', ''),
                "report_sent": report_data.get('report_sent', False)
            }
            
            result = self.client.table("daily-analysis").upsert(
                data,
                on_conflict="channel_id,analysis_date"
            ).execute()
            
            logger.info("✅ Reporte de análisis guardado en Supabase")
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error guardando reporte: {e}")
            return False
    
    def get_user_baseline(self, user_id: str, channel_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Obtiene baseline histórico de un usuario"""
        try:
            # Calcular fecha de inicio
            start_date = datetime.now() - timedelta(days=days)
            start_datetime = start_date.isoformat()
            
            # Consultar mensajes del usuario en el período
            result = self.client.table("slack-channel-project-update").select(
                "timestamp"
            ).eq("channel_id", channel_id).eq("user_id", user_id).gte(
                "timestamp", start_datetime
            ).execute()
            
            if not result.data:
                return None
            
            # Calcular métricas
            total_messages = len(result.data)
            
            # Contar días únicos
            unique_days = set()
            for row in result.data:
                timestamp_dt = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                unique_days.add(timestamp_dt.date())
            
            days_active = len(unique_days)
            avg_messages_per_day = total_messages / days if days > 0 else 0
            
            return {
                'total_messages': total_messages,
                'days_active': days_active,
                'avg_messages_per_day': round(avg_messages_per_day, 2),
                'participation_rate': round((days_active / days) * 100, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo baseline de usuario {user_id}: {e}")
            return None
    
    def mark_message_as_update(self, message_id: str) -> bool:
        """Marca un mensaje como update del proyecto"""
        try:
            result = self.client.table("slack-channel-project-update").update(
                {"is_update": True}
            ).eq("message_id", message_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"❌ Error marcando mensaje como update: {e}")
            return False
    
    def mark_message_analysis(self, message_id: str, sentiment_score: float = None, 
                            urgency_level: str = None, contains_decision: bool = False, 
                            contains_blocker: bool = False) -> bool:
        """Marca análisis de un mensaje"""
        try:
            update_data = {}
            if sentiment_score is not None:
                update_data['sentiment_score'] = sentiment_score
            if urgency_level is not None:
                update_data['urgency_level'] = urgency_level
            if contains_decision is not None:
                update_data['contains_decision'] = contains_decision
            if contains_blocker is not None:
                update_data['contains_blocker'] = contains_blocker
            
            if update_data:
                result = self.client.table("slack-channel-project-update").update(
                    update_data
                ).eq("message_id", message_id).execute()
                
                return len(result.data) > 0
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error marcando análisis de mensaje: {e}")
            return False

# Instancia global del gestor de Supabase
supabase_manager = None

def get_supabase_manager() -> SupabaseManager:
    """Obtiene la instancia global del gestor de Supabase"""
    global supabase_manager
    if supabase_manager is None:
        supabase_manager = SupabaseManager()
    return supabase_manager

def init_supabase():
    """Inicializa la conexión a Supabase"""
    try:
        manager = get_supabase_manager()
        logger.info("✅ Supabase inicializado exitosamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error inicializando Supabase: {e}")
        return False
