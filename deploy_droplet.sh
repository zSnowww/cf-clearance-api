#!/bin/bash

# Script de despliegue automático para CF-Clearance API
# IP del Droplet: 178.128.183.253

set -e

echo "🚀 Iniciando despliegue de CF-Clearance API..."
echo "📍 IP del servidor: 178.128.183.253"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Verificar si somos root
if [ "$EUID" -ne 0 ]; then
    print_error "Este script debe ejecutarse como root"
    echo "Usa: sudo bash deploy_droplet.sh"
    exit 1
fi

print_step "Actualizando sistema..."
apt update && apt upgrade -y
print_success "Sistema actualizado"

print_step "Instalando dependencias básicas..."
apt install -y git curl wget gnupg lsb-release ca-certificates ufw
print_success "Dependencias instaladas"

print_step "Configurando firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw --force enable
print_success "Firewall configurado"

print_step "Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    print_success "Docker instalado"
else
    print_success "Docker ya está instalado"
fi

print_step "Instalando Docker Compose..."
if ! docker compose version &> /dev/null; then
    mkdir -p ~/.docker/cli-plugins/
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o ~/.docker/cli-plugins/docker-compose
    chmod +x ~/.docker/cli-plugins/docker-compose
    print_success "Docker Compose instalado"
else
    print_success "Docker Compose ya está instalado"
fi

print_step "Creando directorios del proyecto..."
mkdir -p /opt/apps
cd /opt/apps

print_step "Clonando repositorio..."
if [ -d "cf-clearance-api" ]; then
    print_warning "El directorio ya existe, actualizando..."
    cd cf-clearance-api
    git pull
else
    git clone https://github.com/zSnowww/cf-clearance-api.git
    cd cf-clearance-api
fi
print_success "Repositorio clonado/actualizado"

print_step "Configurando directorios..."
mkdir -p logs ssl
chmod -R 755 .
print_success "Directorios configurados"

print_step "Iniciando servicios con Docker Compose..."
docker compose down 2>/dev/null || true
docker compose up -d --build

print_success "Servicios iniciados"

print_step "Verificando estado de los servicios..."
sleep 10

if docker compose ps | grep -q "Up"; then
    print_success "Contenedores ejecutándose correctamente"
else
    print_error "Hay problemas con los contenedores"
    docker compose logs
    exit 1
fi

print_step "Probando conectividad..."
sleep 5

# Test health check
if curl -f http://localhost/health &>/dev/null; then
    print_success "API respondiendo en puerto 80 (Nginx)"
else
    print_warning "Nginx no responde, probando puerto directo..."
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_success "API respondiendo en puerto 8000 (directo)"
    else
        print_error "API no responde en ningún puerto"
        docker compose logs
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}🎉 ¡DESPLIEGUE COMPLETADO EXITOSAMENTE!${NC}"
echo ""
echo -e "${BLUE}📍 Información del despliegue:${NC}"
echo "   • IP del servidor: 178.128.183.253"
echo "   • API URL: http://178.128.183.253/"
echo "   • Documentación: http://178.128.183.253/docs"
echo "   • Health check: http://178.128.183.253/health"
echo "   • API directa: http://178.128.183.253:8000/"
echo ""
echo -e "${BLUE}🔐 API Keys disponibles:${NC}"
echo "   • admin123 (1000 req/min)"
echo "   • hello456 (100 req/min)"
echo "   • test789 (50 req/min)"
echo ""
echo -e "${BLUE}🛠 Comandos útiles:${NC}"
echo "   • Ver logs: docker compose logs -f"
echo "   • Reiniciar: docker compose restart"
echo "   • Parar: docker compose down"
echo "   • Estado: docker compose ps"
echo ""
echo -e "${YELLOW}Ejemplo de uso:${NC}"
echo "curl -H 'Authorization: Bearer admin123' http://178.128.183.253/health"
echo ""
