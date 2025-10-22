import os
import json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from anthropic import Anthropic
from dotenv import load_dotenv
import time
from supabase_client import get_supabase_manager, init_supabase

# Limpiar variables de entorno previas para forzar recarga
for key in list(os.environ.keys()):
    if key.startswith(('SLACK_', 'ANTHROPIC_', 'SUPABASE_', 'PROJECT_', 'ENVIRONMENT', 'LOG_LEVEL')):
        del os.environ[key]

# Cargar variables de entorno
load_dotenv(override=True)

# Configuración
SLACK_TOKEN = os.getenv('SLACK_BOT_TOKEN')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
CHANNEL_ID = os.getenv('PROJECT_CHANNEL_ID')
LEAD_USER_ID = os.getenv('PROJECT_LEAD_USER_ID')

# Clientes
slack_client = WebClient(token=SLACK_TOKEN)
anthropic_client = Anthropic(api_key=ANTHROPIC_KEY)

# Cache de usuarios
user_cache = {}

def get_user_name(user_id):
    """Obtiene nombre real del usuario (con cache)"""
    if user_id in user_cache:
        return user_cache[user_id]

    try:
        result = slack_client.users_info(user=user_id)
        name = result['user']['real_name']
        username = result['user']['name']
        user_cache[user_id] = f"{name} (@{username})"
        return user_cache[user_id]
    except:
        return f"Usuario {user_id}"

def enrich_messages_with_names(messages):
    """Añade nombres reales a los mensajes"""
    enriched = []
    for msg in messages:
        if 'user' in msg:
            user_name = get_user_name(msg['user'])
            enriched.append({
                'user_id': msg['user'],
                'user_name': user_name,
                'text': msg.get('text', ''),
                'ts': msg['ts']
            })
    return enriched

def calculate_metrics(messages, enriched_messages):
    """Calcula métricas del canal"""

    # Obtener info del canal
    try:
        channel_info = slack_client.conversations_members(channel=CHANNEL_ID)
        total_members = len(channel_info['members'])
    except:
        total_members = 0

    # Contar usuarios únicos activos
    active_users = set()
    for msg in enriched_messages:
        active_users.add(msg['user_id'])

    # Contar mensajes por usuario
    user_message_count = {}
    for msg in enriched_messages:
        user_name = msg['user_name']
        user_message_count[user_name] = user_message_count.get(user_name, 0) + 1

    # Top 3 más activos
    top_active = sorted(user_message_count.items(), key=lambda x: x[1], reverse=True)[:3]

    metrics = {
        'total_messages': len(enriched_messages),
        'active_users': len(active_users),
        'total_members': total_members,
        'participation_rate': round((len(active_users) / total_members * 100) if total_members > 0 else 0, 1),
        'top_active': top_active
    }

    return metrics

def init_db():
    """Inicializa Supabase"""
    return init_supabase()

def calculate_business_days(days=10):
    """Calcula timestamp del inicio de los últimos N días hábiles (solo lunes-viernes)"""
    current_date = datetime.now()
    business_days_count = 0

    while business_days_count < days:
        current_date -= timedelta(days=1)
        # 0 = Monday, 6 = Sunday
        if current_date.weekday() < 5:  # Monday to Friday
            business_days_count += 1

    # Retornar timestamp al inicio del día
    start_of_day = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day.timestamp()

def get_channel_messages(hours=24):
    """Obtiene mensajes del canal de las últimas X horas o días hábiles"""
    try:
        # Primero intentar obtener de Supabase
        supabase = get_supabase_manager()
        db_messages = supabase.get_messages(CHANNEL_ID, days=10)
        
        if db_messages:
            print(f"✅ Obtenidos {len(db_messages)} mensajes de Supabase (últimos 10 días hábiles)")
            return db_messages
        
        # Si no hay mensajes en BD, obtener de Slack
        oldest = calculate_business_days(days=10)
        result = slack_client.conversations_history(
            channel=CHANNEL_ID,
            oldest=str(oldest)
        )

        messages = result['messages']
        print(f"✅ Obtenidos {len(messages)} mensajes de Slack (últimos 10 días hábiles)")
        return messages

    except SlackApiError as e:
        print(f"❌ Error obteniendo mensajes: {e.response['error']}")
        return []

def save_messages(messages):
    """Guarda mensajes en Supabase"""
    supabase = get_supabase_manager()
    return supabase.save_messages_batch(messages)

def get_user_info(user_id):
    """Obtiene info del usuario"""
    try:
        result = slack_client.users_info(user=user_id)
        return result['user']['real_name']
    except:
        return user_id

def extract_project_updates(enriched_messages):
    """Detecta y extrae updates del proyecto de los mensajes"""
    # Keywords que indican updates
    update_keywords = [
        'update', 'actualización', 'progreso', 'avance',
        'completado', 'terminado', 'listo', 'deploy',
        'release', 'merged', 'aprobado', 'bloqueado',
        'pasó a', 'movido a', '%'
    ]

    updates = []

    for msg in enriched_messages:
        text = msg.get('text', '').lower()

        # Filtrar mensajes cortos
        if len(text) < 20:
            continue

        # Buscar keywords
        has_update = any(keyword in text for keyword in update_keywords)

        if has_update:
            updates.append({
                'user_name': msg['user_name'],
                'text': msg.get('text', ''),
                'timestamp': msg['ts']
            })

    # Ordenar por timestamp (cronológicamente)
    updates.sort(key=lambda x: float(x['timestamp']))

    return updates

def analyze_project_health(enriched_messages, updates):
    """Analiza la salud del proyecto basado en señales positivas y negativas"""
    # Palabras clave
    positive_keywords = ['completado', 'listo', 'terminado', 'merged', 'aprobado', 'resuelto', 'funciona', 'done', 'finished']
    negative_keywords = ['bloqueado', 'stuck', 'problema', 'error', 'bug', 'crítico', 'urgente', 'esperando', 'no puedo', 'blocked', 'issue']

    señales_positivas = []
    señales_negativas = []

    # Analizar todos los mensajes
    all_messages = enriched_messages + [{'user_name': u['user_name'], 'text': u['text']} for u in updates]

    for msg in all_messages:
        text = msg.get('text', '').lower()
        user_name = msg.get('user_name', 'Unknown')

        # Buscar señales positivas
        for keyword in positive_keywords:
            if keyword in text:
                señales_positivas.append({
                    'user': user_name,
                    'keyword': keyword,
                    'context': msg.get('text', '')[:100]  # Primeros 100 caracteres
                })

        # Buscar señales negativas
        for keyword in negative_keywords:
            if keyword in text:
                señales_negativas.append({
                    'user': user_name,
                    'keyword': keyword,
                    'context': msg.get('text', '')[:100]
                })

    # Calcular score de salud (0-100)
    total_signals = len(señales_positivas) + len(señales_negativas)
    if total_signals > 0:
        score = int((len(señales_positivas) / total_signals) * 100)
    else:
        score = 75  # Neutral si no hay señales

    return {
        'score': score,
        'señales_positivas': señales_positivas,
        'señales_negativas': señales_negativas
    }

def analyze_participation_quality(enriched_messages):
    """Analiza la calidad de participación por usuario"""
    user_analysis = {}

    for msg in enriched_messages:
        user_id = msg.get('user_id')
        user_name = msg.get('user_name')
        text = msg.get('text', '')

        if user_id not in user_analysis:
            user_analysis[user_id] = {
                'name': user_name,
                'total_messages': 0,
                'preguntas': 0,
                'respuestas': 0,
                'tecnico': 0,
                'coordinacion': 0
            }

        user_analysis[user_id]['total_messages'] += 1

        # Detectar preguntas
        if '?' in text:
            user_analysis[user_id]['preguntas'] += 1

        # Detectar respuestas (menciones)
        if '<@' in text or '@' in text:
            user_analysis[user_id]['respuestas'] += 1

        # Detectar mensajes técnicos
        technical_keywords = ['código', 'code', 'api', 'database', 'bug', 'error', 'función', 'function', 'deploy', 'merge', 'commit']
        if any(kw in text.lower() for kw in technical_keywords):
            user_analysis[user_id]['tecnico'] += 1

        # Detectar coordinación
        coordination_keywords = ['reunión', 'meeting', 'deadline', 'entrega', 'sprint', 'sync', 'stand-up', 'standup']
        if any(kw in text.lower() for kw in coordination_keywords):
            user_analysis[user_id]['coordinacion'] += 1

    # Clasificar usuarios
    for user_id, data in user_analysis.items():
        total = data['total_messages']

        if total < 3:
            data['tipo'] = 'Observador'
        elif data['tecnico'] / total > 0.5:
            data['tipo'] = 'Facilitador'
        elif data['coordinacion'] / total > 0.5:
            data['tipo'] = 'Coordinador'
        else:
            data['tipo'] = 'Contribuidor'

        # Ratio preguntas/respuestas
        if data['respuestas'] > 0:
            data['ratio_preguntas_respuestas'] = round(data['preguntas'] / data['respuestas'], 2)
        else:
            data['ratio_preguntas_respuestas'] = data['preguntas']

        # Temas principales
        temas = []
        if data['tecnico'] > 0:
            temas.append(f"técnico ({data['tecnico']})")
        if data['coordinacion'] > 0:
            temas.append(f"coordinación ({data['coordinacion']})")
        if data['preguntas'] > 0:
            temas.append(f"preguntas ({data['preguntas']})")
        data['temas_principales'] = ', '.join(temas) if temas else 'general'

    return user_analysis

def infer_causes(enriched_messages, user_analysis, users_with_baseline):
    """Infiere causas de comportamiento basado en patrones"""
    causes = {}

    for user_id, analysis in user_analysis.items():
        user_name = analysis['name']
        total_msgs = analysis['total_messages']

        # Buscar baseline del usuario
        baseline_info = next((u for u in users_with_baseline if u['name'] == user_name), None)

        causa = None
        evidencia = []

        # Analizar ausencia
        if total_msgs == 0:
            causa = "ausencia_total"
            evidencia.append("Sin actividad en el período")

        # Baja participación con baseline
        elif baseline_info and baseline_info.get('comparison', {}).get('has_baseline'):
            comparison = baseline_info['comparison']
            if comparison['direction'] == 'por debajo' and comparison['diff_percentage'] > 50:
                # Buscar mensaje de ausencia
                ausencia_keywords = ['fuera', 'ausente', 'no estaré', 'enfermo', 'vacaciones', 'permiso', 'offline']
                user_messages = [m['text'].lower() for m in enriched_messages if m['user_name'] == user_name]
                if any(any(kw in msg for kw in ausencia_keywords) for msg in user_messages):
                    causa = "ausencia_reportada"
                    evidencia.append(f"Actividad {comparison['diff_percentage']}% por debajo del promedio")
                    evidencia.append("Usuario reportó ausencia")
                else:
                    causa = "baja_participacion_inusual"
                    evidencia.append(f"Actividad {comparison['diff_percentage']}% por debajo del promedio sin explicación")

        # Alta actividad resolviendo dudas
        if analysis['respuestas'] > 5 and analysis['tecnico'] > 3:
            causa = "desbloqueando_equipo"
            evidencia.append(f"{analysis['respuestas']} respuestas técnicas")
            evidencia.append("Patrón de resolver dudas del equipo")

        # Bloqueado (muchas preguntas sin respuestas)
        if analysis['preguntas'] > 3 and analysis['respuestas'] == 0:
            causa = "posiblemente_bloqueado"
            evidencia.append(f"{analysis['preguntas']} preguntas sin respuestas aparentes")
            evidencia.append("Buscando ayuda sin obtenerla")

        if causa:
            causes[user_id] = {
                'user_name': user_name,
                'causa_inferida': causa,
                'evidencia': evidencia
            }

    return causes

def classify_project_status(enriched_messages, channel_baseline):
    """Clasifica el estado del proyecto basado en análisis de mensajes y baseline"""
    # Keywords para detectar estado
    delayed_keywords = ['delayed', 'retrasado', 'retraso', 'atrasado']
    blocked_keywords = ['bloqueado', 'blocked', 'stuck', 'waiting', 'esperando']
    sensitivity_keywords = ['deadline', 'cliente', 'urgente', 'crítico', 'client', 'urgent', 'critical']

    delayed_count = 0
    blocked_count = 0
    sensitivity_count = 0

    for msg in enriched_messages:
        text = msg.get('text', '').lower()

        if any(kw in text for kw in delayed_keywords):
            delayed_count += 1
        if any(kw in text for kw in blocked_keywords):
            blocked_count += 1
        if any(kw in text for kw in sensitivity_keywords):
            sensitivity_count += 1

    # Determinar status
    if blocked_count > 2:
        status = "blocked"
        status_emoji = "🔴"
        status_text = "BLOQUEADO - Requiere atención inmediata"
    elif delayed_count > 1:
        status = "delayed"
        status_emoji = "🟡"
        status_text = "RETRASADO - Necesita acción correctiva"
    elif channel_baseline and len(enriched_messages) > channel_baseline.get('avg_messages_per_day', 0) * 1.5:
        status = "fast_track"
        status_emoji = "🟢"
        status_text = "AVANCE RÁPIDO - Por encima del ritmo esperado"
    else:
        status = "on_track"
        status_emoji = "🟢"
        status_text = "EN TIEMPO - Progreso normal"

    # Determinar sensitivity
    if sensitivity_count > 3:
        sensitivity = "time_sensitive"
        sensitivity_emoji = "⏰"
        sensitivity_text = "SENSIBLE AL TIEMPO - Múltiples deadlines/clientes mencionados"
    else:
        sensitivity = "non_time_sensitive"
        sensitivity_emoji = "✅"
        sensitivity_text = "NO CRÍTICO - Sin presiones temporales detectadas"

    # Determinar recursos (basado en baseline)
    if channel_baseline:
        avg_activity = channel_baseline.get('avg_messages_per_day', 0)
        current_activity = len(enriched_messages)

        if current_activity < avg_activity * 0.6:
            resources = "can_reduce"
            resources_emoji = "📉"
            resources_text = "CAPACIDAD DISPONIBLE - Actividad por debajo del promedio"
        elif current_activity > avg_activity * 1.3:
            resources = "need"
            resources_emoji = "📈"
            resources_text = "REQUIERE MÁS RECURSOS - Actividad muy por encima del promedio"
        else:
            resources = "perfect"
            resources_emoji = "✅"
            resources_text = "RECURSOS ADECUADOS - Actividad dentro del rango normal"
    else:
        resources = "unknown"
        resources_emoji = "❓"
        resources_text = "DESCONOCIDO - Sin histórico para comparar"

    return {
        'status': status,
        'status_emoji': status_emoji,
        'status_text': status_text,
        'sensitivity': sensitivity,
        'sensitivity_emoji': sensitivity_emoji,
        'sensitivity_text': sensitivity_text,
        'resources': resources,
        'resources_emoji': resources_emoji,
        'resources_text': resources_text
    }

def extract_project_progress(enriched_messages, updates):
    """Extrae información de progreso del proyecto"""
    import re

    objetivo_mencionado = None
    progreso_actual = None
    tiempo_estimado = None
    razon_desviacion = None

    # Buscar objetivos/metas
    objetivo_keywords = ['objetivo', 'meta', 'goal', 'target', 'milestone']
    deadline_keywords = ['deadline', 'fecha límite', 'entrega', 'due date']

    for msg in enriched_messages + [{'text': u['text'], 'user_name': u['user_name']} for u in updates]:
        text = msg.get('text', '')

        # Buscar objetivos
        for kw in objetivo_keywords:
            if kw in text.lower():
                objetivo_mencionado = text[:150]  # Primeros 150 caracteres
                break

        # Buscar porcentajes (X%, "X de Y")
        percentage_match = re.search(r'(\d+)%', text)
        if percentage_match:
            progreso_actual = f"{percentage_match.group(1)}%"

        fraction_match = re.search(r'(\d+)\s+de\s+(\d+)', text)
        if fraction_match:
            num = int(fraction_match.group(1))
            den = int(fraction_match.group(2))
            progreso_actual = f"{num}/{den} ({int(num/den*100)}%)"

        # Buscar deadlines
        for kw in deadline_keywords:
            if kw in text.lower():
                tiempo_estimado = text[:150]
                break

        # Buscar razón de desviación
        if any(word in text.lower() for word in ['porque', 'debido a', 'por', 'retraso por', 'bloqueado por']):
            if any(neg in text.lower() for neg in ['retraso', 'problema', 'bloqueado']):
                razon_desviacion = text[:150]

    return {
        'objetivo_mencionado': objetivo_mencionado,
        'progreso_actual': progreso_actual or "No especificado",
        'tiempo_estimado': tiempo_estimado,
        'razon_desviacion': razon_desviacion
    }

def analyze_capacity_per_person(enriched_messages, users_with_baseline, channel_id):
    """Analiza capacidad por persona - TODOS los miembros del canal"""
    capacity_analysis = {}

    # Obtener TODOS los miembros del canal
    try:
        all_members_response = slack_client.conversations_members(channel=channel_id)
        all_member_ids = all_members_response['members']
    except:
        # Si falla, usar solo los usuarios con baseline
        all_member_ids = [u['id'] for u in users_with_baseline]

    # Crear dict de usuarios activos para búsqueda rápida
    active_users = {u['id']: u for u in users_with_baseline}

    for member_id in all_member_ids:
        # Obtener info del usuario
        try:
            user_info_response = slack_client.users_info(user=member_id)
            user_data = user_info_response['user']

            # Skip bots
            if user_data.get('is_bot') or user_data.get('deleted'):
                continue

            user_name = user_data.get('real_name', member_id)
        except:
            user_name = member_id

        # Verificar si está en usuarios activos
        if member_id in active_users:
            user_info = active_users[member_id]
            messages_today = user_info['messages_today']
            baseline = user_info.get('baseline')
            comparison = user_info.get('comparison', {})
        else:
            # Usuario sin actividad hoy
            messages_today = 0
            baseline = get_user_baseline(member_id, channel_id, days=30)
            if baseline:
                comparison = compare_to_baseline(0, baseline['avg_messages_per_day'], "mensajes")
            else:
                comparison = {'has_baseline': False}

        # Calcular carga actual
        if messages_today == 0:
            carga = "⚪ SIN ACTIVIDAD - No participó hoy"
        elif baseline and comparison.get('has_baseline'):
            avg_msgs = baseline['avg_messages_per_day']
            if messages_today > avg_msgs * 1.5:
                carga = "🔴 ALTA - Actividad significativamente elevada"
            elif messages_today < avg_msgs * 0.5:
                carga = "🟢 BAJA - Actividad reducida"
            else:
                carga = "🟡 NORMAL - Dentro del rango habitual"
        else:
            carga = "❓ DESCONOCIDA - Sin histórico"

        # Inferir disponibilidad
        if messages_today == 0:
            if comparison.get('has_baseline'):
                disponibilidad = "❓ AUSENTE HOY - Verificar disponibilidad"
            else:
                disponibilidad = "❓ SIN DATOS - Usuario nuevo o inactivo"
        elif comparison.get('direction') == 'por debajo' and comparison.get('diff_percentage', 0) > 40:
            disponibilidad = "✅ PUEDE TOMAR MÁS - Actividad muy por debajo del promedio"
        elif comparison.get('direction') == 'por encima' and comparison.get('diff_percentage', 0) > 40:
            disponibilidad = "❌ NO PUEDE TOMAR MÁS - Ya sobrecargado"
        else:
            disponibilidad = "⚠️ CAPACIDAD LIMITADA - En su nivel normal"

        # Detectar bloqueadores en sus mensajes
        user_messages = [m['text'] for m in enriched_messages if m.get('user_name') == user_name]
        bloqueadores = []

        blocker_keywords = ['bloqueado', 'blocked', 'esperando', 'waiting', 'stuck', 'no puedo']
        for msg in user_messages:
            for kw in blocker_keywords:
                if kw in msg.lower():
                    bloqueadores.append(msg[:100])
                    break

        # Análisis de si puede liberarse
        if messages_today == 0:
            puede_liberarse = "✅ DISPONIBLE - Sin actividad detectada"
        elif bloqueadores:
            puede_liberarse = "❌ NO - Tiene bloqueadores activos"
        elif messages_today < 3:
            puede_liberarse = "✅ SÍ - Baja actividad, puede reasignarse"
        else:
            puede_liberarse = "⚠️ POSIBLE - Depende de prioridades"

        capacity_analysis[member_id] = {
            'name': user_name,
            'carga': carga,
            'disponibilidad': disponibilidad,
            'bloqueadores': bloqueadores[:3] if bloqueadores else ["Ninguno detectado"],
            'puede_liberarse': puede_liberarse,
            'messages_today': messages_today
        }

    return capacity_analysis

def extract_required_decisions(enriched_messages):
    """Extrae decisiones pendientes"""
    decisions = []

    decision_keywords = ['necesito que', 'requiero aprobación', 'necesitamos decidir', 'hay que decidir',
                         'debemos decidir', 'need approval', 'need to decide', '?']

    for msg in enriched_messages:
        text = msg.get('text', '')
        user_name = msg.get('user_name')

        # Solo si contiene pregunta o frase de decisión
        if any(kw in text.lower() for kw in decision_keywords):
            decisions.append({
                'que': text[:200],
                'quien_pide': user_name,
                'timestamp': msg.get('ts')
            })

    return decisions[:5]  # Top 5 más relevantes

def extract_critical_risks(enriched_messages):
    """Extrae solo riesgos de ALTO IMPACTO"""
    risks = []

    critical_keywords = ['crítico', 'urgente', 'problema grave', 'cliente en riesgo',
                        'vamos a perder', 'critical', 'urgent', 'severe', 'losing client']

    for msg in enriched_messages:
        text = msg.get('text', '')
        user_name = msg.get('user_name')

        if any(kw in text.lower() for kw in critical_keywords):
            # Inferir probabilidad e impacto
            if 'crítico' in text.lower() or 'critical' in text.lower():
                impacto = "ALTO"
                probabilidad = "ALTA"
            elif 'cliente' in text.lower() or 'client' in text.lower():
                impacto = "ALTO"
                probabilidad = "MEDIA"
            else:
                impacto = "MEDIO-ALTO"
                probabilidad = "MEDIA"

            risks.append({
                'riesgo': text[:200],
                'reportado_por': user_name,
                'probabilidad': probabilidad,
                'impacto': impacto
            })

    return risks[:3]  # Top 3 riesgos críticos

def detect_meeting_attendance(enriched_messages):
    """Detecta asistencia a reuniones de sincronización"""
    # Solo reuniones de sincronización específicas
    meeting_keywords = ['sync', 'sincronización', 'standup', 'stand-up', 'daily', 'reunión de equipo', 'meeting de equipo']
    attendance_keywords = ['estoy en', 'me uno', 'joining', 'en la reunión', 'en el sync', 'en el daily', 'en el standup']
    absence_keywords = ['no puedo ir', 'no podré', 'me ausento', 'cant join', 'cannot attend', 'miss the', 'skip']

    meetings_detected = []
    attendees = []
    absences = []

    for msg in enriched_messages:
        text = msg.get('text', '')
        user_name = msg.get('user_name')

        # Detectar si menciona meeting
        is_meeting_mention = any(kw in text.lower() for kw in meeting_keywords)

        if is_meeting_mention:
            meetings_detected.append({
                'mentioned_by': user_name,
                'text': text[:150]
            })

            # Detectar asistencia
            if any(kw in text.lower() for kw in attendance_keywords):
                attendees.append({
                    'name': user_name,
                    'context': text[:100]
                })

            # Detectar ausencia
            if any(kw in text.lower() for kw in absence_keywords):
                # Intentar extraer razón
                razon = "No especificada"
                if 'porque' in text.lower() or 'due to' in text.lower():
                    razon = text[:150]

                absences.append({
                    'name': user_name,
                    'razon': razon
                })

    return {
        'meetings_detected': len(meetings_detected) > 0,
        'num_meetings': len(meetings_detected),
        'attendees': attendees,
        'absences': absences
    }

def get_slack_thread_links(enriched_messages, updates, channel_id):
    """Genera links de Slack a threads importantes"""
    links = {
        'updates_links': [],
        'decisions_links': [],
        'risks_links': []
    }

    # Links para updates
    for update in updates[:5]:
        ts = update['timestamp'].replace('.', '')
        link = f"https://slack.com/app_redirect?channel={channel_id}&message_ts={update['timestamp']}"
        links['updates_links'].append({
            'text': update['text'][:50] + '...',
            'link': link,
            'user': update['user_name']
        })

    # Links para decisiones (mensajes con ?)
    for msg in enriched_messages:
        if '?' in msg.get('text', ''):
            ts = msg['ts'].replace('.', '')
            link = f"https://slack.com/app_redirect?channel={channel_id}&message_ts={msg['ts']}"
            links['decisions_links'].append({
                'text': msg['text'][:50] + '...',
                'link': link,
                'user': msg['user_name']
            })
            if len(links['decisions_links']) >= 3:
                break

    # Links para riesgos
    risk_keywords = ['crítico', 'urgente', 'problema', 'critical', 'urgent']
    for msg in enriched_messages:
        text = msg.get('text', '')
        if any(kw in text.lower() for kw in risk_keywords):
            ts = msg['ts'].replace('.', '')
            link = f"https://slack.com/app_redirect?channel={channel_id}&message_ts={msg['ts']}"
            links['risks_links'].append({
                'text': text[:50] + '...',
                'link': link,
                'user': msg['user_name']
            })
            if len(links['risks_links']) >= 3:
                break

    return links

def analyze_with_claude(enriched_messages, metrics, updates):
    """Analiza mensajes con Claude usando baseline histórico"""

    # Filtrar solo mensajes reales (no automáticos del sistema)
    real_messages = []
    for msg in enriched_messages:
        text = msg.get('text', '')
        if (text and
            'se ha unido al canal' not in text.lower() and
            'has joined' not in text.lower() and
            '<@' not in text[:5] and
            len(text) > 15):
            real_messages.append(msg)

    if not real_messages:
        return "Sin actividad significativa en las últimas 24 horas."

    # Obtener baseline del canal
    channel_baseline = get_channel_baseline(CHANNEL_ID, days=30)

    # Preparar análisis con baseline por usuario
    users_with_baseline = []
    for msg in real_messages:
        user_id = msg['user_id']
        user_name = msg['user_name']

        # Evitar duplicados
        if not any(u['id'] == user_id for u in users_with_baseline):
            # Contar mensajes de este usuario hoy
            user_msg_count = sum(1 for m in real_messages if m['user_id'] == user_id)

            # Obtener baseline del usuario
            user_baseline = get_user_baseline(user_id, CHANNEL_ID, days=30)

            user_data = {
                'id': user_id,
                'name': user_name,
                'messages_today': user_msg_count
            }

            if user_baseline:
                comparison = compare_to_baseline(
                    user_msg_count,
                    user_baseline['avg_messages_per_day'],
                    "mensajes"
                )
                user_data['baseline'] = user_baseline
                user_data['comparison'] = comparison
            else:
                user_data['baseline'] = None
                user_data['comparison'] = {'has_baseline': False}

            users_with_baseline.append(user_data)

    # Análisis predictivo y estructura
    project_health = analyze_project_health(real_messages, updates)
    participation_quality = analyze_participation_quality(real_messages)
    inferred_causes = infer_causes(real_messages, participation_quality, users_with_baseline)
    project_status = classify_project_status(real_messages, channel_baseline)
    project_progress = extract_project_progress(real_messages, updates)
    capacity_analysis = analyze_capacity_per_person(real_messages, users_with_baseline, CHANNEL_ID)
    required_decisions = extract_required_decisions(real_messages)
    critical_risks = extract_critical_risks(real_messages)
    meeting_attendance = detect_meeting_attendance(real_messages)
    slack_links = get_slack_thread_links(real_messages, updates, CHANNEL_ID)

    # Calcular estado del equipo
    total_members = len(capacity_analysis)
    active_today = len([u for u in capacity_analysis.values() if u['messages_today'] > 0])
    inactive_today = total_members - active_today

    inactive_users = []
    for user_id, user_data in capacity_analysis.items():
        if user_data['messages_today'] == 0:
            # Buscar razón inferida
            razon = "Razón desconocida"
            if user_id in inferred_causes:
                razon = inferred_causes[user_id]['causa_inferida']
            inactive_users.append({
                'name': user_data['name'],
                'razon': razon
            })

    # Preparar contexto para Claude
    conversations = []
    for msg in real_messages:
        conversations.append(f"*{msg['user_name']}*: {msg['text']}")
    message_text = "\n".join(conversations)

    # Preparar info de baseline para el prompt
    baseline_context = ""

    if channel_baseline:
        channel_comparison = compare_to_baseline(
            len(real_messages),
            channel_baseline['avg_messages_per_day'],
            "mensajes del canal"
        )
        baseline_context += f"\n📊 BASELINE DEL CANAL (últimos 30 días):\n"
        baseline_context += f"• Promedio mensajes/día: {channel_baseline['avg_messages_per_day']}\n"
        baseline_context += f"• Hoy: {len(real_messages)} mensajes\n"
        baseline_context += f"• Comparación: {channel_comparison['message']}\n"

    baseline_context += f"\n📊 BASELINE POR USUARIO:\n"
    for user in users_with_baseline:
        baseline_context += f"\n*{user['name']}*:\n"
        baseline_context += f"• Mensajes hoy: {user['messages_today']}\n"
        if user['baseline']:
            baseline_context += f"• Promedio últimos 30 días: {user['baseline']['avg_messages_per_day']}/día\n"
            baseline_context += f"• Días activo: {user['baseline']['days_active']}/30 ({user['baseline']['participation_rate']}%)\n"
            if user['comparison']['has_baseline']:
                baseline_context += f"• {user['comparison']['message']}\n"
        else:
            baseline_context += f"• Sin histórico suficiente (usuario nuevo o poco activo)\n"

    # Obtener nombre del canal
    try:
        channel_info = slack_client.conversations_info(channel=CHANNEL_ID)
        channel_name = channel_info['channel']['name']
    except:
        channel_name = "proyecto"

    # Preparar sección de updates
    updates_context = ""
    if updates:
        updates_context = "\n📋 UPDATES DEL PROYECTO (Pre-filtrados):\n"
        updates_context += "----------\n"
        for update in updates:
            updates_context += f"• *{update['user_name']}*: {update['text']}\n"
        updates_context += "----------\n"

    # Preparar análisis automatizado
    automated_analysis = f"\n🤖 ANÁLISIS AUTOMATIZADO:\n"
    automated_analysis += "----------\n"
    automated_analysis += f"📊 *Salud del proyecto:* {project_health['score']}/100\n"

    if project_health['señales_positivas']:
        automated_analysis += f"\n✅ *Señales positivas detectadas:*\n"
        for signal in project_health['señales_positivas'][:5]:  # Top 5
            automated_analysis += f"  • {signal['user']}: {signal['keyword']} - {signal['context'][:60]}...\n"

    if project_health['señales_negativas']:
        automated_analysis += f"\n⚠️ *Señales negativas detectadas:*\n"
        for signal in project_health['señales_negativas'][:5]:  # Top 5
            automated_analysis += f"  • {signal['user']}: {signal['keyword']} - {signal['context'][:60]}...\n"

    automated_analysis += f"\n👥 *Participación por calidad:*\n"
    for user_id, data in participation_quality.items():
        automated_analysis += f"  • {data['name']} ({data['tipo']}): {data['total_messages']} msgs - {data['temas_principales']}\n"

    if inferred_causes:
        automated_analysis += f"\n🔍 *Causas inferidas:*\n"
        for user_id, cause_data in inferred_causes.items():
            automated_analysis += f"  • {cause_data['user_name']}: {cause_data['causa_inferida']}\n"
            for ev in cause_data['evidencia']:
                automated_analysis += f"    - {ev}\n"

    automated_analysis += "----------\n"

    # Preparar contexto estructurado para Claude
    structured_context = f"""
🎯 ESTADO DEL PROYECTO (Análisis automatizado):
- Status: {project_status['status_emoji']} {project_status['status_text']}
- Sensibilidad: {project_status['sensitivity_emoji']} {project_status['sensitivity_text']}
- Recursos: {project_status['resources_emoji']} {project_status['resources_text']}

📊 PROGRESO:
- Objetivo mencionado: {project_progress['objetivo_mencionado'] or 'No especificado'}
- Progreso actual: {project_progress['progreso_actual']}
- Tiempo estimado: {project_progress['tiempo_estimado'] or 'No especificado'}
- Razón desviación: {project_progress['razon_desviacion'] or 'N/A'}

👥 CAPACIDAD POR PERSONA:
"""
    for user_id, cap_data in capacity_analysis.items():
        structured_context += f"\n{cap_data['name']}:\n"
        structured_context += f"  - Carga: {cap_data['carga']}\n"
        structured_context += f"  - Disponibilidad: {cap_data['disponibilidad']}\n"
        structured_context += f"  - Bloqueadores: {', '.join(cap_data['bloqueadores'][:2])}\n"
        structured_context += f"  - Puede liberarse: {cap_data['puede_liberarse']}\n"

    structured_context += f"\n⚠️ DECISIONES REQUERIDAS: {len(required_decisions)} pendientes\n"
    structured_context += f"🔴 RIESGOS CRÍTICOS: {len(critical_risks)} detectados\n"

    structured_context += f"\n👥 ESTADO DEL EQUIPO:\n"
    structured_context += f"  - Total miembros: {total_members}\n"
    structured_context += f"  - Activos hoy: {active_today}\n"
    structured_context += f"  - Inactivos hoy: {inactive_today}\n"
    if inactive_users:
        structured_context += f"  - Usuarios inactivos:\n"
        for inactive_user in inactive_users:
            structured_context += f"    • {inactive_user['name']}: {inactive_user['razon']}\n"

    structured_context += f"\n📞 ASISTENCIA A REUNIONES DE SINCRONIZACIÓN:\n"
    if meeting_attendance['meetings_detected']:
        structured_context += f"  - Reuniones detectadas: {meeting_attendance['num_meetings']}\n"
        structured_context += f"  - Asistentes: {', '.join(meeting_attendance['attendees']) if meeting_attendance['attendees'] else 'Ninguno registrado'}\n"
        if meeting_attendance['absences']:
            structured_context += f"  - Ausencias:\n"
            for absence in meeting_attendance['absences']:
                structured_context += f"    • {absence['name']}: {absence['reason']}\n"
    else:
        structured_context += f"  - No se detectaron reuniones de sincronización registradas\n"

    prompt = f"""Eres un analista ejecutivo que genera reportes diarios STANDALONE (sin asumir memoria del lector).

DATOS DEL CANAL #{channel_name}:
----------
{message_text}
----------

{updates_context}

{structured_context}

{automated_analysis}

INSTRUCCIONES CRÍTICAS:
1. NUNCA uses lenguaje genérico - SIEMPRE nombres completos
2. CADA afirmación DEBE tener: NOMBRE + NÚMERO + POR QUÉ
3. NO asumas memoria del lector - cada reporte es independiente
4. USA SOLO datos del análisis automatizado previo
5. Cuantifica TODO (números, fechas, porcentajes)
6. Si no tienes datos concretos, di "No especificado" en vez de inventar

Genera el reporte en este formato EXACTO:

----------
🎯 *ESTADO DEL PROYECTO*
----------
Estado: {project_status['status_emoji']} {project_status['status_text']}
Sensibilidad: {project_status['sensitivity_emoji']} {project_status['sensitivity_text']}
Recursos: {project_status['resources_emoji']} {project_status['resources_text']}

Progreso vs Objetivo:
• {project_progress['progreso_actual']} completado
• {project_progress['objetivo_mencionado'][:100] if project_progress['objetivo_mencionado'] else 'Objetivo no especificado en conversaciones'}

----------
📋 *UPDATES DEL PROYECTO*
----------
[Lista updates cronológicamente con formato: "• NOMBRE: texto específico del update"
Si no hay updates: "Sin updates reportados hoy"]

----------
👥 *ESTADO DEL EQUIPO*
----------
Total miembros del canal: {{total_members}}
Activos hoy: {{active_today}}
Inactivos hoy: {{inactive_today}}

[Si hay usuarios inactivos, lista cada uno con formato:
"• NOMBRE: razón"
Si todos activos: "Todos los miembros participaron hoy"]

----------
📞 *ASISTENCIA A REUNIONES DE SINCRONIZACIÓN*
----------
[Si meeting_attendance['meetings_detected']:
  "Se detectaron N reunión(es) de sincronización"
  "Asistentes: lista nombres"
  Si hay absences: "Ausencias: lista con formato '• NOMBRE: razón'"
Si no: "No se detectaron reuniones de sincronización registradas"]

----------
👥 *RECURSOS Y CAPACIDAD*
----------
[Para CADA persona del análisis de capacidad, usa este formato exacto:]

*NOMBRE COMPLETO*
- Carga actual: [emoji y dato específico del análisis]
- Disponibilidad: [emoji y conclusión]
- Bloqueadores: [lista específica o "Ninguno"]
- Podría liberarse: [emoji y análisis]

----------
⚠️ *DECISIONES REQUERIDAS*
----------
[Solo si hay decisiones pendientes en el análisis. Lista con formato:
"• QUIÉN pide QUÉ: texto específico"
Si no hay: "Ninguna decisión pendiente"]

----------
🔴 *RIESGOS DE ALTO IMPACTO*
----------
[Solo riesgos críticos del análisis. Formato:
"• RIESGO: [texto]
  Reportado por: NOMBRE
  Probabilidad: [ALTA/MEDIA]
  Impacto: [ALTO/MEDIO-ALTO]"
Si no hay: "No se detectaron riesgos críticos"]

RECUERDA: Nombres específicos + números concretos + por qués basados en datos."""

    print("🤔 Analizando con contexto histórico...")

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )

        analysis = message.content[0].text
        print("✅ Análisis completado con baseline")
        return analysis, slack_links

    except Exception as e:
        print(f"❌ Error en análisis: {e}")
        return None, None

def generate_summary_metrics(enriched_messages):
    """Genera métricas clave de los últimos 10 días hábiles"""
    # Filtrar mensajes reales
    real_messages = [m for m in enriched_messages if len(m.get('text', '')) > 15]
    messages_total = len(real_messages)

    # Usuarios activos
    active_users = len(set(m['user_id'] for m in real_messages))

    # Obtener total de miembros
    try:
        channel_info = slack_client.conversations_members(channel=CHANNEL_ID)
        total_members = len(channel_info['members'])
    except:
        total_members = active_users

    metrics_text = "📊 *MÉTRICAS CLAVE (Últimos 10 días hábiles)*\n"
    metrics_text += "----------\n"
    metrics_text += f"📨 Mensajes: {messages_total}\n"
    metrics_text += f"👥 Usuarios activos: {active_users} de {total_members}\n"
    metrics_text += "----------\n\n"

    return metrics_text

def send_report_to_lead(report, enriched_messages, slack_links):
    """Envía reporte por DM al líder del proyecto"""
    try:
        # Obtener nombre del canal
        channel_info = slack_client.conversations_info(channel=CHANNEL_ID)
        channel_name = channel_info['channel']['name']

        # Abrir conversación DM
        dm_response = slack_client.conversations_open(users=[LEAD_USER_ID])
        dm_channel = dm_response['channel']['id']

        # Generar métricas resumidas
        metrics_summary = generate_summary_metrics(enriched_messages)

        # Formatear con espaciado
        formatted_report = report.replace('**', '*')

        # Preparar sección de links de Slack
        links_section = "\n\n----------\n"
        links_section += "🔗 *ACCESO A DETALLES*\n"
        links_section += "----------\n"

        if slack_links and slack_links['updates_links']:
            links_section += "\n*Updates principales:*\n"
            for link_data in slack_links['updates_links'][:3]:
                links_section += f"• <{link_data['link']}|{link_data['user']}: {link_data['text']}>\n"

        if slack_links and slack_links['decisions_links']:
            links_section += "\n*Decisiones/Preguntas:*\n"
            for link_data in slack_links['decisions_links'][:3]:
                links_section += f"• <{link_data['link']}|{link_data['user']}: {link_data['text']}>\n"

        if slack_links and slack_links['risks_links']:
            links_section += "\n*Riesgos mencionados:*\n"
            for link_data in slack_links['risks_links'][:3]:
                links_section += f"• <{link_data['link']}|{link_data['user']}: {link_data['text']}>\n"

        # Ensamblar reporte completo con métricas al inicio y links al final
        full_report = f"📊 *REPORTE DIARIO - #{channel_name}*\n{datetime.now().strftime('%d/%m/%Y')}\n\n{metrics_summary}{formatted_report}{links_section}"

        # Enviar con mejor formato
        slack_client.chat_postMessage(
            channel=dm_channel,
            text=full_report,
            mrkdwn=True
        )
        print("✅ Reporte enviado")
        return True

    except SlackApiError as e:
        print(f"❌ Error: {e.response['error']}")
        return False

def main():
    """Pipeline principal"""
    print("🚀 Iniciando Pulse...")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("-" * 50)

    # 1. Inicializar BD
    init_db()

    # 2. Obtener mensajes
    messages = get_channel_messages(hours=24)

    if not messages:
        print("ℹ️  No hay mensajes nuevos")
        return

    # 3. Guardar en BD
    new_messages = save_messages(messages)

    if new_messages == 0:
        print("ℹ️  No hay actividad nueva desde el último análisis")
        return

    # 4. Enriquecer con nombres reales
    enriched_messages = enrich_messages_with_names(messages)
    print(f"👤 Nombres resueltos para {len(enriched_messages)} mensajes")

    # 5. Extraer updates del proyecto
    updates = extract_project_updates(enriched_messages)
    print(f"📋 Detectados {len(updates)} updates del proyecto")

    # 6. Calcular métricas
    metrics = calculate_metrics(messages, enriched_messages)
    print(f"📊 Métricas calculadas: {metrics['active_users']} usuarios activos")

    # 7. Analizar con Claude
    analysis, slack_links = analyze_with_claude(enriched_messages, metrics, updates)

    if not analysis:
        print("❌ No se pudo generar análisis")
        return

    # 8. Enviar reporte
    send_report_to_lead(analysis, enriched_messages, slack_links)

    print("-" * 50)
    print("✅ Pipeline completado exitosamente")

def get_user_baseline(user_id, channel_id, days=30):
    """Obtiene baseline histórico de un usuario desde Supabase"""
    try:
        supabase = get_supabase_manager()
        return supabase.get_user_baseline(user_id, channel_id, days)
    except Exception as e:
        print(f"❌ Error obteniendo baseline de usuario {user_id}: {e}")
        return None

def get_channel_baseline(channel_id, days=30):
    """Obtiene baseline histórico del canal desde Supabase"""
    try:
        supabase = get_supabase_manager()
        # Por ahora retorna None, se puede implementar más adelante
        return None
    except Exception as e:
        print(f"❌ Error obteniendo baseline del canal {channel_id}: {e}")
        return None

def compare_to_baseline(current_value, baseline_value, metric_name):
    """Compara valor actual con baseline"""
    if not baseline_value or baseline_value == 0:
        return {
            'has_baseline': False,
            'message': f'Sin baseline para {metric_name}',
            'direction': 'sin datos',
            'diff_percentage': 0
        }
    
    diff = current_value - baseline_value
    diff_percentage = (diff / baseline_value) * 100
    
    if diff > 0:
        direction = 'por encima'
    elif diff < 0:
        direction = 'por debajo'
    else:
        direction = 'igual'
    
    return {
        'has_baseline': True,
        'message': f'{metric_name}: {current_value} ({direction} del promedio de {baseline_value:.1f})',
        'direction': direction,
        'diff_percentage': abs(diff_percentage)
    }

if __name__ == "__main__":
    main()
