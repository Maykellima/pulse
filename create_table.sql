-- =============================================================================
-- PULSE - Crear tabla slack-channel-project-update
-- =============================================================================

-- Crear la tabla principal
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

-- =============================================================================
-- ÍNDICES PARA OPTIMIZACIÓN
-- =============================================================================

-- Índices básicos
CREATE INDEX idx_message_id ON "slack-channel-project-update"(message_id);
CREATE INDEX idx_channel_id ON "slack-channel-project-update"(channel_id);
CREATE INDEX idx_timestamp ON "slack-channel-project-update"(timestamp);

-- Índices adicionales para análisis
CREATE INDEX idx_user_id ON "slack-channel-project-update"(user_id);
CREATE INDEX idx_is_update ON "slack-channel-project-update"(is_update);
CREATE INDEX idx_urgency_level ON "slack-channel-project-update"(urgency_level);
CREATE INDEX idx_contains_decision ON "slack-channel-project-update"(contains_decision);
CREATE INDEX idx_contains_blocker ON "slack-channel-project-update"(contains_blocker);

-- Índice compuesto para consultas frecuentes
CREATE INDEX idx_channel_timestamp ON "slack-channel-project-update"(channel_id, timestamp DESC);

-- =============================================================================
-- FUNCIÓN Y TRIGGER PARA UPDATED_AT
-- =============================================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para updated_at
CREATE TRIGGER update_slack_messages_updated_at 
    BEFORE UPDATE ON "slack-channel-project-update" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- POLÍTICAS DE SEGURIDAD (RLS)
-- =============================================================================

-- Habilitar RLS
ALTER TABLE "slack-channel-project-update" ENABLE ROW LEVEL SECURITY;

-- Política para service role (usado por la aplicación)
CREATE POLICY "Allow all operations for service role" ON "slack-channel-project-update"
    FOR ALL USING (auth.role() = 'service_role');

-- =============================================================================
-- COMENTARIOS EN LA TABLA
-- =============================================================================

COMMENT ON TABLE "slack-channel-project-update" IS 'Tabla principal para almacenar mensajes de Slack del canal del proyecto';
COMMENT ON COLUMN "slack-channel-project-update".id IS 'Identificador único UUID';
COMMENT ON COLUMN "slack-channel-project-update".message_id IS 'ID único del mensaje en Slack';
COMMENT ON COLUMN "slack-channel-project-update".channel_id IS 'ID del canal de Slack';
COMMENT ON COLUMN "slack-channel-project-update".user_id IS 'ID del usuario que envió el mensaje';
COMMENT ON COLUMN "slack-channel-project-update".user_name IS 'Nombre real del usuario';
COMMENT ON COLUMN "slack-channel-project-update".text IS 'Contenido del mensaje';
COMMENT ON COLUMN "slack-channel-project-update".timestamp IS 'Timestamp del mensaje en Slack';
COMMENT ON COLUMN "slack-channel-project-update".thread_ts IS 'Timestamp del hilo si es una respuesta';
COMMENT ON COLUMN "slack-channel-project-update".reply_count IS 'Número de respuestas en el hilo';
COMMENT ON COLUMN "slack-channel-project-update".message_type IS 'Tipo de mensaje: message, bot_message, system';
COMMENT ON COLUMN "slack-channel-project-update".is_update IS 'Si el mensaje es un update del proyecto';
COMMENT ON COLUMN "slack-channel-project-update".sentiment_score IS 'Score de sentimiento del mensaje (-1 a 1)';
COMMENT ON COLUMN "slack-channel-project-update".urgency_level IS 'Nivel de urgencia detectado';
COMMENT ON COLUMN "slack-channel-project-update".contains_decision IS 'Si el mensaje contiene una decisión';
COMMENT ON COLUMN "slack-channel-project-update".contains_blocker IS 'Si el mensaje menciona un bloqueo';
