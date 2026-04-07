# Parallelization Analysis: Group Chat Manager and Delegate Orchestration

## Executive Summary

This document describes the execution flow between Group Chat Manager (GCM) and
Delegate agents under the **tool-based delegation** model that replaced the
earlier round-robin and intelligent-delegation modes.

## Architecture

### Workflow-level

- GCM executes as a single node in the workflow execution sequence.
- Delegates are **not** in the main execution sequence — they are discovered at
  runtime via `delegate`-type graph edges and executed internally by the GCM.
- The workflow executor already parallelises independent nodes at the same
  topological depth, so a GCM can run in parallel with other non-dependent nodes.

### Two-phase GCM execution

1. **Phase 1 — Planning** (sequential, single LLM call):
   The GCM LLM receives the user input, upstream context, and a listing of
   connected delegates (name + description). It produces a numbered plan.

2. **Phase 2 — Tool loop** (iterative, with per-turn parallelism):
   - The GCM LLM receives the plan and one OpenAI-style function tool per
     connected delegate (`tasks: string[]`).
   - Each iteration: the LLM returns zero or more tool calls.
   - **All tool calls in one turn run in parallel** via `asyncio.gather`.
   - Tool results are fed back; the loop repeats until the LLM produces a
     final answer with no tool calls (or a max-iteration cap is hit).

### Delegate execution

Each delegate tool call dispatches to `run_delegate_doc_tool_loop` in
`delegate_tool_executor.py`. When `doc_tool_calling` is enabled on the
delegate, the delegate itself enters a plan → tool-call → synthesis loop
against project documents (same loop used by standalone agents). Otherwise
a single LLM call is made.

## Parallelism points

| Phase | Parallel? | Notes |
|-------|-----------|-------|
| Input aggregation | N/A | Handled before GCM is called |
| Delegate discovery | ✅ | Graph traversal, no I/O |
| Phase-1 planning | ❌ | Single LLM call (sequential by nature) |
| Phase-2 tool calls (same turn) | ✅ | `asyncio.gather` on all calls |
| Delegate doc-tool-calling loop | ✅ per delegate | Each delegate runs its own loop independently |
| Final synthesis | ❌ | Single LLM call after all tool results |

## Key files

- `backend/agent_orchestration/delegate_tool_executor.py` — tool schema builder,
  delegate doc-tool loop, two-phase orchestration entry point.
- `backend/agent_orchestration/chat_manager.py` —
  `execute_group_chat_manager_with_multiple_inputs` (main entry),
  `execute_group_chat_manager` (single-input wrapper).
- `backend/agent_orchestration/workflow_executor.py` — GCM routing in both the
  main sequential executor and the parallel executor.
