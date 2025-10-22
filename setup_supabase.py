"""
Script de configuración inicial para Supabase
Ayuda a configurar la base de datos y verificar la conexión
"""
import os
import sys
from dotenv import load_dotenv
from supabase_client import get_supabase_manager, init_supabase

def check_environment():
    """Verifica que las variables de entorno estén configuradas"""
    print("🔍 Verificando configuración del entorno...")
    
    load_dotenv()
    
    # Variables requeridas
    required_vars = {
        'SLACK_BOT_TOKEN': 'Token del bot de Slack',
        'ANTHROPIC_API_KEY': 'API Key de Anthropic Claude',
        'PROJECT_CHANNEL_ID': 'ID del canal de Slack',
        'PROJECT_LEAD_USER_ID': 'ID del usuario líder'
    }
    
    # Variables de Supabase (cliente oficial)
    supabase_vars = {
        'SUPABASE_URL': 'URL de tu proyecto Supabase',
        'SUPABASE_SERVICE_ROLE_KEY': 'Service Role Key de Supabase'
    }
    
    missing_vars = []
    
    # Verificar variables requeridas
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  • {var}: {description}")
    
    # Verificar variables de Supabase
    has_supabase_vars = all(os.getenv(var) for var in supabase_vars.keys())
    
    if not has_supabase_vars:
        missing_vars.append("  • Variables de Supabase: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY")
    
    if missing_vars:
        print("❌ Variables de entorno faltantes:")
        for var in missing_vars:
            print(var)
        print("\n📝 Por favor, configura tu archivo .env con todas las variables necesarias")
        return False
    
    print("✅ Todas las variables de entorno están configuradas")
    return True

def test_supabase_connection():
    """Prueba la conexión a Supabase"""
    print("\n📡 Probando conexión a Supabase...")
    
    try:
        supabase = get_supabase_manager()
        print("✅ Conexión a Supabase establecida exitosamente")
        
        # Probar una consulta simple
        result = supabase.client.table("slack-channel-project-update").select("count").limit(1).execute()
        print("📊 Conexión a tabla verificada exitosamente")
        
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        print("\n🔧 Posibles soluciones:")
        print("  • Verifica que SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY sean correctos")
        print("  • Asegúrate de que tu proyecto Supabase esté activo")
        print("  • Verifica que la tabla 'slack-channel-project-update' exista")
        return False

def setup_database_schema():
    """Configura el esquema de la base de datos"""
    print("\n🏗️  Configurando esquema de la base de datos...")
    
    try:
        init_supabase()
        print("✅ Supabase inicializado exitosamente")
        print("ℹ️  Asegúrate de que la tabla 'slack-channel-project-update' esté creada en Supabase")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando Supabase: {e}")
        return False

def test_slack_connection():
    """Prueba la conexión a Slack"""
    print("\n💬 Probando conexión a Slack...")
    
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        slack_token = os.getenv('SLACK_BOT_TOKEN')
        channel_id = os.getenv('PROJECT_CHANNEL_ID')
        
        if not slack_token or not channel_id:
            print("❌ Token de Slack o ID de canal no configurados")
            return False
        
        client = WebClient(token=slack_token)
        
        # Probar conexión básica
        response = client.auth_test()
        print(f"✅ Conectado a Slack como: {response['user']}")
        
        # Probar acceso al canal
        try:
            channel_info = client.conversations_info(channel=channel_id)
            print(f"✅ Acceso al canal: #{channel_info['channel']['name']}")
        except SlackApiError as e:
            print(f"❌ Error accediendo al canal: {e.response['error']}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a Slack: {e}")
        return False

def test_anthropic_connection():
    """Prueba la conexión a Anthropic"""
    print("\n🤖 Probando conexión a Anthropic...")
    
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("❌ API Key de Anthropic no configurada")
            return False
        
        client = Anthropic(api_key=api_key)
        
        # Probar una consulta simple
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hola"}]
        )
        
        print("✅ Conexión a Anthropic establecida exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a Anthropic: {e}")
        return False

def main():
    """Función principal de setup"""
    print("=" * 60)
    print("🚀 SETUP INICIAL DE PULSE CON SUPABASE")
    print("=" * 60)
    
    # Verificar entorno
    if not check_environment():
        sys.exit(1)
    
    # Probar conexiones
    tests = [
        ("Supabase", test_supabase_connection),
        ("Esquema de BD", setup_database_schema),
        ("Slack", test_slack_connection),
        ("Anthropic", test_anthropic_connection)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        if not test_func():
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ¡SETUP COMPLETADO EXITOSAMENTE!")
        print("\n📋 Próximos pasos:")
        print("1. Si tienes datos en SQLite, ejecuta: python migrate_to_supabase.py")
        print("2. Ejecuta el sistema: python main.py")
        print("3. O ejecuta el agente: python agent_main.py")
    else:
        print("❌ SETUP INCOMPLETO")
        print("\n🔧 Por favor, resuelve los errores antes de continuar")
        sys.exit(1)

if __name__ == "__main__":
    main()
