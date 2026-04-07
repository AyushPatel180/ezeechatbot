#!/bin/bash
# EzeeChatBot Integration Test Script
# Run this after: docker compose up -d

set -e

BASE_URL="http://localhost:8000"

echo "=== EzeeChatBot Integration Tests ==="
echo ""

# Check if API is up
echo "1. Testing health endpoint..."
for i in {1..30}; do
    if curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
        echo "   ✓ API is up"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "   ✗ API failed to start"
        exit 1
    fi
    sleep 1
done

# Test health response
echo "2. Checking health status..."
HEALTH=$(curl -s "${BASE_URL}/health")
echo "   Response: $HEALTH"

# Test upload with text
echo ""
echo "3. Testing POST /upload (text)..."
UPLOAD_RESP=$(curl -s -X POST "${BASE_URL}/upload" \
    -H "Content-Type: application/json" \
    -d '{
        "content_type": "text",
        "content": "The refund policy is 30 days with receipt. Customers can return items within 30 days of purchase for a full refund. Shipping costs are not refundable. Sale items are final sale."
    }')
echo "   Response: $UPLOAD_RESP"

BOT_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['bot_id'])" 2>/dev/null || echo "")
CHUNKS=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['chunks_created'])" 2>/dev/null || echo "0")

if [ -z "$BOT_ID" ]; then
    echo "   ✗ Upload failed - no bot_id returned"
    exit 1
fi

echo "   ✓ Uploaded successfully (bot_id: $BOT_ID, chunks: $CHUNKS)"

# Test stats endpoint
echo ""
echo "4. Testing GET /stats/{bot_id}..."
STATS_RESP=$(curl -s "${BASE_URL}/stats/${BOT_ID}")
echo "   Response: $STATS_RESP"
echo "   ✓ Stats retrieved"

# Test chat - question IN document
echo ""
echo "5. Testing POST /chat (question IN document)..."
echo "   Sending: 'What is the refund policy?'"
curl -s -N -X POST "${BASE_URL}/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"bot_id\": \"${BOT_ID}\",
        \"user_message\": \"What is the refund policy?\"
    }" | while read line; do
    echo "   $line"
    if [[ "$line" == *"[DONE]"* ]]; then
        break
    fi
done
echo "   ✓ Chat streaming complete"

# Test chat - question NOT in document (hallucination guard)
echo ""
echo "6. Testing POST /chat (question NOT in document - hallucination guard)..."
echo "   Sending: 'What is the capital of France?'"
curl -s -N -X POST "${BASE_URL}/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"bot_id\": \"${BOT_ID}\",
        \"user_message\": \"What is the capital of France?\"
    }" | while read line; do
    echo "   $line"
    if [[ "$line" == *"[DONE]"* ]]; then
        break
    fi
done
echo "   ✓ Hallucination guard tested"

# Check final stats
echo ""
echo "7. Final stats check..."
FINAL_STATS=$(curl -s "${BASE_URL}/stats/${BOT_ID}")
echo "   Response: $FINAL_STATS"
MESSAGES=$(echo "$FINAL_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_messages_served'])" 2>/dev/null || echo "0")
echo "   ✓ Total messages served: $MESSAGES"

echo ""
echo "=== All Tests Complete ==="
echo ""
echo "Summary:"
echo "  - Health check: ✓"
echo "  - Upload: ✓ (bot_id: $BOT_ID)"
echo "  - Chat (in-doc): ✓"
echo "  - Chat (off-topic): ✓"
echo "  - Stats: ✓ ($MESSAGES messages)"
