"""
Script de prueba para el sistema agéntico
Prueba las herramientas sin necesidad de Slack
"""
from agent_main import (
    analyze_sentiment,
    detect_blockers,
    classify_urgency,
    calculate_team_health,
    extract_key_decisions
)
import json

def test_analyze_sentiment():
    print("\n" + "="*60)
    print("🧪 TEST 1: analyze_sentiment")
    print("="*60)

    test_messages = [
        "Estoy frustrado, esto no funciona otra vez",
        "¡Genial! Ya está listo el deploy 🎉",
        "Me preocupa el deadline, vamos atrasados",
        "Revisé el código y todo está bien",
        "Bloqueado esperando revisión"
    ]

    result = analyze_sentiment(test_messages)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def test_detect_blockers():
    print("\n" + "="*60)
    print("🧪 TEST 2: detect_blockers")
    print("="*60)

    test_messages = [
        {
            'user_name': 'Juan Pérez (@juan)',
            'text': 'Estoy bloqueado esperando que <@U123> revise el PR',
            'ts': '1234567890.123456'
        },
        {
            'user_name': 'María García (@maria)',
            'text': 'No puedo avanzar hasta que se resuelva el bug #123',
            'ts': '1234567891.123456'
        },
        {
            'user_name': 'Pedro López (@pedro)',
            'text': 'Ya lo reviso, te desbloqueo en 10 minutos',
            'ts': '1234567892.123456'
        }
    ]

    result = detect_blockers(test_messages)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def test_classify_urgency():
    print("\n" + "="*60)
    print("🧪 TEST 3: classify_urgency")
    print("="*60)

    test_contexts = [
        "El cliente está reportando que no puede acceder a producción, urgente!",
        "Hay que hacer esta feature para el deadline de la próxima semana",
        "Cuando puedas, revisa este PR no urgente"
    ]

    for i, context in enumerate(test_contexts, 1):
        print(f"\n--- Contexto {i} ---")
        print(f"Texto: {context}")
        result = classify_urgency(context)
        print(json.dumps(result, indent=2, ensure_ascii=False))


def test_calculate_team_health():
    print("\n" + "="*60)
    print("🧪 TEST 4: calculate_team_health")
    print("="*60)

    test_data = {
        'total_members': 10,
        'active_members': 8,
        'total_messages': 50,
        'collaborative_messages': 20,
        'messages_per_user': [5, 8, 3, 12, 7, 4, 6, 5, 0, 0],
        'total_blockers': 2,
        'sentiment_score': 65
    }

    result = calculate_team_health(test_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def test_extract_key_decisions():
    print("\n" + "="*60)
    print("🧪 TEST 5: extract_key_decisions")
    print("="*60)

    test_messages = [
        {
            'user_name': 'Ana Torres (@ana)',
            'text': 'Decidimos que vamos a usar PostgreSQL porque necesitamos transacciones ACID',
            'ts': '1234567890.123456'
        },
        {
            'user_name': 'Carlos Ruiz (@carlos)',
            'text': '¿Deberíamos migrar el frontend a React o quedarnos con Vue?',
            'ts': '1234567891.123456'
        },
        {
            'user_name': 'Laura Díaz (@laura)',
            'text': 'Acordamos hacer el deploy el viernes. Siguiente paso: preparar el entorno de staging',
            'ts': '1234567892.123456'
        }
    ]

    result = extract_key_decisions(test_messages)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    print("\n" + "🧪"*30)
    print("PRUEBAS DEL SISTEMA AGÉNTICO")
    print("🧪"*30)

    test_analyze_sentiment()
    test_detect_blockers()
    test_classify_urgency()
    test_calculate_team_health()
    test_extract_key_decisions()

    print("\n" + "="*60)
    print("✅ TODAS LAS PRUEBAS COMPLETADAS")
    print("="*60)
    print("\nPara ejecutar el agente completo con Slack:")
    print("  python agent_main.py")
    print("\nAsegúrate de tener configurado el archivo .env con:")
    print("  - SLACK_BOT_TOKEN")
    print("  - ANTHROPIC_API_KEY")
    print("  - PROJECT_CHANNEL_ID")
    print("  - PROJECT_LEAD_USER_ID")


if __name__ == "__main__":
    main()
