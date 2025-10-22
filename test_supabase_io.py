import os
from supabase import create_client
from datetime import datetime

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
assert url and key, "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env"

sb = create_client(url, key)

row = {
    "message_id": f"{datetime.utcnow().timestamp():.6f}",
    "channel_id": os.getenv("PROJECT_CHANNEL_ID") or "C_TEST",
    "user_id": "U_TEST",
    "user_name": "Test User (@test)",
    "text": "Update de prueba desde script ✅",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "is_update": True
}

print("Insertando...")
print(sb.table("slack-channel-project-update").upsert(row, on_conflict="message_id").execute())
print("Leyendo...")
print(sb.table("slack-channel-project-update").select("*").order("timestamp", desc=True).limit(1).execute())
