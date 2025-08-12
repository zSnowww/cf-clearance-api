# CF-Clearance Scraper - Producción
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 scraper
USER scraper
WORKDIR /app

# Copiar archivos de la aplicación
COPY --chown=scraper:scraper requirements.txt .
COPY --chown=scraper:scraper . .

# Instalar dependencias de Python
RUN pip install --user --no-cache-dir -r requirements.txt

# Variables de entorno
ENV PATH="/home/scraper/.local/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Optimizaciones para memoria limitada
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --memory-pressure-off"

# Puerto de la aplicación
EXPOSE 8000

# Comando por defecto
CMD ["python", "api_server.py", "--host", "0.0.0.0", "--port", "8000"]
