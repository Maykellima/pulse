-- =============================================================================
-- PULSE - Esquema de Base de Datos para Supabase
-- =============================================================================

-- Tabla principal de mensajes de Slack
CREATE TABLE "slack-channel-project-update" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id TEXT UNIQUE NOT NULL,
  channel_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  user_name TEXT,
  text TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  thread_ts TEXT,
  reply_count INTEGER DEFAULT 0,
  
  -- Campos adicionales para análisis
  message_type TEXT DEFAULT 'message', -- 'message', 'bot_message', 'system'
  is_update BOOLEAN DEFAULT FALSE, -- Si es un update del proyecto
  sentiment_score REAL, -- Score de sentimiento (-1 a 1)
  urgency_level TEXT, -- 'low', 'medium', 'high', 'critical'
  contains_decision BOOLEAN DEFAULT FALSE, -- Si contiene una decisión
  contains_blocker BOOLEAN DEFAULT FALSE, -- Si menciona un bloqueo
  
  -- Metadatos
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para optimización
CREATE INDEX idx_message_id ON "slack-channel-project-update"(message_id);
CREATE INDEX idx_channel_id ON "slack-channel-project-update"(channel_id);
CREATE INDEX idx_timestamp ON "slack-channel-project-update"(timestamp);
CREATE INDEX idx_user_id ON "slack-channel-project-update"(user_id);
CREATE INDEX idx_is_update ON "slack-channel-project-update"(is_update);
CREATE INDEX idx_urgency_level ON "slack-channel-project-update"(urgency_level);
CREATE INDEX idx_contains_decision ON "slack-channel-project-update"(contains_decision);
CREATE INDEX idx_contains_blocker ON "slack-channel-project-update"(contains_blocker);

-- Índice compuesto para consultas frecuentes
CREATE INDEX idx_channel_timestamp ON "slack-channel-project-update"(channel_id, timestamp DESC);

-- =============================================================================
-- TABLA DE USUARIOS
-- =============================================================================

CREATE TABLE "slack-users" (
  user_id TEXT PRIMARY KEY,
  real_name TEXT,
  username TEXT,
  email TEXT,
  is_bot BOOLEAN DEFAULT FALSE,
  is_admin BOOLEAN DEFAULT FALSE,
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_active TIMESTAMPTZ DEFAULT NOW(),
  total_messages INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para usuarios
CREATE INDEX idx_users_username ON "slack-users"(username);
CREATE INDEX idx_users_last_active ON "slack-users"(last_active DESC);

-- =============================================================================
-- TABLA DE ANÁLISIS DIARIOS
-- =============================================================================

CREATE TABLE "daily-analysis" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id TEXT NOT NULL,
  analysis_date DATE NOT NULL,
  
  -- Métricas del día
  total_messages INTEGER DEFAULT 0,
  active_users INTEGER DEFAULT 0,
  updates_count INTEGER DEFAULT 0,
  decisions_count INTEGER DEFAULT 0,
  blockers_count INTEGER DEFAULT 0,
  
  -- Scores
  sentiment_score REAL, -- Promedio del día
  team_health_score REAL, -- 0-100
  urgency_score REAL, -- 0-100
  
  -- Reporte generado
  report_content TEXT,
  report_sent BOOLEAN DEFAULT FALSE,
  
  -- Metadatos
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraint único por canal y fecha
  UNIQUE(channel_id, analysis_date)
);

-- Índices para análisis diarios
CREATE INDEX idx_daily_analysis_date ON "daily-analysis"(analysis_date DESC);
CREATE INDEX idx_daily_analysis_channel ON "daily-analysis"(channel_id);
CREATE INDEX idx_daily_analysis_sent ON "daily-analysis"(report_sent);

-- =============================================================================
-- TABLA DE MÉTRICAS DE USUARIOS
-- =============================================================================

CREATE TABLE "user-metrics" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  metric_date DATE NOT NULL,
  
  -- Métricas del usuario
  messages_count INTEGER DEFAULT 0,
  updates_count INTEGER DEFAULT 0,
  decisions_count INTEGER DEFAULT 0,
  questions_count INTEGER DEFAULT 0,
  answers_count INTEGER DEFAULT 0,
  
  -- Scores
  sentiment_score REAL,
  collaboration_score REAL, -- Basado en menciones y respuestas
  
  -- Metadatos
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Constraint único por usuario, canal y fecha
  UNIQUE(user_id, channel_id, metric_date)
);

-- Índices para métricas de usuarios
CREATE INDEX idx_user_metrics_user ON "user-metrics"(user_id);
CREATE INDEX idx_user_metrics_date ON "user-metrics"(metric_date DESC);
CREATE INDEX idx_user_metrics_channel ON "user-metrics"(channel_id);

-- =============================================================================
-- TABLA DE CONFIGURACIÓN
-- =============================================================================

CREATE TABLE "pulse-config" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_key TEXT UNIQUE NOT NULL,
  config_value TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Configuraciones por defecto
INSERT INTO "pulse-config" (config_key, config_value, description) VALUES
('analysis_interval_hours', '24', 'Intervalo de análisis en horas'),
('business_days_analysis', '10', 'Días hábiles para análisis histórico'),
('sentiment_threshold', '0.3', 'Umbral para clasificar sentimiento'),
('urgency_keywords', 'urgente,critical,deadline,cliente', 'Palabras clave de urgencia'),
('update_keywords', 'update,actualización,progreso,avance,completado', 'Palabras clave de updates');

-- =============================================================================
-- FUNCIONES Y TRIGGERS
-- =============================================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_slack_messages_updated_at 
    BEFORE UPDATE ON "slack-channel-project-update" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_slack_users_updated_at 
    BEFORE UPDATE ON "slack-users" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_analysis_updated_at 
    BEFORE UPDATE ON "daily-analysis" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pulse_config_updated_at 
    BEFORE UPDATE ON "pulse-config" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VISTAS ÚTILES
-- =============================================================================

-- Vista de mensajes con información de usuario
CREATE VIEW "messages_with_users" AS
SELECT 
    m.*,
    u.real_name,
    u.username,
    u.is_bot,
    u.is_admin
FROM "slack-channel-project-update" m
LEFT JOIN "slack-users" u ON m.user_id = u.user_id;

-- Vista de métricas diarias resumidas
CREATE VIEW "daily_summary" AS
SELECT 
    analysis_date,
    channel_id,
    total_messages,
    active_users,
    updates_count,
    decisions_count,
    blockers_count,
    sentiment_score,
    team_health_score,
    urgency_score,
    CASE 
        WHEN team_health_score >= 80 THEN 'EXCELENTE'
        WHEN team_health_score >= 60 THEN 'BUENO'
        WHEN team_health_score >= 40 THEN 'REGULAR'
        ELSE 'CRÍTICO'
    END as health_status
FROM "daily-analysis"
ORDER BY analysis_date DESC;

-- =============================================================================
-- POLÍTICAS DE SEGURIDAD (RLS)
-- =============================================================================

-- Habilitar RLS en todas las tablas
ALTER TABLE "slack-channel-project-update" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "slack-users" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "daily-analysis" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "user-metrics" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "pulse-config" ENABLE ROW LEVEL SECURITY;

-- Políticas básicas (ajustar según necesidades)
CREATE POLICY "Allow all operations for service role" ON "slack-channel-project-update"
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow all operations for service role" ON "slack-users"
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow all operations for service role" ON "daily-analysis"
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow all operations for service role" ON "user-metrics"
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow all operations for service role" ON "pulse-config"
    FOR ALL USING (auth.role() = 'service_role');
