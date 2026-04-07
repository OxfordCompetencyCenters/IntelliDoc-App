#!/bin/bash

echo "🔍 Testing API Endpoints Manually..."
echo "======================================"

# Test the history endpoint
echo "📊 Testing History API..."
curl -s "http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/workflows/3e3335b5-3754-439f-99b0-95d984aa3354/history/" | jq . > /tmp/history_response.json

if [ $? -eq 0 ]; then
    echo "✅ History API Response saved to /tmp/history_response.json"
    echo "Response size: $(wc -c < /tmp/history_response.json) bytes"
    echo "Recent executions count: $(jq '.recent_executions | length' /tmp/history_response.json)"
    echo "First execution ID: $(jq -r '.recent_executions[0].execution_id' /tmp/history_response.json)"
    
    # Get the execution ID for testing conversation API
    EXEC_ID=$(jq -r '.recent_executions[0].execution_id' /tmp/history_response.json)
    
    echo ""
    echo "💬 Testing Conversation API..."
    curl -s "http://localhost:8000/api/projects/d61a5d4d-6c3a-4b4c-89a9-b0edf7e54a99/workflows/3e3335b5-3754-439f-99b0-95d984aa3354/conversation/?execution_id=$EXEC_ID" | jq . > /tmp/conversation_response.json
    
    if [ $? -eq 0 ]; then
        echo "✅ Conversation API Response saved to /tmp/conversation_response.json"
        echo "Response size: $(wc -c < /tmp/conversation_response.json) bytes"
        echo "Messages count: $(jq '.messages | length' /tmp/conversation_response.json)"
    else
        echo "❌ Conversation API failed"
    fi
else
    echo "❌ History API failed"
fi

echo ""
echo "📋 Response files:"
echo "   History: /tmp/history_response.json"
echo "   Conversation: /tmp/conversation_response.json"
echo ""
echo "✅ API Test Complete"
