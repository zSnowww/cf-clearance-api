#!/bin/bash

echo "🔐 Configurando SSL para zsnow.site..."

# Instalar Certbot
apt update
apt install -y certbot python3-certbot-nginx

# Crear directorio SSL
mkdir -p /opt/cf-clearance/ssl

# Obtener certificados para ambos subdominios
certbot certonly --standalone --non-interactive --agree-tos \
  --email tu-email@gmail.com \
  -d api.zsnow.site \
  -d status.zsnow.site

# Copiar certificados a directorio del proyecto
cp /etc/letsencrypt/live/api.zsnow.site/fullchain.pem /opt/cf-clearance/ssl/api.zsnow.site.pem
cp /etc/letsencrypt/live/api.zsnow.site/privkey.pem /opt/cf-clearance/ssl/api.zsnow.site.key
cp /etc/letsencrypt/live/status.zsnow.site/fullchain.pem /opt/cf-clearance/ssl/status.zsnow.site.pem
cp /etc/letsencrypt/live/status.zsnow.site/privkey.pem /opt/cf-clearance/ssl/status.zsnow.site.key

# Configurar renovación automática
echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose -f /opt/cf-clearance/docker-compose.zsnow.yml restart nginx" | crontab -

echo "✅ SSL configurado. Descomenta las secciones HTTPS en nginx.zsnow.conf"

