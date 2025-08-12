#!/bin/bash

# Script para migrar de Nginx a Caddy con SSL automático
# Dominios: api.asukaservices.xyz, status.asukaservices.xyz

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}==>${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

DOMAINS="api.asukaservices.xyz status.asukaservices.xyz"

print_step "Migrando de Nginx a Caddy con SSL automático..."

# Verificar DNS
print_step "Verificando configuración DNS..."
for domain in $DOMAINS; do
    if dig +short $domain | grep -q "178.128.183.253"; then
        print_success "$domain apunta correctamente al servidor"
    else
        print_warning "$domain no apunta al servidor. Verificar DNS."
    fi
done

# Parar servicios actuales
print_step "Deteniendo servicios Nginx..."
docker compose -f docker-compose.asuka.yml down 2>/dev/null || true
docker compose down 2>/dev/null || true

# Crear directorios para Caddy
print_step "Creando directorios para Caddy..."
mkdir -p caddy_data caddy_config logs/caddy

# Dar permisos adecuados
chmod -R 755 caddy_data caddy_config logs

# Iniciar servicios con Caddy
print_step "Iniciando servicios con Caddy..."
docker compose -f docker-compose.caddy.yml up -d

print_step "Esperando que Caddy configure SSL automáticamente..."
sleep 15

# Verificar estado de los servicios
print_step "Verificando estado de los servicios..."
if docker compose -f docker-compose.caddy.yml ps | grep -q "Up"; then
    print_success "Contenedores ejecutándose correctamente"
else
    print_error "Hay problemas con los contenedores"
    docker compose -f docker-compose.caddy.yml logs
    exit 1
fi

# Verificar conectividad HTTP (Caddy redirige automáticamente a HTTPS)
print_step "Verificando conectividad HTTP..."
sleep 5

if curl -s -o /dev/null -w "%{http_code}" http://api.asukaservices.xyz/ | grep -E "(200|301|302)"; then
    print_success "HTTP responde correctamente"
else
    print_warning "HTTP no responde como esperado"
fi

# Verificar HTTPS (puede tomar unos minutos para el primer certificado)
print_step "Verificando HTTPS (puede tomar 1-2 minutos para obtener certificados)..."
sleep 30

for domain in $DOMAINS; do
    print_step "Probando HTTPS para $domain..."
    if curl -s -k -o /dev/null -w "%{http_code}" https://$domain/ | grep -q "200"; then
        print_success "HTTPS funcionando para $domain"
    else
        print_warning "HTTPS aún no disponible para $domain (puede tardar más tiempo)"
    fi
done

echo ""
echo -e "${GREEN}🎉 ¡MIGRACIÓN A CADDY COMPLETADA!${NC}"
echo ""
echo -e "${BLUE}📍 URLs disponibles:${NC}"
echo "   • API: https://api.asukaservices.xyz/"
echo "   • Documentación: https://api.asukaservices.xyz/docs"
echo "   • Status: https://status.asukaservices.xyz/"
echo "   • Métricas: https://status.asukaservices.xyz/metrics"
echo ""
echo -e "${BLUE}🔐 API Keys disponibles:${NC}"
echo "   • admin123 (1000 req/min)"
echo "   • hello456 (100 req/min)"
echo "   • test789 (50 req/min)"
echo ""
echo -e "${BLUE}🛠 Comandos útiles:${NC}"
echo "   • Ver logs: docker compose -f docker-compose.caddy.yml logs -f"
echo "   • Reiniciar: docker compose -f docker-compose.caddy.yml restart"
echo "   • Ver certificados: docker compose -f docker-compose.caddy.yml exec caddy caddy list-certificates"
echo ""
echo -e "${YELLOW}📝 Nota: SSL se configura automáticamente. Si HTTPS no funciona inmediatamente,${NC}"
echo -e "${YELLOW}espera 2-5 minutos para que Caddy obtenga los certificados de Let's Encrypt.${NC}"
echo ""
echo -e "${BLUE}🧪 Ejemplo de uso:${NC}"
echo "curl -H 'Authorization: Bearer admin123' https://api.asukaservices.xyz/health"
echo ""
