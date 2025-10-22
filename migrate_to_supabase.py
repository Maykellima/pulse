"""
Script de migración de SQLite a Supabase
Migra datos existentes de pulse.db a Supabase PostgreSQL
"""
import os
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv
from database import get_db_manager, init_database

# Cargar variables de entorno
load_dotenv()

def migrate_sqlite_to_supabase():
    """Migra datos de SQLite local a Supabase"""
    print("🚀 Iniciando migración de SQLite a Supabase...")
    
    # 1. Verificar que existe pulse.db
    sqlite_file = 'pulse.db'
    if not os.path.exists(sqlite_file):
        print(f"❌ No se encontró {sqlite_file}")
        return False
    
    # 2. Inicializar Supabase
    print("📡 Conectando a Supabase...")
    try:
        init_database()
        db = get_db_manager()
        print("✅ Conexión a Supabase establecida")
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        return False
    
    # 3. Conectar a SQLite
    print("📁 Conectando a SQLite...")
    try:
        sqlite_conn = sqlite3.connect(sqlite_file)
        sqlite_cursor = sqlite_conn.cursor()
        print("✅ Conexión a SQLite establecida")
    except Exception as e:
        print(f"❌ Error conectando a SQLite: {e}")
        return False
    
    # 4. Migrar mensajes
    print("📨 Migrando mensajes...")
    try:
        sqlite_cursor.execute("SELECT id, user_id, text, timestamp, processed FROM messages")
        messages = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for msg in messages:
            message_id, user_id, text, timestamp, processed = msg
            
            # Guardar en Supabase
            success = db.save_message(message_id, user_id, text or '', timestamp)
            if success:
                migrated_count += 1
        
        print(f"✅ Migrados {migrated_count} mensajes a Supabase")
        
    except Exception as e:
        print(f"❌ Error migrando mensajes: {e}")
        return False
    
    # 5. Cerrar conexiones
    sqlite_conn.close()
    db.close()
    
    print("🎉 Migración completada exitosamente!")
    print("\n📋 Próximos pasos:")
    print("1. Verifica que los datos se migraron correctamente en Supabase")
    print("2. Actualiza tu archivo .env con las credenciales de Supabase")
    print("3. Ejecuta el sistema con: python main.py")
    print("4. Una vez confirmado que funciona, puedes eliminar pulse.db")
    
    return True

def verify_migration():
    """Verifica que la migración fue exitosa"""
    print("\n🔍 Verificando migración...")
    
    try:
        db = get_db_manager()
        
        # Contar mensajes en Supabase
        query = "SELECT COUNT(*) FROM messages"
        with db.connection.begin():
            result = db.connection.execute(query)
            count = result.scalar()
        
        print(f"✅ Mensajes en Supabase: {count}")
        
        # Mostrar algunos mensajes de ejemplo
        query = "SELECT id, user_id, text, timestamp FROM messages ORDER BY timestamp DESC LIMIT 5"
        with db.connection.begin():
            result = db.connection.execute(query)
            messages = result.fetchall()
        
        print("\n📋 Últimos 5 mensajes migrados:")
        for msg in messages:
            message_id, user_id, text, timestamp = msg
            print(f"  • {user_id}: {text[:50]}... ({datetime.fromtimestamp(timestamp)})")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando migración: {e}")
        return False

def main():
    """Función principal"""
    print("=" * 60)
    print("🔄 MIGRACIÓN DE SQLITE A SUPABASE")
    print("=" * 60)
    
    # Verificar variables de entorno
    required_vars = ['DATABASE_URL', 'DB_HOST', 'DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        print("Por favor, configura tu archivo .env con las credenciales de Supabase")
        return
    
    # Ejecutar migración
    if migrate_sqlite_to_supabase():
        verify_migration()
    else:
        print("❌ La migración falló")

if __name__ == "__main__":
    main()
