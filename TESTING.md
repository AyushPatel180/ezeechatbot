# Testing Guide for EzeeChatBot

## Quick Start

```bash
# 1. Start all services
docker compose up -d

# 2. Wait for services to be ready (check health)
./test_integration.sh

# 3. Or test manually with curl
```

## Manual curl Tests

### Health Check
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"api":"healthy","qdrant":"healthy","litellm_proxy":"healthy","sqlite":"healthy"}
```

### Upload Text Content
```bash
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "text",
    "content": "The refund policy is 30 days with receipt. Customers can return items within 30 days of purchase for a full refund. Shipping costs are not refundable."
  }'
```
Expected response:
```json
{
  "bot_id": "uuid-here",
  "chunks_created": 3,
  "tokens_ingested": 150,
  "source_type": "text",
  "message": "Knowledge base ready. Use this bot_id to chat."
}
```

### Get Stats
```bash
# Replace with actual bot_id from upload response
curl http://localhost:8000/stats/{bot_id}
```

### Chat (In-Document Question)
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "{bot_id}",
    "user_message": "What is the refund policy?"
  }'
```
Expected: Streaming SSE response with grounded answer

### Chat (Off-Topic Question - Hallucination Guard)
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "{bot_id}",
    "user_message": "What is the capital of France?"
  }'
```
Expected: Fallback message saying it couldn't find the information

### Upload PDF (base64 encoded)
```bash
# First encode a PDF to base64
PDF_CONTENT=$(base64 -i document.pdf)

curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d "{
    \"content_type\": \"pdf_base64\",
    \"content\": \"$PDF_CONTENT\"
  }"
```

### Upload URL
```bash
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "url",
    "content": "https://example.com/docs"
  }'
```

## Viewing Logs

```bash
# API logs
docker compose logs -f api

# All services
docker compose logs -f

# Qdrant logs
docker compose logs -f qdrant

# LiteLLM Proxy logs
docker compose logs -f litellm-proxy
```

## Testing Multi-Bot Isolation

```bash
# Create bot A with document about refunds
BOT_A=$(curl -s -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"content_type": "text", "content": "Refund policy: 30 days"}' | jq -r '.bot_id')

# Create bot B with document about shipping
BOT_B=$(curl -s -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"content_type": "text", "content": "Shipping takes 5-7 business days"}' | jq -r '.bot_id')

# Query bot A about shipping (should not know)
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"bot_id\": \"$BOT_A\", \"user_message\": \"How long does shipping take?\"}"

# Query bot B about refunds (should not know)
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"bot_id\": \"$BOT_B\", \"user_message\": \"What is the refund policy?\"}"
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_upload.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Troubleshooting

### Services not starting
```bash
# Check Docker is running
docker ps

# Check logs for errors
docker compose logs

# Restart services
docker compose down -v
docker compose up -d --build
```

### Qdrant connection issues
```bash
# Check Qdrant is healthy
curl http://localhost:6333/healthz
```

### LiteLLM Proxy issues
```bash
# Check proxy health
curl http://localhost:4000/health

# Check proxy logs
docker compose logs -f litellm-proxy
```
