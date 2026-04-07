#!/usr/bin/env python3
"""
Extract Experiment Metrics from Logs and Database
=================================================

This script extracts experiment metrics from:
1. Backend logs (EXP_METRIC_* lines)
2. Database evaluation results (WorkflowEvaluationResult)

Usage:
    python scripts/extract_experiment_metrics.py [--log-file path/to/logs.txt] [--evaluation-id uuid]
"""

import json
import re
import sys
import os
import argparse
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from users.models import WorkflowEvaluation, WorkflowEvaluationResult, WorkflowExecution


def parse_log_line(line: str) -> Dict[str, Any] | None:
    """Parse an EXP_METRIC log line and extract JSON payload"""
    # Pattern: EXP_METRIC_<TYPE> | {json}
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
        print(f"⚠️  Failed to parse JSON from line: {line[:100]}...")
        return None


def extract_metrics_from_logs(log_file: str = None) -> List[Dict[str, Any]]:
    """Extract all EXP_METRIC lines from logs"""
    metrics = []
    
    if log_file and os.path.exists(log_file):
        # Read from file
        with open(log_file, 'r') as f:
            for line in f:
                metric = parse_log_line(line)
                if metric:
                    metrics.append(metric)
    else:
        # Try to read from docker logs
        print("📋 Reading from docker logs...")
        import subprocess
        try:
            result = subprocess.run(
                ['docker', 'compose', 'logs', 'backend', '--tail=1000'],
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), '..')
            )
            for line in result.stdout.split('\n'):
                metric = parse_log_line(line)
                if metric:
                    metrics.append(metric)
        except Exception as e:
            print(f"⚠️  Could not read docker logs: {e}")
            print("   Please provide --log-file path or pipe logs to stdin")
    
    return metrics


def get_evaluation_metrics(evaluation_id: str = None) -> List[Dict[str, Any]]:
    """Get evaluation metrics from database"""
    from django.db.models import Avg, Count, Min, Max, Q
    
    if evaluation_id:
        evaluations = WorkflowEvaluation.objects.filter(evaluation_id=evaluation_id)
    else:
        # Get most recent evaluation
        evaluations = WorkflowEvaluation.objects.all().order_by('-created_at')[:1]
    
    results = []
    for eval_obj in evaluations:
        eval_results = WorkflowEvaluationResult.objects.filter(evaluation=eval_obj)
        
        stats = eval_results.aggregate(
            avg_execution_time=Avg('execution_time_seconds'),
            min_execution_time=Min('execution_time_seconds'),
            max_execution_time=Max('execution_time_seconds'),
            total_rows=Count('id'),
            successful=Count('id', filter=Q(status='success')),
            avg_bert_score=Avg('bert_score'),
            avg_semantic_similarity=Avg('semantic_similarity'),
            avg_average_score=Avg('average_score'),
        )
        
        results.append({
            'evaluation_id': str(eval_obj.evaluation_id),
            'workflow_name': eval_obj.workflow.name,
            'csv_filename': eval_obj.csv_filename,
            'total_rows': eval_obj.total_rows,
            'completed_rows': eval_obj.completed_rows,
            'status': eval_obj.status,
            'stats': stats,
            'individual_results': [
                {
                    'row_number': r.row_number,
                    'execution_time_seconds': r.execution_time_seconds,
                    'average_score': r.average_score,
                    'bert_score': r.bert_score,
                    'semantic_similarity': r.semantic_similarity,
                }
                for r in eval_results[:10]  # First 10 for preview
            ]
        })
    
    return results


def print_workflow_execution_metrics(metrics: List[Dict[str, Any]]):
    """Print workflow execution timing metrics"""
    workflow_metrics = [m for m in metrics if m.get('_metric_type') == 'WORKFLOW_EXECUTION']
    
    if not workflow_metrics:
        print("❌ No EXP_METRIC_WORKFLOW_EXECUTION metrics found")
        return
    
    print("\n" + "="*80)
    print("WORKFLOW EXECUTION METRICS (Sequential vs Parallel)")
    print("="*80)
    
    # Group by workflow
    by_workflow = {}
    for m in workflow_metrics:
        wf_id = m.get('workflow_id', 'unknown')
        if wf_id not in by_workflow:
            by_workflow[wf_id] = []
        by_workflow[wf_id].append(m)
    
    for wf_id, executions in by_workflow.items():
        workflow_name = executions[0].get('workflow_name', 'Unknown')
        print(f"\n📊 Workflow: {workflow_name} ({wf_id[:8]}...)")
        print(f"   Total Executions: {len(executions)}")
        
        durations = [e.get('duration_s', 0) for e in executions]
        if durations:
            print(f"   Average Duration: {sum(durations)/len(durations):.3f}s")
            print(f"   Min Duration: {min(durations):.3f}s")
            print(f"   Max Duration: {max(durations):.3f}s")
        
        # Check for parallel execution
        parallel_count = sum(1 for e in executions if e.get('parallel_batches', 0) > 0)
        sequential_count = len(executions) - parallel_count
        
        print(f"   Parallel Executions: {parallel_count}")
        print(f"   Sequential Executions: {sequential_count}")
        
        if parallel_count > 0:
            parallel_durations = [e.get('duration_s', 0) for e in executions if e.get('parallel_batches', 0) > 0]
            if parallel_durations:
                avg_parallel = sum(parallel_durations) / len(parallel_durations)
                print(f"   Avg Parallel Duration: {avg_parallel:.3f}s")
        
        if sequential_count > 0:
            sequential_durations = [e.get('duration_s', 0) for e in executions if e.get('parallel_batches', 0) == 0]
            if sequential_durations:
                avg_sequential = sum(sequential_durations) / len(sequential_durations)
                print(f"   Avg Sequential Duration: {avg_sequential:.3f}s")
                
                if parallel_count > 0 and avg_parallel:
                    speedup = avg_sequential / avg_parallel
                    print(f"   ⚡ Parallel Speedup: {speedup:.2f}x")


def print_docaware_metrics(metrics: List[Dict[str, Any]]):
    """Print DocAware retrieval overhead metrics"""
    docaware_metrics = [
        m for m in metrics 
        if m.get('_metric_type') in ['DOCAWARE_SINGLE', 'DOCAWARE_CONTEXT']
    ]
    
    if not docaware_metrics:
        print("\n✅ No DocAware metrics found (agents running without DocAware)")
        return
    
    print("\n" + "="*80)
    print("DOCAWARE RETRIEVAL METRICS")
    print("="*80)
    
    retrieval_times = [m.get('search_duration_ms', 0) for m in docaware_metrics]
    if retrieval_times:
        print(f"   Total DocAware Calls: {len(docaware_metrics)}")
        print(f"   Average Retrieval Time: {sum(retrieval_times)/len(retrieval_times):.2f}ms")
        print(f"   Min Retrieval Time: {min(retrieval_times):.2f}ms")
        print(f"   Max Retrieval Time: {max(retrieval_times):.2f}ms")
        
        # Group by agent
        by_agent = {}
        for m in docaware_metrics:
            agent = m.get('agent_name', 'unknown')
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(m.get('search_duration_ms', 0))
        
        print(f"\n   Per-Agent Averages:")
        for agent, times in by_agent.items():
            print(f"      {agent}: {sum(times)/len(times):.2f}ms (n={len(times)})")


def print_evaluation_metrics(eval_metrics: List[Dict[str, Any]]):
    """Print evaluation results from database"""
    if not eval_metrics:
        print("\n❌ No evaluation metrics found in database")
        return
    
    print("\n" + "="*80)
    print("EVALUATION RESULTS (from Database)")
    print("="*80)
    
    for eval_data in eval_metrics:
        print(f"\n📋 Evaluation: {eval_data['csv_filename']}")
        print(f"   Workflow: {eval_data['workflow_name']}")
        print(f"   Status: {eval_data['status']}")
        print(f"   Rows: {eval_data['completed_rows']}/{eval_data['total_rows']}")
        
        stats = eval_data['stats']
        if stats['avg_execution_time']:
            print(f"\n   ⏱️  Execution Time:")
            print(f"      Average: {stats['avg_execution_time']:.3f}s")
            print(f"      Min: {stats['min_execution_time']:.3f}s")
            print(f"      Max: {stats['max_execution_time']:.3f}s")
        
        if stats['avg_average_score']:
            print(f"\n   📊 Quality Scores:")
            print(f"      Average Score: {stats['avg_average_score']:.3f}")
            if stats['avg_bert_score']:
                print(f"      BERTScore: {stats['avg_bert_score']:.3f}")
            if stats['avg_semantic_similarity']:
                print(f"      Semantic Similarity: {stats['avg_semantic_similarity']:.3f}")


def main():
    parser = argparse.ArgumentParser(description='Extract experiment metrics from logs and database')
    parser.add_argument('--log-file', help='Path to log file (default: read from docker logs)')
    parser.add_argument('--evaluation-id', help='Specific evaluation ID to analyze')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Extract metrics from logs
    print("🔍 Extracting metrics from logs...")
    log_metrics = extract_metrics_from_logs(args.log_file)
    print(f"✅ Found {len(log_metrics)} experiment metric entries")
    
    # Get evaluation metrics from database
    print("\n🔍 Extracting evaluation metrics from database...")
    try:
        eval_metrics = get_evaluation_metrics(args.evaluation_id)
        print(f"✅ Found {len(eval_metrics)} evaluation(s)")
    except Exception as e:
        print(f"⚠️  Could not access database: {e}")
        eval_metrics = []
    
    if args.json:
        # Output as JSON
        output = {
            'log_metrics': log_metrics,
            'evaluation_metrics': eval_metrics
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        # Print formatted output
        print_workflow_execution_metrics(log_metrics)
        print_docaware_metrics(log_metrics)
        print_evaluation_metrics(eval_metrics)
        
        print("\n" + "="*80)
        print("💡 Tip: Use --json flag for machine-readable output")
        print("="*80)


if __name__ == '__main__':
    main()

