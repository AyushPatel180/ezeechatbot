#!/bin/bash
# EzeeChatBot Verification Script

echo "=== EzeeChatBot Pre-Submission Verification ==="
echo ""

# Check Python syntax
echo "1. Checking Python syntax..."
python -m py_compile app/main.py 2>/dev/null && echo "   ✓ main.py" || echo "   ✗ main.py SYNTAX ERROR"
python -m py_compile app/config.py 2>/dev/null && echo "   ✓ config.py" || echo "   ✗ config.py SYNTAX ERROR"
python -m py_compile app/models.py 2>/dev/null && echo "   ✓ models.py" || echo "   ✗ models.py SYNTAX ERROR"
echo ""

# Check required files exist
echo "2. Checking required files..."
files=(
    "README.md"
    "requirements.txt"
    "Dockerfile"
    "docker-compose.yml"
    "proxy_config.yaml"
    ".env.example"
    "app/main.py"
    "app/config.py"
    "app/models.py"
    "app/routers/upload.py"
    "app/routers/chat.py"
    "app/routers/stats.py"
    "app/routers/health.py"
    "app/services/pipeline.py"
    "app/services/retriever.py"
    "app/services/chat_engine.py"
    "app/services/cost_tracker.py"
    "app/services/ingestion/pdf_reader.py"
    "app/services/ingestion/url_reader.py"
    "app/services/ingestion/__init__.py"
    "app/core/qdrant_client.py"
    "app/core/llama_settings.py"
    "app/core/langfuse_handler.py"
    "app/db/database.py"
    "app/db/stats_repo.py"
    "app/utils/errors.py"
    "tests/conftest.py"
    "tests/test_upload.py"
    "tests/test_chat.py"
    "tests/test_stats.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    else
        echo "   ✗ $file MISSING"
    fi
done
echo ""

# Check directory structure
echo "3. Checking directory structure..."
dirs=(
    "app"
    "app/routers"
    "app/services"
    "app/services/ingestion"
    "app/core"
    "app/db"
    "app/utils"
    "tests"
)

for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "   ✓ $dir/"
    else
        echo "   ✗ $dir/ MISSING"
    fi
done
echo ""

echo "=== Verification Complete ==="
echo ""
echo "To run the application:"
echo "  1. cp .env.example .env && edit with your API keys"
echo "  2. docker compose up -d"
echo "  3. curl http://localhost:8000/health"
echo ""
echo "To run tests:"
echo "  pytest tests/ -v"
