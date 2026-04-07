# Intelligent Delegation Accuracy Metric - Root Cause Analysis

## Problem
The "Intelligent Delegation Accuracy" metric under System Performance Analysis is not being captured.

## Root Cause

The metric is **only logged when GroupChatManager nodes are configured with `delegation_mode: 'intelligent'`**. 

Looking at the workflow execution logs:
- GroupChatManager nodes are executing successfully
- But there are **no logs** showing:
  - `🔧 GROUP CHAT MANAGER (MULTI-INPUT): Delegation mode: intelligent`
  - `🧠 GROUP CHAT MANAGER (MULTI-INPUT): Using intelligent delegation mode`
  - `EXP_METRIC_INTELLIGENT_DELEGATION`

This indicates the GroupChatManager nodes are using the **default `'round_robin'` mode** instead of `'intelligent'` mode.

## How the Metric Works

1. **Metric Logging Location**: `backend/agent_orchestration/chat_manager.py` line 1651
   - Only executed when `execute_group_chat_manager_intelligent_delegation()` is called
   - Which only happens when `delegation_mode == 'intelligent'` (line 63)

2. **Metric Storage**: The metric is stored in the `ExperimentMetric` table with:
   - `experiment_type='intelligent_delegation'`
   - Contains: `total_subqueries`, `successful_delegations`, `broadcast_subqueries`, etc.

3. **Metric Retrieval**: `backend/api/universal_project_views.py` line 398
   - Filters for `experiment_type='intelligent_delegation'`
   - If none found, returns message: `'Requires workflow with Group Chat Manager using intelligent delegation mode'`

## Solution

### Step 1: Configure GroupChatManager Nodes

In the Agent Orchestration UI:

1. Select each **GroupChatManager** node in your workflow
2. Open the **Node Properties Panel**
3. Find the **"Delegation Mode"** dropdown
4. Change from **"Round Robin (Default)"** to **"Intelligent Delegation"**
5. Save the workflow

### Step 2: Verify Configuration

After updating, check the node's `data` object in the workflow JSON. It should contain:
```json
{
  "delegation_mode": "intelligent",
  ...
}
```

### Step 3: Execute Workflow

Run the workflow again. You should now see in the logs:
```
INFO 🔧 GROUP CHAT MANAGER (MULTI-INPUT): Delegation mode: intelligent
INFO 🧠 GROUP CHAT MANAGER (MULTI-INPUT): Using intelligent delegation mode
INFO EXP_METRIC_INTELLIGENT_DELEGATION | {...}
INFO ✅ Stored intelligent delegation experiment metric: id=..., project=...
```

### Step 4: Check System Performance Analysis

After execution, the System Performance Analysis page should show:
- **Routing Accuracy (%)**: Percentage of successful delegations
- **Broadcast Rate (%)**: Percentage of subqueries broadcast to all delegates

## Code References

- **Delegation Mode Check**: `backend/agent_orchestration/chat_manager.py:59-63`
- **Intelligent Delegation Execution**: `backend/agent_orchestration/chat_manager.py:1188-1752`
- **Metric Logging**: `backend/agent_orchestration/chat_manager.py:1651`
- **Metric Storage**: `backend/agent_orchestration/chat_manager.py:1654-1677`
- **Metric Retrieval**: `backend/api/universal_project_views.py:397-421`
- **UI Configuration**: `frontend/my-sveltekit-app/src/lib/components/NodePropertiesPanel.svelte:1522-1543`

## Additional Notes

1. **Intelligent Delegation Requirements**:
   - Works best with **multiple input sources**
   - Automatically splits input into subqueries
   - Routes subqueries to specialized delegate agents based on capabilities
   - Uses confidence thresholds for routing decisions

2. **Round Robin vs Intelligent**:
   - **Round Robin**: All delegates process the same input in sequence/parallel rounds
   - **Intelligent**: Input is split into subqueries, each routed to the most appropriate delegate(s)

3. **Why Default is Round Robin**:
   - Round robin is simpler and more predictable
   - Intelligent delegation requires more configuration (confidence thresholds, etc.)
   - Intelligent delegation is an advanced feature for complex workflows

## Verification Commands

To check if metrics are being stored:

```bash
# Check database for intelligent_delegation metrics
docker exec -it ai_catalogue_backend python manage.py shell
```

```python
from users.models import ExperimentMetric
metrics = ExperimentMetric.objects.filter(experiment_type='intelligent_delegation')
print(f"Found {metrics.count()} intelligent delegation metrics")
for m in metrics:
    print(f"  - ID: {m.id}, Project: {m.project.name}, Total Subqueries: {m.metric_data.get('total_subqueries', 0)}")
```

## Expected Log Output (When Working)

When intelligent delegation is properly configured and executed, you should see:

```
INFO 🔧 GROUP CHAT MANAGER (MULTI-INPUT): Delegation mode: intelligent
INFO 🧠 GROUP CHAT MANAGER (MULTI-INPUT): Using intelligent delegation mode
INFO 🧠 GROUP CHAT MANAGER (INTELLIGENT): Starting intelligent delegation for Chat Manager 1
INFO 🧠 GROUP CHAT MANAGER (INTELLIGENT): Split input into 3 subqueries
INFO 🧠 GROUP CHAT MANAGER (INTELLIGENT): Matching subqueries to delegates...
INFO ✅ GROUP CHAT MANAGER (INTELLIGENT): Completed parallel delegation in 2.45s
INFO EXP_METRIC_INTELLIGENT_DELEGATION | {"experiment": "intelligent_delegation", "total_subqueries": 3, "successful_delegations": 3, ...}
INFO ✅ Stored intelligent delegation experiment metric: id=123, project=...
```
