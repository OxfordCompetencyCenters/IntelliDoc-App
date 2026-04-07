#!/usr/bin/env python3
"""
Quick script to check evaluation execution times from database
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from users.models import WorkflowEvaluation, WorkflowEvaluationResult
from django.db.models import Avg, Min, Max, Count


def main():
    # Get most recent evaluation
    latest_eval = WorkflowEvaluation.objects.all().order_by('-created_at').first()
    
    if not latest_eval:
        print("❌ No evaluations found in database")
        return
    
    print("="*80)
    print(f"📊 Latest Evaluation: {latest_eval.csv_filename}")
    print(f"   Workflow: {latest_eval.workflow.name}")
    print(f"   Status: {latest_eval.status}")
    print(f"   Completed: {latest_eval.completed_rows}/{latest_eval.total_rows} rows")
    print("="*80)
    
    # Get results
    results = WorkflowEvaluationResult.objects.filter(evaluation=latest_eval)
    
    if not results.exists():
        print("❌ No results found for this evaluation")
        return
    
    # Calculate statistics
    stats = results.aggregate(
        avg_time=Avg('execution_time_seconds'),
        min_time=Min('execution_time_seconds'),
        max_time=Max('execution_time_seconds'),
        total=Count('id'),
        successful=Count('id', filter=models.Q(status='success')),
        avg_bert=Avg('bert_score'),
        avg_semantic=Avg('semantic_similarity'),
        avg_score=Avg('average_score'),
    )
    
    print(f"\n⏱️  EXECUTION TIME STATISTICS:")
    print(f"   Average: {stats['avg_time']:.3f}s")
    print(f"   Minimum: {stats['min_time']:.3f}s")
    print(f"   Maximum: {stats['max_time']:.3f}s")
    print(f"   Total Executions: {stats['total']}")
    
    if stats['avg_score']:
        print(f"\n📊 QUALITY SCORES:")
        print(f"   Average Score: {stats['avg_score']:.3f}")
        if stats['avg_bert']:
            print(f"   BERTScore: {stats['avg_bert']:.3f}")
        if stats['avg_semantic']:
            print(f"   Semantic Similarity: {stats['avg_semantic']:.3f}")
    
    # Show first 5 individual results
    print(f"\n📋 First 5 Results:")
    for result in results[:5]:
        print(f"   Row {result.row_number}: {result.execution_time_seconds:.3f}s | Score: {result.average_score:.3f if result.average_score else 'N/A'}")
    
    print("\n" + "="*80)
    print("💡 To check for DocAware overhead, look for EXP_METRIC_DOCAWARE logs")
    print("   Run: docker compose logs backend | grep EXP_METRIC_DOCAWARE")
    print("="*80)


if __name__ == '__main__':
    from django.db import models
    main()

