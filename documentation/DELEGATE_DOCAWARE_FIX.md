# Fix: Delegate Agents Not Getting DocAware Search Results

## Root Cause Identified

**The Problem**: When GroupChatManager nodes execute in **parallel**, they were being treated as regular AssistantAgents instead of going through the delegate execution code path.

### The Issue

1. **Parallel Execution Path**: When multiple nodes execute in parallel (e.g., Chat Manager 1 and Chat Manager 2), they go through `_execute_nodes_in_parallel()` function
2. **Missing Special Handling**: This function did NOT have special handling for GroupChatManager
3. **Result**: GroupChatManager was executed as a regular AssistantAgent:
   - Called `craft_conversation_prompt_with_docaware()` directly
   - Called `llm_provider.generate_response()` directly
   - **Never discovered or executed delegates**
   - **DocAware never ran for delegates**

### Evidence from Logs

The logs showed:
- ✅ GroupChatManager nodes executing in parallel
- ✅ GroupChatManager completing successfully
- ❌ **NO** delegate discovery logs
- ❌ **NO** delegate execution logs
- ❌ **NO** DocAware logs for delegates

## The Fix

### Changes Made

1. **Added GroupChatManager Special Handling in Parallel Execution** (`workflow_executor.py:2107-2155`)
   - Detects when a node is GroupChatManager in parallel execution
   - Routes to `execute_group_chat_manager_with_multiple_inputs()` or `execute_group_chat_manager()`
   - Ensures delegates are discovered and executed
   - Ensures DocAware runs for delegates

2. **Updated Result Processing** (`workflow_executor.py:2218-2250`)
   - Handles GroupChatManager results from parallel execution
   - Extracts delegate conversations and status
   - Logs delegate messages properly

3. **Enhanced Diagnostic Logging** (`chat_manager.py`)
   - Added comprehensive logging to delegate discovery (both multi-input and single-input paths)
   - Added detailed DocAware integration logging
   - Logs when/why DocAware is skipped

## Expected Behavior After Fix

When you run the workflow again, you should see:

```
INFO 👥 PARALLEL: Executing GroupChatManager Chat Manager 1 with delegate support
INFO 📥 PARALLEL: GroupChatManager Chat Manager 1 has 1 input source - using single-input mode
INFO 👥 GROUP CHAT MANAGER: Starting enhanced execution for Chat Manager 1
INFO 🔍 DELEGATE DISCOVERY (SINGLE-INPUT): Chat Manager ID: f312db7a-4827-4c7f-83aa-adff98eaa846, Total edges: 11, Total nodes: 11
INFO 🔍 DELEGATE DISCOVERY (SINGLE-INPUT): Found X edges with type='delegate'
INFO 🤝 GROUP CHAT MANAGER: Found X connected delegate agents
INFO 🔄 GROUP CHAT MANAGER: Round 1/10
INFO 🤝 DELEGATE: Starting execution for Delegate 1
INFO 📚 DOCAWARE CHECK: Delegate Delegate 1 - DocAware enabled: True, Project ID: 1f47a478-1991-469e-ba4f-682fb8623ee3
INFO 📚 DOCAWARE: Processing DocAware for delegate Delegate 1
INFO 📚 DOCAWARE: Added document context to delegate Delegate 1 prompt (1307 chars)
INFO ✅ GROUP CHAT MANAGER: Successfully executed delegate Delegate 1 - response length: 1234 chars
```

## Pipeline Flow (After Fix)

### Round Robin Mode

1. **GroupChatManager Execution** (Parallel or Sequential)
   - Discovers delegates via `delegate`-type edges
   - Initializes delegate status tracking

2. **Delegate Execution Loop**
   - For each round (up to `max_rounds`):
     - Executes all delegates in parallel
     - For each delegate:
       - **DocAware Check**: `is_docaware_enabled(delegate_node)`
       - **Query Extraction**: `extract_search_query_from_aggregated_input()`
       - **Document Search**: `get_docaware_context_from_query()`
       - **Context Addition**: Adds document context to system message
       - **LLM Call**: Executes delegate with enriched context

3. **Final Aggregation**
   - GroupChatManager synthesizes delegate responses
   - Returns final summary

### Intelligent Delegation Mode

1. **Subquery Generation**: Splits input into subqueries
2. **Delegate Matching**: Matches subqueries to delegates based on capabilities
3. **Delegate Execution**: Similar to Round Robin, but per subquery
4. **DocAware Integration**: Runs for each delegate per subquery

## QueryRefinement Integration

When QueryRefinement is enabled:
1. Query is extracted from aggregated input
2. Query is refined using LLM (if enabled in delegate config)
3. Refined query is used for DocAware search
4. Results are added to delegate context

## Verification Steps

After the fix, verify:

1. **Delegate Discovery**:
   ```bash
   docker logs ai_catalogue_backend 2>&1 | grep "DELEGATE DISCOVERY"
   ```
   Should show delegate discovery logs

2. **Delegate Execution**:
   ```bash
   docker logs ai_catalogue_backend 2>&1 | grep "DELEGATE.*Starting execution"
   ```
   Should show delegate execution logs

3. **DocAware Integration**:
   ```bash
   docker logs ai_catalogue_backend 2>&1 | grep "DOCAWARE.*Delegate"
   ```
   Should show DocAware processing for each delegate

4. **Document Context**:
   ```bash
   docker logs ai_catalogue_backend 2>&1 | grep "Added document context to delegate"
   ```
   Should show document context being added

## Code Locations

- **Parallel Execution Fix**: `backend/agent_orchestration/workflow_executor.py:2107-2155`
- **Result Processing**: `backend/agent_orchestration/workflow_executor.py:2218-2250`
- **Delegate Discovery Logging**: `backend/agent_orchestration/chat_manager.py:98-130` (multi-input), `811-850` (single-input)
- **DocAware Integration**: `backend/agent_orchestration/chat_manager.py:436-459`

## Next Steps

1. **Test the Fix**: Run the workflow again and check logs for delegate execution
2. **Verify DocAware**: Ensure delegates receive document context
3. **Check QueryRefinement**: If enabled, verify queries are refined before search
4. **Monitor Performance**: Check delegate execution times and DocAware search times
