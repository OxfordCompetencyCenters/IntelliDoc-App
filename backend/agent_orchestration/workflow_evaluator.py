"""
Workflow Evaluator Service
==========================

Service for evaluating workflows using CSV input/output pairs and various metrics.
"""

import logging
import csv
import io
import time
import asyncio
import os
from typing import Dict, List, Any, Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import (
    AgentWorkflow, WorkflowExecution, WorkflowEvaluation, WorkflowEvaluationResult,
    EvaluationStatus, EvaluationResultStatus
)

logger = logging.getLogger(__name__)


class WorkflowEvaluator:
    """Service for evaluating workflows with CSV data"""
    
    def __init__(self, workflow_executor, llm_provider_manager, workflow_parser):
        """
        Initialize evaluator with required dependencies
        
        Args:
            workflow_executor: WorkflowExecutor instance
            llm_provider_manager: LLMProviderManager instance
            workflow_parser: WorkflowParser instance
        """
        self.workflow_executor = workflow_executor
        self.llm_provider_manager = llm_provider_manager
        self.workflow_parser = workflow_parser
    
    async def evaluate_workflow(
        self,
        workflow: AgentWorkflow,
        csv_file: Any,
        executed_by,
        evaluation_id: str = None
    ) -> WorkflowEvaluation:
        """
        Main evaluation orchestration method
        
        Args:
            workflow: AgentWorkflow instance to evaluate
            csv_file: Uploaded CSV file
            executed_by: User who initiated the evaluation
            evaluation_id: Optional evaluation ID (for resuming)
            
        Returns:
            WorkflowEvaluation instance
        """
        logger.info(f"🔍 EVALUATOR: Starting workflow evaluation for {workflow.name}")
        
        # Parse CSV file
        csv_data = self.parse_csv_file(csv_file)
        total_rows = len(csv_data)
        
        # Create or get evaluation record
        if evaluation_id:
            evaluation = await sync_to_async(WorkflowEvaluation.objects.get)(
                evaluation_id=evaluation_id
            )
        else:
            evaluation = await sync_to_async(WorkflowEvaluation.objects.create)(
                workflow=workflow,
                csv_filename=getattr(csv_file, 'name', 'uploaded.csv'),
                total_rows=total_rows,
                status=EvaluationStatus.RUNNING,
                executed_by=executed_by
            )
        
        # Auto-detect concurrency limit
        cpu_count = os.cpu_count() or 4  # Default to 4 if cpu_count() returns None
        concurrency_limit = min(total_rows, cpu_count * 2, 10)
        logger.info(f"🔀 EVALUATOR: Processing {total_rows} rows with concurrency limit: {concurrency_limit}")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Wrapper function to process row with semaphore control
        async def process_row_with_semaphore(row_index: int, row_data: Dict[str, str]):
            """Process a single row with semaphore-based concurrency control"""
            async with semaphore:
                return await self._process_evaluation_row(
                    evaluation,
                    workflow,
                    row_index,
                    row_data,
                    executed_by
                )
                
        # Create tasks for all rows
        logger.info(f"🚀 EVALUATOR: Starting parallel execution of {total_rows} rows")
        tasks = [
            process_row_with_semaphore(row_index, row_data)
            for row_index, row_data in enumerate(csv_data, start=1)
        ]
        
        # Execute all rows in parallel with error handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and update evaluation progress in batch
        completed_count = 0
        failed_count = 0
        
        for i, result in enumerate(results):
            row_index = i + 1
            row_data = csv_data[i]
            
            if isinstance(result, Exception):
                # Handle failed row
                logger.error(f"❌ EVALUATOR: Failed to process row {row_index}: {result}")
                failed_count += 1
                
                # Create failed result record
                await sync_to_async(WorkflowEvaluationResult.objects.create)(
                    evaluation=evaluation,
                    row_number=row_index,
                    input_text=row_data.get('input', ''),
                    expected_output=row_data.get('expected_output', ''),
                    status=EvaluationResultStatus.FAILED,
                    error_message=str(result)
                )
            else:
                # Success - result is already saved in _process_evaluation_row
                completed_count += 1
        
        # Batch update evaluation progress
        evaluation.completed_rows = completed_count
        evaluation.failed_rows = failed_count
        evaluation.status = EvaluationStatus.COMPLETED
        await sync_to_async(evaluation.save)(update_fields=['completed_rows', 'failed_rows', 'status'])
        
        logger.info(f"✅ EVALUATOR: Parallel execution completed - {completed_count} successful, {failed_count} failed")
        
        return evaluation
    
    def parse_csv_file(self, csv_file: Any) -> List[Dict[str, str]]:
        """
        Parse CSV file and validate format
        
        Args:
            csv_file: Uploaded CSV file
            
        Returns:
            List of dictionaries with 'input' and 'expected_output' keys
            
        Raises:
            ValueError: If CSV format is invalid
        """
        try:
            # Read file content
            if hasattr(csv_file, 'read'):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8-sig')  # utf-8-sig automatically strips BOM
                else:
                    # If already a string, strip BOM manually
                    if content.startswith('\ufeff'):
                        content = content[1:]
            else:
                content = csv_file
                # Strip BOM if present
                if isinstance(content, str) and content.startswith('\ufeff'):
                    content = content[1:]
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            rows = list(csv_reader)
            
            if not rows:
                raise ValueError("CSV file is empty")
            
            # Get available column names (case-insensitive, strip BOM and whitespace)
            # Strip BOM and whitespace from column names before normalization
            normalized_column_map = {}
            for key in rows[0].keys():
                # Strip BOM, leading/trailing whitespace, then normalize to lowercase
                clean_key = key.lstrip('\ufeff').strip().lower()
                normalized_column_map[clean_key] = key
            
            available_columns = normalized_column_map
            logger.info(f"📊 EVALUATOR: Found CSV columns: {list(rows[0].keys())}")
            
            # Normalize column names (handle case-insensitive matching and common alternatives)
            # Common input column names: input, question, query, prompt, text, user_input
            # Common output column names: expected_output, expected output, output, answer, response, expected
            input_column_map = {
                'input', 'question', 'query', 'prompt', 'text', 'user_input', 
                'user input', 'user_query', 'user query', 'input_text', 'input text'
            }
            output_column_map = {
                'expected_output', 'expected output', 'output', 'answer', 'response', 
                'expected', 'expected_answer', 'expected answer', 'ground_truth', 
                'ground truth', 'target', 'target_output', 'target output'
            }
            
            # Find input column
            input_column = None
            for col_key in input_column_map:
                if col_key in available_columns:
                    input_column = available_columns[col_key]
                    logger.info(f"📊 EVALUATOR: Mapped '{input_column}' -> 'input'")
                    break
            
            # Find output column
            output_column = None
            for col_key in output_column_map:
                if col_key in available_columns:
                    output_column = available_columns[col_key]
                    logger.info(f"📊 EVALUATOR: Mapped '{output_column}' -> 'expected_output'")
                    break
            
            # Validate that we found both required columns
            missing = []
            if not input_column:
                missing.append('input (or: question, query, prompt, text)')
            if not output_column:
                missing.append('expected_output (or: answer, response, output)')
            
            if missing:
                found_columns = list(rows[0].keys())
                raise ValueError(
                    f"CSV missing required columns: {', '.join(missing)}. "
                    f"Found columns: {', '.join(found_columns)}"
                )
            
            # Normalize rows to use standard column names
            normalized_rows = []
            for row in rows:
                normalized_row = {
                    'input': row[input_column].strip() if row.get(input_column) else '',
                    'expected_output': row[output_column].strip() if row.get(output_column) else ''
                }
                # Include any additional columns as-is
                for key, value in row.items():
                    if key not in [input_column, output_column]:
                        normalized_row[key] = value.strip() if value else ''
                normalized_rows.append(normalized_row)
            
            logger.info(f"📊 EVALUATOR: Parsed {len(normalized_rows)} rows from CSV")
            return normalized_rows
            
        except Exception as e:
            logger.error(f"❌ EVALUATOR: CSV parsing failed: {e}")
            raise ValueError(f"Failed to parse CSV file: {str(e)}")
    
    async def _process_evaluation_row(
        self,
        evaluation: WorkflowEvaluation,
        workflow: AgentWorkflow,
        row_number: int,
        row_data: Dict[str, str],
        executed_by
    ):
        """
        Process a single evaluation row
        
        Args:
            evaluation: WorkflowEvaluation instance
            workflow: AgentWorkflow instance
            row_number: Row number in CSV
            row_data: Dictionary with 'input' and 'expected_output'
            executed_by: User who initiated evaluation
            
        Returns:
            None on success, raises Exception on failure (caught by asyncio.gather with return_exceptions=True)
        """
        input_text = row_data.get('input', '')
        expected_output = row_data.get('expected_output', '')
        
        logger.info(f"🔍 EVALUATOR: Processing row {row_number} - input: {input_text[:50]}...")
        
        start_time = time.time()
        
        # Execute workflow with input substitution, passing evaluation_id
        evaluation_id_str = str(evaluation.evaluation_id) if evaluation.evaluation_id else ''
        execution_result = await self.execute_workflow_with_input(
            workflow,
            input_text,
            executed_by,
            evaluation_id=evaluation_id_str
        )
        
        execution_time = time.time() - start_time
        
        # Extract End node input messages
        workflow_output = self.extract_end_node_inputs(
            execution_result,
            workflow.graph_json
        )
        
        # Calculate metrics
        metrics = self.calculate_metrics(workflow_output, expected_output)
        
        # Create evaluation result
        await sync_to_async(WorkflowEvaluationResult.objects.create)(
            evaluation=evaluation,
            row_number=row_number,
            input_text=input_text,
            expected_output=expected_output,
            workflow_output=workflow_output,
            execution_id=execution_result.get('execution_id', ''),
            rouge_1_score=metrics['rouge_1'],
            rouge_2_score=metrics['rouge_2'],
            rouge_l_score=metrics['rouge_l'],
            bleu_score=metrics['bleu'],
            bert_score=metrics['bert_score'],
            semantic_similarity=metrics['semantic_similarity'],
            average_score=metrics['average_score'],
            status=EvaluationResultStatus.SUCCESS,
            execution_time_seconds=execution_time
        )
        
        logger.info(f"✅ EVALUATOR: Row {row_number} processed successfully - avg score: {metrics['average_score']:.3f}")
        
        # Return None on success - exceptions will be caught by asyncio.gather
    
    async def execute_workflow_with_input(
        self,
        workflow: AgentWorkflow,
        input_text: str,
        executed_by,
        evaluation_id: str = ''
    ) -> Dict[str, Any]:
        """
        Execute workflow with custom input (substitutes Start node prompt)
        
        Args:
            workflow: AgentWorkflow instance
            input_text: Input text to use as Start node prompt
            executed_by: User executing the workflow
            evaluation_id: Optional evaluation ID to link metrics to evaluation
            
        Returns:
            Execution result dictionary
        """
        logger.info(f"🚀 EVALUATOR: Executing workflow with input: {input_text[:50]}...")
        
        # Get workflow graph and make a deep copy to avoid modifying original
        import copy
        graph_json = copy.deepcopy(workflow.graph_json)
        
        # Find Start node and replace prompt with input_text
        for node in graph_json.get('nodes', []):
            if node.get('type') == 'StartNode':
                node_data = node.get('data', {})
                if isinstance(node_data, dict):
                    node_data['prompt'] = input_text
                    node['data'] = node_data
                    logger.info(f"🔄 EVALUATOR: Replaced Start node prompt with input text")
                break
        
        # Create a temporary workflow-like object with modified graph
        # We'll need to patch the workflow's graph_json property temporarily
        # Since graph_json is likely a JSONField, we can temporarily modify it
        original_graph = workflow.graph_json
        
        # Temporarily set the modified graph
        # Note: This modifies the workflow object in memory, but we'll restore it
        workflow.graph_json = graph_json
        
        try:
            # Execute workflow with modified graph, passing evaluation_id via deployment_context
            evaluation_context = {
                'evaluation_id': evaluation_id
            } if evaluation_id else None
            
            execution_result = await self.workflow_executor.execute_workflow(
                workflow, 
                executed_by,
                deployment_context=evaluation_context
            )
            
            return execution_result
            
        finally:
            # Always restore original graph, even if execution fails
            workflow.graph_json = original_graph
    
    def extract_end_node_inputs(
        self,
        execution_result: Dict[str, Any],
        workflow_graph: Dict[str, Any]
    ) -> str:
        """
        Extract all messages that feed into End node and aggregate them
        
        Args:
            execution_result: Workflow execution result dictionary
            workflow_graph: Workflow graph JSON
            
        Returns:
            Aggregated text of all messages received by End node
        """
        messages = execution_result.get('messages', [])
        
        if not messages:
            logger.warning("⚠️ EVALUATOR: No messages in execution result")
            return ""
        
        # Find End node(s)
        end_nodes = [node for node in workflow_graph.get('nodes', []) 
                    if node.get('type') == 'EndNode']
        
        if not end_nodes:
            logger.warning("⚠️ EVALUATOR: No End node found in workflow graph")
            # If no End node, return the last message content
            return messages[-1].get('content', '') if messages else ''
        
        # Find predecessor node IDs (nodes with edges pointing to End node)
        predecessor_node_ids = set()
        end_node_ids = {node['id'] for node in end_nodes}
        
        for edge in workflow_graph.get('edges', []):
            if edge.get('target') in end_node_ids:
                predecessor_node_ids.add(edge.get('source'))
        
        # Create mapping from node ID to node name
        node_id_to_name = {}
        for node in workflow_graph.get('nodes', []):
            node_id_to_name[node['id']] = node.get('data', {}).get('name', node.get('id'))
        
        # Extract messages from predecessor nodes
        end_node_messages = []
        for msg in messages:
            agent_name = msg.get('agent_name', '')
            
            # Check if this message is from a predecessor node
            # Match by agent_name (which corresponds to node name in execution)
            if agent_name in [node_id_to_name.get(node_id, node_id) for node_id in predecessor_node_ids]:
                content = msg.get('content', '')
                if content:
                    end_node_messages.append(content)
        
        # If no predecessor messages found, try to get messages just before End node
        if not end_node_messages:
            # Find the last message before End node message
            end_node_message_indices = [
                i for i, msg in enumerate(messages)
                if msg.get('agent_type') == 'EndNode' or msg.get('message_type') == 'workflow_end'
            ]
            
            if end_node_message_indices:
                # Get messages before End node (last few messages)
                last_index = end_node_message_indices[0]
                relevant_messages = messages[:last_index]
                end_node_messages = [msg.get('content', '') for msg in relevant_messages if msg.get('content')]
        
        # Aggregate messages (combine with newlines)
        aggregated_output = '\n\n'.join(end_node_messages) if end_node_messages else ''
        
        logger.info(f"📝 EVALUATOR: Extracted {len(end_node_messages)} messages for End node input")
        
        return aggregated_output
    
    def calculate_metrics(self, workflow_output: str, expected_output: str) -> Dict[str, float]:
        """
        Calculate comprehensive evaluation metrics
        
        Args:
            workflow_output: Output from workflow execution
            expected_output: Expected output from CSV
            
        Returns:
            Dictionary with metric scores
        """
        if not workflow_output or not expected_output:
            logger.warning("⚠️ EVALUATOR: Empty output or expected output, returning zero scores")
            return {
                'rouge_1': 0.0,
                'rouge_2': 0.0,
                'rouge_l': 0.0,
                'bleu': 0.0,
                'bert_score': 0.0,
                'semantic_similarity': 0.0,
                'average_score': 0.0
            }
        
        metrics = {}
        
        try:
            # ROUGE scores
            from rouge_score import rouge_scorer
            scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
            rouge_scores = scorer.score(expected_output, workflow_output)
            metrics['rouge_1'] = rouge_scores['rouge1'].fmeasure
            metrics['rouge_2'] = rouge_scores['rouge2'].fmeasure
            metrics['rouge_l'] = rouge_scores['rougeL'].fmeasure
            
        except Exception as e:
            logger.error(f"❌ EVALUATOR: ROUGE calculation failed: {e}")
            metrics['rouge_1'] = 0.0
            metrics['rouge_2'] = 0.0
            metrics['rouge_l'] = 0.0
        
        try:
            # BLEU score
            from sacrebleu import BLEU
            bleu = BLEU()
            bleu_result = bleu.sentence_score(workflow_output, [expected_output])
            metrics['bleu'] = bleu_result.score / 100.0
            
        except Exception as e:
            logger.error(f"❌ EVALUATOR: BLEU calculation failed: {e}")
            metrics['bleu'] = 0.0
        
        try:
            # BERTScore (optional - requires internet or cached models)
            from bert_score import score
            import os
            
            # Try to use offline mode if HF_HOME or TRANSFORMERS_CACHE is set
            # Otherwise, try to download (may fail in offline environments)
            try:
                P, R, F1 = score(
                    [workflow_output], 
                    [expected_output], 
                    lang='en', 
                    verbose=False,
                    device='cpu'  # Use CPU to avoid GPU issues
                )
                metrics['bert_score'] = float(F1.item())
                logger.debug(f"✅ EVALUATOR: BERTScore calculated: {metrics['bert_score']:.3f}")
            except Exception as bert_error:
                # If download fails, try to use cached model or skip
                error_msg = str(bert_error).lower()
                if 'huggingface.co' in error_msg or 'connection' in error_msg or 'offline' in error_msg:
                    logger.warning(f"⚠️ EVALUATOR: BERTScore unavailable (offline mode or no cached models). Skipping BERTScore metric.")
                    logger.warning(f"⚠️ EVALUATOR: To enable BERTScore, ensure internet access or pre-download models using: bert_score --model roberta-large")
                else:
                    logger.warning(f"⚠️ EVALUATOR: BERTScore calculation failed: {bert_error}")
                metrics['bert_score'] = 0.0
            
        except ImportError:
            logger.warning("⚠️ EVALUATOR: bert_score library not installed. Skipping BERTScore metric.")
            metrics['bert_score'] = 0.0
        except Exception as e:
            logger.warning(f"⚠️ EVALUATOR: BERTScore unavailable: {e}")
            metrics['bert_score'] = 0.0
        
        try:
            # Semantic Similarity (using sentence transformers)
            from sentence_transformers import SentenceTransformer
            import numpy as np
            from numpy.linalg import norm
            
            # Lazy load model (cache it if needed)
            if not hasattr(self, '_semantic_model'):
                self._semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            embeddings = self._semantic_model.encode([workflow_output, expected_output])
            
            # Calculate cosine similarity
            dot_product = np.dot(embeddings[0], embeddings[1])
            norm_a = norm(embeddings[0])
            norm_b = norm(embeddings[1])
            similarity = dot_product / (norm_a * norm_b)
            
            metrics['semantic_similarity'] = float(similarity)
            
        except Exception as e:
            logger.error(f"❌ EVALUATOR: Semantic similarity calculation failed: {e}")
            metrics['semantic_similarity'] = 0.0
        
        # Calculate average score (only include metrics that were successfully calculated)
        # Track which metrics succeeded vs failed (failed metrics are set to 0.0)
        # Note: We can't easily distinguish between "calculated as 0.0" vs "failed and set to 0.0"
        # So we include all metrics in the average, but log which ones might have failed
        metric_values = [
            metrics['rouge_1'],
            metrics['rouge_2'],
            metrics['rouge_l'],
            metrics['bleu'],
            metrics['bert_score'],
            metrics['semantic_similarity']
        ]
        metrics['average_score'] = sum(metric_values) / len(metric_values)
        
        # Log which metrics contributed to the average
        successful_metrics = []
        if metrics['rouge_1'] > 0 or metrics['rouge_2'] > 0 or metrics['rouge_l'] > 0:
            successful_metrics.append('ROUGE')
        if metrics['bleu'] > 0:
            successful_metrics.append('BLEU')
        if metrics['bert_score'] > 0:
            successful_metrics.append('BERTScore')
        if metrics['semantic_similarity'] > 0:
            successful_metrics.append('SemanticSimilarity')
        
        if successful_metrics:
            logger.debug(f"📊 EVALUATOR: Average calculated from {len(successful_metrics)} metric type(s): {', '.join(successful_metrics)}")
        
        logger.info(f"📊 EVALUATOR: Metrics calculated - Avg: {metrics['average_score']:.3f}, "
                   f"ROUGE-1: {metrics['rouge_1']:.3f}, BLEU: {metrics['bleu']:.3f}")
        
        return metrics

