FROM python:3.12-slim

WORKDIR /app

# Dépendances Python (mcp + mcpo + client LLM).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Code du serveur MCP.
COPY server.py llm.py case_loader.py mcpo_config.json ./

# L'enquête est montée en volume à l'exécution (voir docker-compose.yml).
ENV CASE_DIR=/app/case
EXPOSE 8000

# mcpo lance le serveur MCP (stdio) et l'expose en OpenAPI sur le port 8000.
# La clé d'API protège l'accès aux outils ; elle est fournie par l'environnement.
CMD ["sh", "-c", "mcpo --host 0.0.0.0 --port 8000 --api-key \"$MCPO_API_KEY\" --config mcpo_config.json"]
