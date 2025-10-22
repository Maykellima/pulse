import os
import json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase_client import get_supabase_manager, init_supabase

# Cargar variables de entorno
load_dotenv()

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

# ============================================================================
# FUNCIONES ÚTILES DE main.py
# ============================================================================

def get_user_name(user_id):
    """Obtiene nombre real del usuario (con cache)"""
    if user_id in user_cache:
        return user_cache[user_id]

    try:
        result = slack_client.users_info(user=user_id)
        user = result.get('user', {})
        name = user.get('real_name') or user.get('name') or user_id
        username = user.get('name', user_id)

        # Si es un bot, usar display_name o bot name
        if user.get('is_bot'):
            name = user.get('profile', {}).get('display_name') or user.get('profile', {}).get('real_name') or 'Bot'

        user_cache[user_id] = f"{name} (@{username})"
        return user_cache[user_id]
    except Exception as e:
        print(f"⚠️  Error obteniendo usuario {user_id}: {e}")
        return f"Usuario {user_id}"


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
    """Obtiene mensajes del canal de los últimos 10 días hábiles"""
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


# ============================================================================
# HERRAMIENTAS PARA EL AGENTE
# ============================================================================

def analyze_sentiment(messages):
    """
    Analiza el tono emocional del equipo en los mensajes.
    Retorna score 0-100 y palabras clave detectadas.
    """
    try:
        # Keywords por categoría emocional
        frustration_keywords = ['frustrado', 'molesto', 'no funciona', 'otra vez', 'no puedo',
                                'bloqueado', 'stuck', 'no avanza', 'cansado', 'harto']
        enthusiasm_keywords = ['genial', 'excelente', 'perfecto', 'listo', 'completado',
                               'funciona', 'logré', 'conseguí', 'awesome', 'great', '🎉', '✅']
        concern_keywords = ['preocupa', 'problema', 'riesgo', 'urgente', 'crítico',
                           'atrasado', 'retraso', 'concerned', 'worried', 'issue']

        sentiment_scores = {
            'frustration': 0,
            'enthusiasm': 0,
            'concern': 0,
            'neutral': 0
        }

        detected_keywords = []
        total_messages = len(messages)

        if total_messages == 0:
            return {
                'overall_score': 50,
                'sentiment_breakdown': sentiment_scores,
                'detected_keywords': [],
                'summary': 'Sin mensajes para analizar'
            }

        for msg in messages:
            text = msg.lower() if isinstance(msg, str) else msg.get('text', '').lower()

            has_sentiment = False

            # Detectar frustración
            for kw in frustration_keywords:
                if kw in text:
                    sentiment_scores['frustration'] += 1
                    detected_keywords.append(('frustración', kw))
                    has_sentiment = True
                    break

            # Detectar entusiasmo
            for kw in enthusiasm_keywords:
                if kw in text:
                    sentiment_scores['enthusiasm'] += 1
                    detected_keywords.append(('entusiasmo', kw))
                    has_sentiment = True
                    break

            # Detectar preocupación
            for kw in concern_keywords:
                if kw in text:
                    sentiment_scores['concern'] += 1
                    detected_keywords.append(('preocupación', kw))
                    has_sentiment = True
                    break

            if not has_sentiment:
                sentiment_scores['neutral'] += 1

        # Calcular score general (0-100)
        # Fórmula: entusiasmo suma, frustración/preocupación restan
        positive = sentiment_scores['enthusiasm']
        negative = sentiment_scores['frustration'] + sentiment_scores['concern']

        if total_messages > 0:
            score = 50 + ((positive - negative) / total_messages * 50)
            score = max(0, min(100, score))  # Clamp entre 0-100
        else:
            score = 50

        # Crear resumen
        dominant = max(sentiment_scores, key=sentiment_scores.get)
        summary = f"Tono predominante: {dominant} ({sentiment_scores[dominant]}/{total_messages} mensajes)"

        return {
            'overall_score': round(score, 1),
            'sentiment_breakdown': sentiment_scores,
            'detected_keywords': detected_keywords[:10],  # Top 10
            'summary': summary
        }

    except Exception as e:
        print(f"❌ Error en analyze_sentiment: {e}")
        return {
            'overall_score': 50,
            'sentiment_breakdown': {},
            'detected_keywords': [],
            'summary': f'Error: {str(e)}'
        }


def detect_blockers(messages):
    """
    Identifica bloqueos técnicos o de proceso.
    Detecta quién está bloqueado, por qué, y quién puede desbloquearlo.
    """
    try:
        blocker_keywords = ['bloqueado', 'blocked', 'stuck', 'esperando', 'waiting',
                           'no puedo avanzar', 'necesito que', 'dependiendo de']
        unblock_keywords = ['puedo ayudar', 'lo reviso', 'me encargo', 'ya lo hago',
                           'te desbloqueo', 'listo', 'resuelto']

        blockers = []

        for msg in messages:
            if isinstance(msg, str):
                continue

            text = msg.get('text', '').lower()
            user_name = msg.get('user_name', 'Unknown')

            # Detectar bloqueo
            is_blocked = any(kw in text for kw in blocker_keywords)

            if is_blocked:
                # Intentar extraer razón del bloqueo
                reason = text[:150]

                # Intentar detectar quién puede desbloquear (menciones)
                blocked_by = None
                if '<@' in text:
                    # Hay una mención, podría ser quien puede desbloquear
                    blocked_by = "Usuario mencionado en el mensaje"
                elif 'esperando' in text or 'waiting' in text:
                    blocked_by = "Esperando respuesta externa"
                else:
                    blocked_by = "No especificado"

                blockers.append({
                    'who_is_blocked': user_name,
                    'reason': reason,
                    'blocked_by': blocked_by,
                    'timestamp': msg.get('ts', 'unknown')
                })

        # Detectar intentos de desbloqueo
        unblockers = []
        for msg in messages:
            if isinstance(msg, str):
                continue

            text = msg.get('text', '').lower()
            user_name = msg.get('user_name', 'Unknown')

            is_unblocking = any(kw in text for kw in unblock_keywords)

            if is_unblocking:
                unblockers.append({
                    'who_helps': user_name,
                    'context': text[:100]
                })

        return {
            'total_blockers': len(blockers),
            'blockers': blockers,
            'unblockers': unblockers,
            'summary': f"Detectados {len(blockers)} bloqueos activos y {len(unblockers)} intentos de ayuda"
        }

    except Exception as e:
        print(f"❌ Error en detect_blockers: {e}")
        return {
            'total_blockers': 0,
            'blockers': [],
            'unblockers': [],
            'summary': f'Error: {str(e)}'
        }


def classify_urgency(context):
    """
    Evalúa nivel de urgencia REAL basado en contexto.
    Considera: impacto en clientes, deadlines, dependencias.
    """
    try:
        context_lower = context.lower()

        # Indicadores de urgencia crítica
        critical_indicators = ['cliente afectado', 'producción caída', 'perdiendo dinero',
                              'deadline hoy', 'client down', 'production down']

        # Indicadores de urgencia alta
        high_indicators = ['deadline esta semana', 'cliente preguntando', 'bloqueando a otros',
                          'urgente', 'asap', 'prioritario', 'critical']

        # Indicadores de urgencia media
        medium_indicators = ['deadline próximo', 'importante', 'deberíamos', 'hay que']

        # Indicadores de urgencia baja
        low_indicators = ['cuando puedas', 'no urgente', 'eventualmente', 'nice to have']

        urgency_level = 'bajo'
        score = 25
        reasoning = []

        # Evaluar en orden de prioridad
        for indicator in critical_indicators:
            if indicator in context_lower:
                urgency_level = 'crítico'
                score = 100
                reasoning.append(f"Detectado: '{indicator}' - impacto inmediato")
                break

        if urgency_level != 'crítico':
            for indicator in high_indicators:
                if indicator in context_lower:
                    urgency_level = 'alto'
                    score = 75
                    reasoning.append(f"Detectado: '{indicator}' - requiere atención pronta")
                    break

        if urgency_level not in ['crítico', 'alto']:
            for indicator in medium_indicators:
                if indicator in context_lower:
                    urgency_level = 'medio'
                    score = 50
                    reasoning.append(f"Detectado: '{indicator}' - planificar pronto")
                    break

        if urgency_level == 'bajo':
            for indicator in low_indicators:
                if indicator in context_lower:
                    reasoning.append(f"Detectado: '{indicator}' - sin presión temporal")
                    break

        # Detectar deadlines explícitos
        if 'deadline' in context_lower or 'fecha límite' in context_lower:
            reasoning.append("Deadline explícito mencionado")
            if score < 75:
                score = 75
                urgency_level = 'alto'

        # Detectar impacto en clientes
        if 'cliente' in context_lower or 'client' in context_lower:
            reasoning.append("Impacto en clientes mencionado")
            if score < 75:
                score = 75
                urgency_level = 'alto'

        if not reasoning:
            reasoning.append("Sin indicadores claros de urgencia")

        return {
            'urgency_level': urgency_level,
            'score': score,
            'reasoning': reasoning,
            'summary': f"Urgencia {urgency_level.upper()} (score: {score}/100)"
        }

    except Exception as e:
        print(f"❌ Error en classify_urgency: {e}")
        return {
            'urgency_level': 'desconocido',
            'score': 50,
            'reasoning': [f'Error: {str(e)}'],
            'summary': 'No se pudo clasificar urgencia'
        }


def calculate_team_health(team_data):
    """
    Calcula score 0-100 de salud del equipo.
    Considera: distribución de trabajo, colaboración, bloqueos, sentiment, participación.
    """
    try:
        # Componentes del health score
        health_components = {
            'participation': 0,
            'collaboration': 0,
            'workload_distribution': 0,
            'blockers': 0,
            'sentiment': 0
        }

        weights = {
            'participation': 0.25,
            'collaboration': 0.20,
            'workload_distribution': 0.20,
            'blockers': 0.20,
            'sentiment': 0.15
        }

        # 1. Participación (% de miembros activos)
        total_members = team_data.get('total_members', 1)
        active_members = team_data.get('active_members', 0)
        if total_members > 0:
            participation_rate = (active_members / total_members) * 100
            health_components['participation'] = participation_rate

        # 2. Colaboración (mensajes con menciones, respuestas)
        total_messages = team_data.get('total_messages', 1)
        collaborative_messages = team_data.get('collaborative_messages', 0)
        if total_messages > 0:
            collaboration_rate = (collaborative_messages / total_messages) * 100
            health_components['collaboration'] = min(collaboration_rate, 100)

        # 3. Distribución de carga
        # Usar coeficiente de variación de mensajes por usuario
        messages_per_user = team_data.get('messages_per_user', [])
        # Asegurar que sea una lista
        if not isinstance(messages_per_user, list):
            messages_per_user = []
        if len(messages_per_user) > 1:
            import statistics
            # Convertir a números (en caso de que vengan strings)
            messages_per_user = [float(x) if isinstance(x, (int, float, str)) and str(x).replace('.','').replace('-','').isdigit() else 0 for x in messages_per_user]
            # Filtrar valores válidos
            messages_per_user = [x for x in messages_per_user if x >= 0]

            if len(messages_per_user) > 1:
                mean = statistics.mean(messages_per_user)
                stdev = statistics.stdev(messages_per_user)
                cv = (stdev / mean) if mean > 0 else 0
                # CV bajo = buena distribución (score alto)
                # CV > 1 = distribución muy desigual (score bajo)
                distribution_score = max(0, 100 - (cv * 50))
                health_components['workload_distribution'] = distribution_score
            else:
                health_components['workload_distribution'] = 50
        else:
            health_components['workload_distribution'] = 50

        # 4. Bloqueos (menos bloqueos = mejor)
        total_blockers = team_data.get('total_blockers', 0)
        if total_blockers == 0:
            health_components['blockers'] = 100
        elif total_blockers <= 2:
            health_components['blockers'] = 70
        elif total_blockers <= 5:
            health_components['blockers'] = 40
        else:
            health_components['blockers'] = 20

        # 5. Sentiment score
        sentiment_score = team_data.get('sentiment_score', 50)
        health_components['sentiment'] = sentiment_score

        # Calcular score total ponderado
        total_score = sum(
            health_components[component] * weights[component]
            for component in health_components
        )

        # Determinar estado
        if total_score >= 80:
            status = 'EXCELENTE'
            emoji = '🟢'
        elif total_score >= 60:
            status = 'BUENO'
            emoji = '🟡'
        elif total_score >= 40:
            status = 'REGULAR'
            emoji = '🟠'
        else:
            status = 'CRÍTICO'
            emoji = '🔴'

        return {
            'overall_score': round(total_score, 1),
            'status': status,
            'emoji': emoji,
            'components': health_components,
            'summary': f"Salud del equipo: {emoji} {status} ({round(total_score, 1)}/100)"
        }

    except Exception as e:
        print(f"❌ Error en calculate_team_health: {e}")
        return {
            'overall_score': 50,
            'status': 'DESCONOCIDO',
            'emoji': '❓',
            'components': {},
            'summary': f'Error: {str(e)}'
        }


def extract_key_decisions(messages):
    """
    Extrae decisiones importantes tomadas.
    Retorna: qué se decidió, quién lo decidió, por qué, y próximos pasos.
    """
    try:
        decision_indicators = ['decidimos', 'vamos a', 'haremos', 'acordamos', 'decided to',
                              'we will', 'we are going to', 'agreed to']
        question_indicators = ['?', 'deberíamos', 'qué hacemos con', 'should we']

        decisions_made = []
        decisions_pending = []

        for msg in messages:
            if isinstance(msg, str):
                continue

            text = msg.get('text', '')
            text_lower = text.lower()
            user_name = msg.get('user_name', 'Unknown')

            # Detectar decisión tomada
            has_decision = any(indicator in text_lower for indicator in decision_indicators)

            if has_decision:
                # Intentar extraer "por qué"
                reasoning = None
                if 'porque' in text_lower or 'ya que' in text_lower or 'because' in text_lower:
                    reasoning = text[:200]

                # Intentar extraer próximos pasos
                next_steps = None
                if 'siguiente' in text_lower or 'next' in text_lower or 'luego' in text_lower:
                    next_steps = text[:200]

                decisions_made.append({
                    'what': text[:150],
                    'who_decided': user_name,
                    'reasoning': reasoning or 'No especificado',
                    'next_steps': next_steps or 'No especificado',
                    'timestamp': msg.get('ts', 'unknown')
                })

            # Detectar decisión pendiente (pregunta)
            has_question = any(indicator in text_lower for indicator in question_indicators)

            if has_question and not has_decision:
                decisions_pending.append({
                    'what': text[:150],
                    'who_asks': user_name,
                    'timestamp': msg.get('ts', 'unknown')
                })

        return {
            'total_decisions_made': len(decisions_made),
            'total_decisions_pending': len(decisions_pending),
            'decisions_made': decisions_made[:5],  # Top 5
            'decisions_pending': decisions_pending[:5],  # Top 5
            'summary': f"Decisiones tomadas: {len(decisions_made)}, Pendientes: {len(decisions_pending)}"
        }

    except Exception as e:
        print(f"❌ Error en extract_key_decisions: {e}")
        return {
            'total_decisions_made': 0,
            'total_decisions_pending': 0,
            'decisions_made': [],
            'decisions_pending': [],
            'summary': f'Error: {str(e)}'
        }


# ============================================================================
# DEFINICIÓN DE HERRAMIENTAS PARA ANTHROPIC
# ============================================================================

TOOLS = [
    {
        "name": "analyze_sentiment",
        "description": "Analiza el tono emocional del equipo en los mensajes (frustración, entusiasmo, preocupación, neutral). Retorna score 0-100 y palabras clave detectadas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Lista de mensajes o textos a analizar",
                    "items": {"type": "string"}
                }
            },
            "required": ["messages"]
        }
    },
    {
        "name": "detect_blockers",
        "description": "Identifica bloqueos técnicos o de proceso. Detecta quién está bloqueado, por qué, y quién puede desbloquearlo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Lista de mensajes enriquecidos con user_name, text, ts"
                }
            },
            "required": ["messages"]
        }
    },
    {
        "name": "classify_urgency",
        "description": "Evalúa nivel de urgencia REAL (crítico/alto/medio/bajo) basado en contexto, no solo palabras. Considera: impacto en clientes, deadlines, dependencias.",
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Texto o contexto a analizar para determinar urgencia"
                }
            },
            "required": ["context"]
        }
    },
    {
        "name": "calculate_team_health",
        "description": "Calcula score 0-100 de salud del equipo. Considera: distribución de trabajo, colaboración, bloqueos, sentiment, participación.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_data": {
                    "type": "object",
                    "description": "Objeto con métricas del equipo: total_members, active_members, total_messages, collaborative_messages, messages_per_user, total_blockers, sentiment_score"
                }
            },
            "required": ["team_data"]
        }
    },
    {
        "name": "extract_key_decisions",
        "description": "Extrae decisiones importantes tomadas con contexto completo: qué se decidió, quién lo decidió, por qué, y próximos pasos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Lista de mensajes enriquecidos"
                }
            },
            "required": ["messages"]
        }
    }
]


# ============================================================================
# PROCESADOR DE HERRAMIENTAS
# ============================================================================

def process_tool_call(tool_name, tool_input):
    """Ejecuta la herramienta solicitada y retorna el resultado"""
    try:
        if tool_name == "analyze_sentiment":
            return analyze_sentiment(tool_input['messages'])

        elif tool_name == "detect_blockers":
            return detect_blockers(tool_input['messages'])

        elif tool_name == "classify_urgency":
            return classify_urgency(tool_input['context'])

        elif tool_name == "calculate_team_health":
            return calculate_team_health(tool_input['team_data'])

        elif tool_name == "extract_key_decisions":
            return extract_key_decisions(tool_input['messages'])

        else:
            return {"error": f"Herramienta desconocida: {tool_name}"}

    except Exception as e:
        print(f"❌ Error ejecutando {tool_name}: {e}")
        return {"error": str(e)}


# ============================================================================
# LOOP AGÉNTICO
# ============================================================================

def run_agentic_analysis(enriched_messages):
    """
    Ejecuta el loop agéntico con Claude.
    Claude usa las herramientas para analizar los mensajes y generar un reporte.
    """
    try:
        # Preparar contexto inicial
        channel_name = "proyecto"
        try:
            channel_info = slack_client.conversations_info(channel=CHANNEL_ID)
            channel_name = channel_info['channel']['name']
        except Exception as e:
            print(f"⚠️  No se pudo obtener nombre del canal: {e}")

        # Filtrar mensajes reales (no automáticos)
        real_messages = []
        for msg in enriched_messages:
            text = msg.get('text', '')
            if (text and
                'se ha unido al canal' not in text.lower() and
                'has joined' not in text.lower() and
                len(text) > 15):
                real_messages.append(msg)

        if not real_messages:
            return None

        # Preparar datos del equipo para análisis
        active_users = set(m['user_id'] for m in real_messages)

        # Obtener total de miembros
        try:
            channel_members = slack_client.conversations_members(channel=CHANNEL_ID)
            total_members = len(channel_members['members'])
        except:
            total_members = len(active_users)

        # Contar mensajes por usuario
        messages_per_user = {}
        for msg in real_messages:
            user_id = msg['user_id']
            messages_per_user[user_id] = messages_per_user.get(user_id, 0) + 1

        # Mensajes colaborativos (con menciones o respuestas)
        collaborative_messages = sum(1 for m in real_messages if '<@' in m.get('text', '') or '@' in m.get('text', ''))

        # Preparar conversaciones para el contexto
        conversations = []
        for msg in real_messages[:50]:  # Limitar a últimos 50 para no exceder tokens
            conversations.append(f"*{msg['user_name']}*: {msg['text']}")
        message_context = "\n".join(conversations)

        # Prompt inicial para Claude
        initial_prompt = f"""Eres un analista ejecutivo experto. Analiza la actividad del canal #{channel_name} de los últimos 10 días hábiles.

DATOS DEL CANAL:
----------
Total mensajes: {len(real_messages)}
Usuarios activos: {len(active_users)}
Total miembros: {total_members}

CONVERSACIONES RECIENTES:
----------
{message_context}
----------

TU TAREA:
1. USA LAS HERRAMIENTAS disponibles para analizar los mensajes en detalle
2. Detecta sentiment, bloqueos, urgencias, decisiones, y salud del equipo
3. Genera un reporte ejecutivo COMPLETO y ESPECÍFICO con nombres, números, y contexto

FORMATO CRÍTICO - SLACK mrkdwn:
- NO uses # para títulos (Slack no los reconoce)
- USA asteriscos para negrita: *TEXTO EN NEGRITA*
- Para títulos/secciones: usa emojis + *texto en negrita*
- Ejemplo correcto: "🎯 *ESTADO DEL PROYECTO*"
- Ejemplo INCORRECTO: "## 🎯 ESTADO DEL PROYECTO" o "# Estado"
- Para subtítulos: usa "  • *Subtítulo:*" (con bullet point)
- Separa secciones con líneas: ----------

ESTRUCTURA DEL REPORTE:
----------
🎯 *ESTADO DEL PROYECTO*
  • *Status:* [descripción]
  • *Progreso:* [detalles específicos]
  • *Nivel de urgencia:* [ALTO/MEDIO/BAJO con score y razón]

----------
📊 *SALUD DEL EQUIPO*
  • *Score general:* [número/100 con emoji]
  • *Sentiment:* [Neutral/Positivo/Negativo con score]
  • *Participación:* [X de Y miembros activos]
  • *Impacto:* [problemas detectados]

----------
🚧 *BLOQUEOS Y RIESGOS CRÍTICOS*
  *Bloqueos Activos:*
    • [Nombre]: [qué lo bloquea]
    • [Responsable desbloqueador]: [quién puede ayudar]

  *Ausencias por Emergencias Médicas:*
    • [Nombre]: [situación]
    • *Impacto:* [consecuencias en el proyecto]

  *Problemas Técnicos:*
    • [descripción específica del problema]

----------
✅ *DECISIONES CLAVE*
  *Tomadas:*
    • [decisión con contexto]

  *Pendientes:*
    • [decisión pendiente]

----------
👥 *PARTICIPACIÓN Y COLABORACIÓN*
  • Usuarios activos: [X de Y]
  • Promedio mensajes: [número por usuario]
  • Patrones detectados: [insight específico]

----------
💡 *RECOMENDACIONES*
  • [acción específica 1]
  • [acción específica 2]

REGLAS ESTRICTAS:
- NUNCA uses #, ##, ### para títulos
- USA solo *negrita* y emojis para estructura
- SIEMPRE incluye nombres específicos y números
- NO inventes información, usa solo lo detectado por las herramientas
- Sé conciso pero completo"""

        # Iniciar conversación con Claude
        messages = [{"role": "user", "content": initial_prompt}]

        print("🤖 Iniciando análisis agéntico con Claude...")

        # Loop agéntico
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"🔄 Iteración {iteration}/{max_iterations}")

            # Llamar a Claude con herramientas
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=TOOLS,
                messages=messages
            )

            # Verificar si Claude quiere usar herramientas
            if response.stop_reason == "tool_use":
                # Procesar todas las herramientas solicitadas
                tool_results = []

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_id = content_block.id

                        print(f"  🔧 Ejecutando herramienta: {tool_name}")

                        # Ejecutar herramienta
                        result = process_tool_call(tool_name, tool_input)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": json.dumps(result, ensure_ascii=False)
                        })

                # Añadir respuesta de Claude a mensajes
                messages.append({"role": "assistant", "content": response.content})

                # Añadir resultados de herramientas
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                # Claude terminó, extraer reporte final
                print("✅ Análisis completado")

                # Extraer texto del reporte
                report_text = ""
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        report_text += content_block.text

                return report_text

            else:
                print(f"⚠️  Stop reason inesperado: {response.stop_reason}")
                break

        print("⚠️  Se alcanzó el máximo de iteraciones")
        return None

    except Exception as e:
        print(f"❌ Error en análisis agéntico: {e}")
        return None


# ============================================================================
# ENVÍO DE REPORTE
# ============================================================================

def send_report_to_lead(report, enriched_messages):
    """Envía reporte por DM al líder del proyecto"""
    try:
        # Obtener nombre del canal
        try:
            channel_info = slack_client.conversations_info(channel=CHANNEL_ID)
            channel_name = channel_info['channel']['name']
        except:
            channel_name = "proyecto"

        # Abrir conversación DM
        dm_response = slack_client.conversations_open(users=[LEAD_USER_ID])
        dm_channel = dm_response['channel']['id']

        # Generar métricas resumidas
        real_messages = [m for m in enriched_messages if len(m.get('text', '')) > 15]
        active_users = len(set(m['user_id'] for m in real_messages))

        try:
            channel_members = slack_client.conversations_members(channel=CHANNEL_ID)
            total_members = len(channel_members['members'])
        except:
            total_members = active_users

        metrics_summary = f"""📊 *MÉTRICAS CLAVE (Últimos 10 días hábiles)*
----------
📨 Mensajes: {len(real_messages)}
👥 Usuarios activos: {active_users} de {total_members}
----------

"""

        # Formatear reporte
        formatted_report = report.replace('**', '*')

        # Ensamblar reporte completo
        full_report = f"""📊 *REPORTE AGÉNTICO - #{channel_name}*
{datetime.now().strftime('%d/%m/%Y')}

{metrics_summary}{formatted_report}

----------
🤖 Generado por Pulse Agent con Claude AI
"""

        # Enviar
        slack_client.chat_postMessage(
            channel=dm_channel,
            text=full_report,
            mrkdwn=True
        )
        print("✅ Reporte enviado al líder del proyecto")
        return True

    except SlackApiError as e:
        print(f"❌ Error enviando reporte: {e.response['error']}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Pipeline principal del agente"""
    print("🚀 Iniciando Pulse Agent (Sistema Agéntico)...")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("-" * 50)

    # 1. Obtener mensajes del canal
    messages = get_channel_messages()

    if not messages:
        print("ℹ️  No hay mensajes para analizar")
        return

    # 2. Enriquecer con nombres reales
    enriched_messages = enrich_messages_with_names(messages)
    print(f"👤 Nombres resueltos para {len(enriched_messages)} mensajes")

    # 3. Ejecutar análisis agéntico
    report = run_agentic_analysis(enriched_messages)

    if not report:
        print("❌ No se pudo generar el reporte")
        return

    # 4. Enviar reporte al líder
    send_report_to_lead(report, enriched_messages)

    print("-" * 50)
    print("✅ Pipeline agéntico completado exitosamente")


if __name__ == "__main__":
    main()
