# MIGRATION FIX INSTRUCTIONS

## 🔧 Problem Fixed
The migration dependency was incorrect. I've fixed it and renamed the migration file.

## 🚀 Manual Steps to Run Migration

1. **Navigate to backend directory:**
   ```bash
   cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Check current migration status:**
   ```bash
   python manage.py showmigrations users
   ```

4. **Run the fixed migration:**
   ```bash
   python manage.py migrate users 0020
   ```

5. **Verify migration completed:**
   ```bash
   python manage.py showmigrations users
   ```

## 📋 What the Migration Does

The migration `0020_workflow_execution_history.py` creates:

- **WorkflowExecution** table to store execution records
- **WorkflowExecutionMessage** table to store conversation messages
- Proper foreign key relationships
- Indexes for performance

## ✅ Expected Output

You should see:
```
Operations to perform:
  Target specific migration: 0020_workflow_execution_history, from users
Running migrations:
  Applying users.0020_workflow_execution_history... OK
```

## 🔍 If Migration Still Fails

If you get any errors, please share the exact error message and I can fix it immediately.

After successful migration, both issues will be resolved:
1. ✅ New workflows start blank (no default StartNode)
2. ✅ Execution history shows full conversation messages
