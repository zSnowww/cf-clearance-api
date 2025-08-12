#!/bin/bash

# Script para configurar SSL para asukaservices.xyz subdominios
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
EMAIL="admin@asukaservices.xyz"  # Cambia por tu email

print_step "Configurando SSL para dominios: $DOMAINS"

# Verificar que los dominios apunten al servidor
print_step "Verificando configuración DNS..."
for domain in $DOMAINS; do
    print_step "Verificando $domain..."
    if dig +short $domain | grep -q "178.128.183.253"; then
        print_success "$domain apunta correctamente al servidor"
    else
        print_warning "$domain no apunta al servidor aún. DNS puede tardar hasta 24h en propagarse."
    fi
done

# Crear directorios necesarios
print_step "Creando directorios SSL..."
mkdir -p ssl ssl-challenge logs/nginx

# Configuración temporal de Nginx para verificación SSL
print_step "Creando configuración temporal para verificación SSL..."
cat > nginx.ssl.temp.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream cf_clearance_api {
        server cf-clearance-api:8000;
    }

    # Servidor temporal para verificación SSL
    server {
        listen 80;
        server_name api.asukaservices.xyz status.asukaservices.xyz;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$server_name$request_uri;
        }
    }
}
EOF

# Reiniciar con configuración temporal
print_step "Aplicando configuración temporal..."
docker compose -f docker-compose.asuka.yml down
cp nginx.ssl.temp.conf nginx.asuka.conf
docker compose -f docker-compose.asuka.yml up -d nginx

sleep 5

# Obtener certificados SSL
print_step "Obteniendo certificados SSL..."
docker compose -f docker-compose.asuka.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d api.asukaservices.xyz \
    -d status.asukaservices.xyz

if [ $? -eq 0 ]; then
    print_success "Certificados SSL obtenidos exitosamente"
else
    print_error "Error obteniendo certificados SSL"
    exit 1
fi

# Crear configuración final con HTTPS
print_step "Creando configuración final con HTTPS..."
cat > nginx.asuka.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Configuración de logs
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;

    # Configuración básica
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;

    # Configuración SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Configuración de gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    # Upstream para la API
    upstream cf_clearance_api {
        server cf-clearance-api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=status:10m rate=30r/s;

    # Redirección HTTP a HTTPS
    server {
        listen 80;
        server_name api.asukaservices.xyz status.asukaservices.xyz;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    # Servidor HTTPS para api.asukaservices.xyz
    server {
        listen 443 ssl http2;
        server_name api.asukaservices.xyz;

        ssl_certificate /etc/letsencrypt/live/api.asukaservices.xyz/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.asukaservices.xyz/privkey.pem;

        # Rate limiting para API
        limit_req zone=api burst=20 nodelay;

        # Headers de seguridad
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        location / {
            proxy_pass http://cf_clearance_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Bloquear acceso directo al health check
        location /health {
            return 404;
        }
    }

    # Servidor HTTPS para status.asukaservices.xyz
    server {
        listen 443 ssl http2;
        server_name status.asukaservices.xyz;

        ssl_certificate /etc/letsencrypt/live/api.asukaservices.xyz/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.asukaservices.xyz/privkey.pem;

        # Rate limiting más permisivo para status
        limit_req zone=status burst=50 nodelay;

        # Headers de seguridad
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        # Página de status (sin /health en la URL)
        location / {
            proxy_pass http://cf_clearance_api/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            
            # Headers específicos para status
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }

        # Endpoint adicional para métricas (opcional)
        location /metrics {
            proxy_pass http://cf_clearance_api/admin/stats;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
        }
    }

    # Servidor por defecto (para la IP directa)
    server {
        listen 80 default_server;
        listen 443 ssl default_server;
        server_name _;
        
        ssl_certificate /etc/letsencrypt/live/api.asukaservices.xyz/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.asukaservices.xyz/privkey.pem;
        
        location / {
            return 444;
        }
    }
}
EOF

# Reiniciar con configuración final
print_step "Aplicando configuración final..."
docker compose -f docker-compose.asuka.yml down
docker compose -f docker-compose.asuka.yml up -d

# Limpiar archivo temporal
rm -f nginx.ssl.temp.conf

print_success "Configuración SSL completada!"

echo ""
echo -e "${GREEN}🎉 ¡CONFIGURACIÓN COMPLETADA!${NC}"
echo ""
echo -e "${BLUE}📍 URLs disponibles:${NC}"
echo "   • API: https://api.asukaservices.xyz/"
echo "   • Documentación: https://api.asukaservices.xyz/docs"
echo "   • Status: https://status.asukaservices.xyz/"
echo "   • Métricas: https://status.asukaservices.xyz/metrics"
echo ""
echo -e "${BLUE}🔐 Ejemplo de uso:${NC}"
echo "curl -H 'Authorization: Bearer admin123' https://api.asukaservices.xyz/health"
echo ""
