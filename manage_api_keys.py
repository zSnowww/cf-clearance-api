#!/usr/bin/env python3
"""
Herramienta para gestionar API keys del sistema CF-Clearance.

Uso:
  python manage_api_keys.py generate --name cliente1 --rate-limit 100
  python manage_api_keys.py list
  python manage_api_keys.py revoke --key YOUR_API_KEY
"""

import argparse
import sys
from cf_clearance_scraper.api.auth import add_api_key, revoke_api_key, API_KEYS, hash_api_key


def generate_key(name: str, rate_limit: int) -> None:
    """Genera una nueva API key."""
    api_key = add_api_key(name, rate_limit)
    print(f"✅ Nueva API key generada:")
    print(f"   Cliente: {name}")
    print(f"   Rate limit: {rate_limit} requests/minuto")
    print(f"   API Key: {api_key}")
    print(f"   Hash: {hash_api_key(api_key)}")
    print()
    print("🔐 Ejemplo de uso:")
    print(f'   curl -H "Authorization: Bearer {api_key}" http://localhost:8000/health')


def list_keys() -> None:
    """Lista todas las API keys existentes."""
    print("📋 API Keys registradas:")
    print()
    
    if not API_KEYS:
        print("   No hay API keys registradas.")
        return
    
    for hashed_key, info in API_KEYS.items():
        print(f"   Cliente: {info['name']}")
        print(f"   Rate limit: {info['rate_limit']} requests/minuto")
        print(f"   Hash: {hashed_key}")
        print()


def revoke_key(api_key: str) -> None:
    """Revoca una API key existente."""
    success = revoke_api_key(api_key)
    
    if success:
        print(f"✅ API key revocada exitosamente: {api_key[:10]}...")
    else:
        print(f"❌ API key no encontrada: {api_key[:10]}...")


def test_examples() -> None:
    """Muestra ejemplos de las API keys predeterminadas."""
    print("🔧 API Keys de ejemplo (para desarrollo):")
    print()
    
    examples = {
        "admin123": {"name": "admin", "rate_limit": 1000},
        "hello456": {"name": "client1", "rate_limit": 100},
        "test789": {"name": "client2", "rate_limit": 50},
    }
    
    for api_key, info in examples.items():
        print(f"   Cliente: {info['name']}")
        print(f"   API Key: {api_key}")
        print(f"   Rate limit: {info['rate_limit']} requests/minuto")
        print(f"   Ejemplo curl:")
        print(f'   curl -H "Authorization: Bearer {api_key}" http://localhost:8000/health')
        print()


def main():
    parser = argparse.ArgumentParser(description="Gestión de API keys para CF-Clearance")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando generate
    generate_parser = subparsers.add_parser("generate", help="Generar nueva API key")
    generate_parser.add_argument("--name", required=True, help="Nombre del cliente")
    generate_parser.add_argument("--rate-limit", type=int, default=100, 
                                help="Límite de requests por minuto (default: 100)")
    
    # Comando list
    subparsers.add_parser("list", help="Listar API keys existentes")
    
    # Comando revoke
    revoke_parser = subparsers.add_parser("revoke", help="Revocar API key")
    revoke_parser.add_argument("--key", required=True, help="API key a revocar")
    
    # Comando examples
    subparsers.add_parser("examples", help="Mostrar API keys de ejemplo")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "generate":
            generate_key(args.name, args.rate_limit)
        elif args.command == "list":
            list_keys()
        elif args.command == "revoke":
            revoke_key(args.key)
        elif args.command == "examples":
            test_examples()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

