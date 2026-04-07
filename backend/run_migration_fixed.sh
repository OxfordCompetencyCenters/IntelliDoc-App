#!/bin/bash

# Navigate to backend directory  
cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend

# Activate virtual environment
source venv/bin/activate

echo "🔄 Running migration to create WorkflowExecution models..."
python manage.py migrate users 0020

if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully!"
    echo ""
    echo "🎯 Summary of Changes:"
    echo "  ✅ Frontend: Removed default StartNode from new workflows"
    echo "  ✅ Backend: Added WorkflowExecution and WorkflowExecutionMessage models"
    echo "  ✅ Backend: Updated conversation orchestrator to save execution history"
    echo "  ✅ Backend: Updated history endpoint to return actual conversations"
    echo ""
    echo "🚀 You can now:"
    echo "  1. Create new workflows - they will start BLANK (no default nodes)"
    echo "  2. Execute workflows with agents - conversation history will be saved"
    echo "  3. View conversation history in the execution history tab"
    echo ""
    echo "🔧 Next: Restart your Django server to load the updated code"
else
    echo "❌ Migration failed!"
    echo "Check the error above and try again."
fi
