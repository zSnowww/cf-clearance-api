#!/bin/bash

# Script para probar la API después del despliegue
# IP: 178.128.183.253

API_BASE="http://178.128.183.253"
API_KEY="admin123"

echo "🧪 Probando CF-Clearance API en $API_BASE"
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

test_endpoint() {
    local endpoint=$1
    local method=${2:-GET}
    local data=${3:-}
    
    echo -n "Testing $method $endpoint... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "%{http_code}" -H "Authorization: Bearer $API_KEY" "$API_BASE$endpoint")
    else
        response=$(curl -s -w "%{http_code}" -X $method -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d "$data" "$API_BASE$endpoint")
    fi
    
    http_code="${response: -3}"
    body="${response%???}"
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✓ OK${NC}"
        echo "   Response: $body" | head -c 100
        echo ""
    else
        echo -e "${RED}✗ FAILED (HTTP $http_code)${NC}"
        echo "   Response: $body"
        echo ""
    fi
}

echo -e "${BLUE}=== Tests básicos ===${NC}"
test_endpoint "/"
test_endpoint "/health"
test_endpoint "/docs"

echo -e "${BLUE}=== Test de autenticación ===${NC}"
echo -n "Testing authentication... "
response=$(curl -s -w "%{http_code}" "$API_BASE/health")
http_code="${response: -3}"
if [ "$http_code" -eq 401 ] || [ "$http_code" -eq 403 ]; then
    echo -e "${GREEN}✓ Auth required${NC}"
else
    echo -e "${RED}✗ No auth required${NC}"
fi

echo -e "${BLUE}=== Test Turnstile Detection ===${NC}"
test_endpoint "/turnstile/detect" "POST" '{"url": "https://example.com"}'

echo ""
echo -e "${GREEN}🎉 Tests completados!${NC}"
echo ""
echo -e "${BLUE}Para usar la API:${NC}"
echo "curl -H 'Authorization: Bearer admin123' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"url\": \"https://example.com\"}' \\"
echo "     $API_BASE/scrape"
echo ""
