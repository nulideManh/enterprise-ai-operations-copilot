#!/usr/bin/env sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NETWORK_NAME="enterprise-copilot-net"
DB_VOLUME="enterprise-copilot-postgres"
DB_CONTAINER="enterprise-copilot-db"
API_CONTAINER="enterprise-copilot-api"
WEB_CONTAINER="enterprise-copilot-web"

if ! colima status >/dev/null 2>&1; then
  colima start --cpu 4 --memory 6 --disk 40
fi

docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || docker network create "$NETWORK_NAME"
docker volume inspect "$DB_VOLUME" >/dev/null 2>&1 || docker volume create "$DB_VOLUME"

for container in "$WEB_CONTAINER" "$API_CONTAINER" "$DB_CONTAINER"; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$container"; then
    docker rm -f "$container" >/dev/null
  fi
done

docker run -d \
  --name "$DB_CONTAINER" \
  --network "$NETWORK_NAME" \
  -p 5432:5432 \
  -e POSTGRES_DB=copilot \
  -e POSTGRES_USER=copilot \
  -e POSTGRES_PASSWORD=copilot \
  -v "$DB_VOLUME:/var/lib/postgresql/data" \
  -v "$PROJECT_ROOT/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro" \
  pgvector/pgvector:pg16 >/dev/null

until docker exec "$DB_CONTAINER" pg_isready -U copilot -d copilot >/dev/null 2>&1; do
  sleep 1
done

docker build -t enterprise-copilot-backend "$PROJECT_ROOT/backend"
docker run -d \
  --name "$API_CONTAINER" \
  --network "$NETWORK_NAME" \
  --add-host=host.docker.internal:host-gateway \
  -p 8001:8000 \
  -e "DATABASE_URL=postgresql+asyncpg://copilot:copilot@$DB_CONTAINER:5432/copilot" \
  -e CORS_ORIGINS=http://localhost:3000 \
  -e LLM_PROVIDER="${LLM_PROVIDER:-auto}" \
  -e LOCAL_LLM_BASE_URL="${LOCAL_LLM_BASE_URL:-http://host.docker.internal:8000/v1}" \
  -e LOCAL_LLM_API_KEY="${LOCAL_LLM_API_KEY:-local}" \
  -e LOCAL_CHAT_MODEL="${LOCAL_CHAT_MODEL:-local-model}" \
  -e LOCAL_EMBEDDING_BASE_URL="${LOCAL_EMBEDDING_BASE_URL:-}" \
  -e LOCAL_EMBEDDING_MODEL="${LOCAL_EMBEDDING_MODEL:-}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  -e OPENAI_CHAT_MODEL="${OPENAI_CHAT_MODEL:-gpt-4.1-mini}" \
  -e OPENAI_EMBEDDING_MODEL="${OPENAI_EMBEDDING_MODEL:-text-embedding-3-large}" \
  -e EMBEDDING_DIMENSIONS=1536 \
  enterprise-copilot-backend >/dev/null

until docker exec "$API_CONTAINER" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" >/dev/null 2>&1; do
  sleep 1
done

docker build -t enterprise-copilot-frontend "$PROJECT_ROOT/frontend"
docker run -d \
  --name "$WEB_CONTAINER" \
  --network "$NETWORK_NAME" \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8001 \
  enterprise-copilot-frontend >/dev/null

echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8001"
echo "Local LLM expected at: ${LOCAL_LLM_BASE_URL:-http://host.docker.internal:8000/v1}"
echo "Database: localhost:5432"
