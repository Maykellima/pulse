# 🚀 Pulse - Sistema de Análisis Automático del Proyecto

## 📋 ¿Qué es Pulse?

**Pulse** es un asistente de IA que analiza automáticamente las conversaciones del canal de Slack **#hornblower-internal** y genera reportes ejecutivos semanales sobre el estado del proyecto.

---

## ✨ ¿Qué hace?

Cada vez que se ejecuta, Pulse:

1. **📨 Lee** los últimos 7 días hábiles de mensajes del canal
2. **🤖 Analiza** con Claude AI (Anthropic) usando 5 herramientas especializadas:
   - Análisis de sentimiento del equipo
   - Detección de bloqueos técnicos
   - Clasificación de urgencia de tareas
   - Cálculo de salud del equipo
   - Extracción de decisiones clave

3. **📊 Genera** un reporte ejecutivo completo con:
   - Estado del proyecto
   - Salud del equipo
   - Bloqueos detectados
   - Decisiones tomadas
   - Recomendaciones accionables

4. **💬 Envía** el reporte por mensaje directo en Slack

---

## 🎯 Beneficios para el Equipo

✅ **Visibilidad automática** - No más "¿en qué estamos?"
✅ **Detección temprana** - Identifica bloqueos antes de que escalen
✅ **Memoria del proyecto** - Histórico completo en base de datos
✅ **Ahorro de tiempo** - Sin necesidad de status meetings largos
✅ **Análisis objetivo** - IA sin sesgos evalúa el estado real

---

## 🔧 Tecnologías Utilizadas

- **Slack API** - Obtención de mensajes del canal
- **Anthropic Claude AI** - Análisis avanzado con IA (claude-sonnet-4)
- **Supabase PostgreSQL** - Base de datos en la nube para histórico
- **Python** - Backend del sistema

---

## 📅 ¿Cómo se usa?

**Opción 1: Ejecución Local**
```bash
python3 agent_main.py
```

**Opción 2: GitHub Actions (próximamente)**
- Click en botón "Run workflow" desde GitHub
- Reportes automáticos programados (si lo configuramos)

---

## 📊 ¿Qué información analiza?

### Del Canal #hornblower-internal:
- ✅ Últimos 7 días hábiles (lunes a viernes, incluyendo hoy)
- ✅ Todos los mensajes de miembros del equipo
- ✅ Threads y respuestas
- ✅ Menciones y colaboraciones

### NO analiza:
- ❌ Mensajes de bots
- ❌ Mensajes muy cortos (< 15 caracteres)
- ❌ Mensajes anteriores a los 7 días

---

## 🗄️ Datos e Histórico

- **Supabase** almacena todos los mensajes incrementalmente
- **No hay duplicados** - Sistema inteligente de deduplicación
- **Histórico de largo plazo** - Todos los mensajes se guardan para futuras consultas
- **No se compara con histórico** - Reportes enfocados solo en la semana actual

---

## 📈 Ejemplo de Reporte

El reporte incluye secciones como:

```
📊 MÉTRICAS CLAVE (Últimos 7 días hábiles)
----------
📨 Mensajes: 25
👥 Usuarios activos: 6 de 9

🎯 ESTADO DEL PROYECTO
  • Status: En progreso activo con múltiples frentes
  • Progreso: Backend API completado, Frontend en desarrollo
  • Nivel de urgencia: MEDIO (score: 6/10)

🚧 BLOQUEOS Y RIESGOS
  • José bloqueado en integración de Auth0
  • Dependencia externa: Esperando API de terceros

✅ DECISIONES CLAVE
  • Migrar a PostgreSQL (acordado el lunes)
  • Sprint review el viernes a las 15h

💡 RECOMENDACIONES
  1. Priorizar desbloqueo de José con Auth0
  2. Programar sync con equipo de backend
```

---

## 🔒 Privacidad y Seguridad

- ✅ Solo analiza el canal **#hornblower-internal**
- ✅ Reportes solo visibles para el líder del proyecto
- ✅ Credenciales seguras en variables de entorno
- ✅ Base de datos protegida con autenticación
- ✅ Sin acceso a DMs privados

---

## 🎉 Estado Actual

**✅ Sistema Completamente Funcional**

Última ejecución exitosa:
- 25 mensajes analizados (últimos 7 días hábiles)
- 25 mensajes guardados en Supabase
- Reporte generado y enviado
- Todas las integraciones funcionando

---

## 🚀 Próximos Pasos (Opcionales)

- [ ] Automatización diaria/semanal vía GitHub Actions
- [ ] Dashboard web para visualizar tendencias
- [ ] Análisis de múltiples canales
- [ ] Alertas proactivas por Slack
- [ ] Comparación de semanas (trends)

---

## 👥 ¿Preguntas?

Si tienen dudas sobre:
- ¿Qué datos analiza?
- ¿Cómo funciona la IA?
- ¿Puedo ver mi histórico?
- ¿Cómo se protege la privacidad?

**Contactar a:** Maykel Lima (@maykel)

---

## 📚 Recursos

- **Repositorio:** https://github.com/Maykellima/pulse
- **Bot en Slack:** @pulse
- **Canal monitoreado:** #hornblower-internal

---

*Sistema desarrollado con Claude Code - Octubre 2025*
