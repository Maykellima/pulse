# Pulse

Sistema autónomo de análisis de proyectos que monitorea Slack y genera reportes proactivos usando IA.

## 🚀 Características

- **Monitoreo automático** de canales de Slack
- **Análisis agéntico** con Claude AI
- **Base de datos en la nube** con Supabase PostgreSQL
- **Reportes ejecutivos** automáticos
- **Detección de bloqueos** y riesgos
- **Análisis de sentimiento** del equipo
- **Métricas de salud** del proyecto

## 📋 Setup Inicial

### 1. Configuración del entorno

```bash
# Clonar el repositorio
git clone <tu-repo>
cd pulse

# Instalar dependencias
pip3 install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Configuración de Supabase

1. **Crear proyecto en Supabase:**
   - Ve a [supabase.com](https://supabase.com/)
   - Crea un nuevo proyecto
   - Anota la URL y las credenciales

2. **Configurar variables de entorno:**
   ```bash
   # En tu archivo .env
   SUPABASE_URL=https://tu-proyecto.supabase.co
   DATABASE_URL=postgresql://postgres:tu-password@db.tu-proyecto.supabase.co:5432/postgres
   ```

3. **Ejecutar setup inicial:**
   ```bash
   python3 setup_supabase.py
   ```

### 3. Configuración de Slack

1. **Crear app de Slack:**
   - Ve a [api.slack.com/apps](https://api.slack.com/apps)
   - Crea una nueva app
   - Instala el bot en tu workspace

2. **Configurar permisos:**
   - `channels:history` - Leer mensajes del canal
   - `users:read` - Obtener información de usuarios
   - `chat:write` - Enviar mensajes

3. **Obtener credenciales:**
   ```bash
   # En tu archivo .env
   SLACK_BOT_TOKEN=xoxb-tu-token-aqui
   PROJECT_CHANNEL_ID=C1234567890
   PROJECT_LEAD_USER_ID=U1234567890
   ```

### 4. Configuración de Anthropic

1. **Crear cuenta en Anthropic:**
   - Ve a [console.anthropic.com](https://console.anthropic.com/)
   - Genera una API key

2. **Configurar variable:**
   ```bash
   # En tu archivo .env
   ANTHROPIC_API_KEY=sk-ant-tu-api-key-aqui
   ```

## 🏃‍♂️ Ejecución

### Setup inicial (solo la primera vez)
```bash
python3 setup_supabase.py
```

### Migración de datos existentes (si tienes SQLite)
```bash
python3 migrate_to_supabase.py
```

### Ejecutar el sistema
```bash
# Sistema tradicional
python3 main.py

# Sistema agéntico (recomendado)
python3 agent_main.py

# Pruebas
python3 test_agent.py
```

## 📊 Estructura de la Base de Datos

El sistema crea automáticamente las siguientes tablas en Supabase:

- **messages**: Mensajes de Slack almacenados
- **analysis_reports**: Reportes de análisis generados
- **users**: Información de usuarios del equipo
- **daily_metrics**: Métricas diarias del proyecto

## 🔧 Troubleshooting

### Error de conexión a Supabase
- Verifica que las credenciales en `.env` sean correctas
- Asegúrate de que tu proyecto Supabase esté activo
- Verifica la whitelist de IPs si aplica

### Error de conexión a Slack
- Verifica que el bot tenga los permisos necesarios
- Confirma que el bot esté instalado en el workspace
- Verifica que el canal ID sea correcto

### Error de conexión a Anthropic
- Verifica que la API key sea válida
- Confirma que tengas créditos disponibles

## 📁 Estructura del Proyecto

```
pulse/
├── main.py                 # Sistema principal
├── agent_main.py          # Sistema agéntico
├── database.py            # Gestión de Supabase
├── setup_supabase.py      # Setup inicial
├── migrate_to_supabase.py # Migración de datos
├── test_agent.py          # Pruebas del sistema
├── requirements.txt       # Dependencias
├── .env.example          # Variables de entorno
└── README.md             # Este archivo
```

## 🤖 Sistema Agéntico

El sistema agéntico (`agent_main.py`) utiliza Claude AI con herramientas especializadas para:

- **Análisis de sentimiento** del equipo
- **Detección de bloqueos** técnicos
- **Clasificación de urgencia** de tareas
- **Cálculo de salud** del equipo
- **Extracción de decisiones** importantes

## 📈 Próximas Funcionalidades

- [ ] Programación automática de reportes
- [ ] Integración con más canales de comunicación
- [ ] Dashboard web para visualización
- [ ] Alertas proactivas por email/Slack
- [ ] Análisis predictivo de riesgos
