#!/usr/bin/env python3
"""
Comprehensive Experiment Log Analysis
====================================

Analyzes experiment logs and database results to extract:
1. Workflow execution times (with/without DocAware)
2. DocAware retrieval overhead
3. Evaluation results comparison
"""

import os
import sys
import json
import re
from collections import defaultdict
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from users.models import WorkflowEvaluation, WorkflowEvaluationResult, WorkflowExecution
from django.db.models import Avg, Min, Max, Count, Q


def parse_log_line(line: str) -> Dict[str, Any] | None:
    """Parse an EXP_METRIC log line"""
    match = re.search(r'EXP_METRIC_(\w+)\s*\|\s*(.+)', line)
    if not match:
        return None
    
    metric_type = match.group(1)
    json_str = match.group(2).strip()
    
    try:
        payload = json.loads(json_str)
        payload['_metric_type'] = metric_type
        return payload
    except json.JSONDecodeError:
        return None


def read_docker_logs() -> List[str]:
    """Read logs from docker compose"""
    import subprocess
    try:
        result = subprocess.run(
            ['docker', 'compose', 'logs', 'backend', '--tail=2000'],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '..')
        )
        return result.stdout.split('\n')
    except Exception as e:
        print(f"⚠️  Could not read docker logs: {e}")
        return []


def analyze_workflow_execution_metrics(metrics: List[Dict[str, Any]]):
    """Analyze workflow execution timing metrics"""
    workflow_metrics = [m for m in metrics if m.get('_metric_type') == 'WORKFLOW_EXECUTION']
    
    if not workflow_metrics:
        print("❌ No EXP_METRIC_WORKFLOW_EXECUTION metrics found")
        return None
    
    # Group by workflow
    by_workflow = defaultdict(list)
    for m in workflow_metrics:
        wf_id = m.get('workflow_id', 'unknown')
        by_workflow[wf_id].append(m)
    
    results = {}
    for wf_id, executions in by_workflow.items():
        workflow_name = executions[0].get('workflow_name', 'Unknown')
        durations = [e.get('duration_s', 0) for e in executions if e.get('duration_s')]
        
        if not durations:
            continue
        
        results[wf_id] = {
            'workflow_name': workflow_name,
            'count': len(executions),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'parallel_count': sum(1 for e in executions if e.get('parallel_batches', 0) > 0),
            'sequential_count': sum(1 for e in executions if e.get('parallel_batches', 0) == 0),
        }
    
    return results


def analyze_docaware_metrics(metrics: List[Dict[str, Any]]):
    """Analyze DocAware retrieval overhead"""
    docaware_metrics = [
        m for m in metrics 
        if m.get('_metric_type') in ['DOCAWARE_SINGLE', 'DOCAWARE_CONTEXT']
    ]
    
    if not docaware_metrics:
        return None
    
    retrieval_times = [m.get('search_duration_ms', 0) for m in docaware_metrics if m.get('search_duration_ms')]
    
    if not retrieval_times:
        return None
    
    # Group by agent
    by_agent = defaultdict(list)
    for m in docaware_metrics:
        agent = m.get('agent_name', 'unknown')
        if m.get('search_duration_ms'):
            by_agent[agent].append(m.get('search_duration_ms'))
    
    agent_stats = {}
    for agent, times in by_agent.items():
        agent_stats[agent] = {
            'count': len(times),
            'avg_ms': sum(times) / len(times),
            'min_ms': min(times),
            'max_ms': max(times),
        }
    
    return {
        'total_calls': len(docaware_metrics),
        'avg_retrieval_ms': sum(retrieval_times) / len(retrieval_times),
        'min_retrieval_ms': min(retrieval_times),
        'max_retrieval_ms': max(retrieval_times),
        'by_agent': agent_stats
    }


def analyze_evaluation_results():
    """Analyze evaluation results from database"""
    evaluations = WorkflowEvaluation.objects.all().order_by('-created_at')[:5]
    
    results = []
    for eval_obj in evaluations:
        eval_results = WorkflowEvaluationResult.objects.filter(evaluation=eval_obj)
        
        if not eval_results.exists():
            continue
        
        stats = eval_results.aggregate(
            avg_time=Avg('execution_time_seconds'),
            min_time=Min('execution_time_seconds'),
            max_time=Max('execution_time_seconds'),
            total=Count('id'),
            successful=Count('id', filter=Q(status='success')),
            avg_bert=Avg('bert_score'),
            avg_semantic=Avg('semantic_similarity'),
            avg_score=Avg('average_score'),
        )
        
        results.append({
            'evaluation_id': str(eval_obj.evaluation_id),
            'workflow_name': eval_obj.workflow.name,
            'csv_filename': eval_obj.csv_filename,
            'status': eval_obj.status,
            'completed': eval_obj.completed_rows,
            'total': eval_obj.total_rows,
            'stats': stats
        })
    
    return results


def print_comparison(without_rag: Dict, with_rag: Dict):
    """Print comparison between runs with and without RAG"""
    print("\n" + "="*80)
    print("📊 COMPARISON: Without RAG vs With RAG")
    print("="*80)
    
    if not without_rag or not with_rag:
        print("⚠️  Need both runs to compare")
        return
    
    wf_without = list(without_rag.values())[0] if without_rag else None
    wf_with = list(with_rag.values())[0] if with_rag else None
    
    if not wf_without or not wf_with:
        print("⚠️  Could not find matching workflows")
        return
    
    print(f"\n⏱️  EXECUTION TIME:")
    print(f"   Without RAG: {wf_without['avg_duration']:.3f}s (avg)")
    print(f"   With RAG:    {wf_with['avg_duration']:.3f}s (avg)")
    
    overhead = wf_with['avg_duration'] - wf_without['avg_duration']
    overhead_pct = (overhead / wf_without['avg_duration']) * 100 if wf_without['avg_duration'] > 0 else 0
    
    print(f"   📈 RAG Overhead: +{overhead:.3f}s ({overhead_pct:.1f}% increase)")
    
    print(f"\n📊 EXECUTION COUNT:")
    print(f"   Without RAG: {wf_without['count']} executions")
    print(f"   With RAG:    {wf_with['count']} executions")


def main():
    print("🔍 Analyzing Experiment Logs and Database Results...")
    print("="*80)
    
    # Read logs
    print("\n📋 Reading logs from docker...")
    log_lines = read_docker_logs()
    
    # Parse metrics
    metrics = []
    for line in log_lines:
        metric = parse_log_line(line)
        if metric:
            metrics.append(metric)
    
    print(f"✅ Found {len(metrics)} experiment metric entries")
    
    # Analyze workflow execution
    print("\n📊 Analyzing workflow execution metrics...")
    workflow_metrics = analyze_workflow_execution_metrics(metrics)
    
    if workflow_metrics:
        print("\n" + "="*80)
        print("WORKFLOW EXECUTION METRICS")
        print("="*80)
        for wf_id, stats in workflow_metrics.items():
            print(f"\n📊 Workflow: {stats['workflow_name']}")
            print(f"   Executions: {stats['count']}")
            print(f"   Average Duration: {stats['avg_duration']:.3f}s")
            print(f"   Min Duration: {stats['min_duration']:.3f}s")
            print(f"   Max Duration: {stats['max_duration']:.3f}s")
            print(f"   Parallel: {stats['parallel_count']}, Sequential: {stats['sequential_count']}")
    
    # Analyze DocAware
    print("\n📊 Analyzing DocAware metrics...")
    docaware_stats = analyze_docaware_metrics(metrics)
    
    if docaware_stats:
        print("\n" + "="*80)
        print("DOCAWARE RETRIEVAL OVERHEAD")
        print("="*80)
        print(f"   Total DocAware Calls: {docaware_stats['total_calls']}")
        print(f"   Average Retrieval Time: {docaware_stats['avg_retrieval_ms']:.2f}ms")
        print(f"   Min Retrieval Time: {docaware_stats['min_retrieval_ms']:.2f}ms")
        print(f"   Max Retrieval Time: {docaware_stats['max_retrieval_ms']:.2f}ms")
        
        if docaware_stats['by_agent']:
            print(f"\n   Per-Agent Breakdown:")
            for agent, stats in docaware_stats['by_agent'].items():
                print(f"      {agent}: {stats['avg_ms']:.2f}ms avg (n={stats['count']})")
    else:
        print("   ✅ No DocAware metrics found - agents ran without RAG")
    
    # Analyze evaluation results
    print("\n📊 Analyzing evaluation results from database...")
    eval_results = analyze_evaluation_results()
    
    if eval_results:
        print("\n" + "="*80)
        print("EVALUATION RESULTS (Database)")
        print("="*80)
        for eval_data in eval_results:
            print(f"\n📋 {eval_data['csv_filename']}")
            print(f"   Workflow: {eval_data['workflow_name']}")
            print(f"   Status: {eval_data['status']}")
            print(f"   Completed: {eval_data['completed']}/{eval_data['total']} rows")
            
            stats = eval_data['stats']
            if stats['avg_time']:
                print(f"   ⏱️  Execution Time:")
                print(f"      Average: {stats['avg_time']:.3f}s")
                print(f"      Min: {stats['min_time']:.3f}s")
                print(f"      Max: {stats['max_time']:.3f}s")
            
            if stats['avg_score']:
                print(f"   📊 Quality Scores:")
                print(f"      Average: {stats['avg_score']:.3f}")
                if stats['avg_bert']:
                    print(f"      BERTScore: {stats['avg_bert']:.3f}")
                if stats['avg_semantic']:
                    print(f"      Semantic Similarity: {stats['avg_semantic']:.3f}")
    
    # Summary
    print("\n" + "="*80)
    print("📝 SUMMARY FOR PAPER TABLE")
    print("="*80)
    
    if workflow_metrics:
        wf_stats = list(workflow_metrics.values())[0]
        print(f"\n✅ Workflow Execution Time: {wf_stats['avg_duration']:.3f}s (avg)")
        print(f"   Range: {wf_stats['min_duration']:.3f}s - {wf_stats['max_duration']:.3f}s")
    
    if docaware_stats:
        print(f"\n✅ DocAware Overhead: {docaware_stats['avg_retrieval_ms']:.2f}ms per retrieval")
        print(f"   Total DocAware calls: {docaware_stats['total_calls']}")
    else:
        print(f"\n✅ DocAware: Not enabled (baseline measurement)")
    
    if eval_results and eval_results[0]['stats']['avg_time']:
        print(f"\n✅ Evaluation Average Time: {eval_results[0]['stats']['avg_time']:.3f}s")
        if eval_results[0]['stats']['avg_score']:
            print(f"   Average Quality Score: {eval_results[0]['stats']['avg_score']:.3f}")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()

