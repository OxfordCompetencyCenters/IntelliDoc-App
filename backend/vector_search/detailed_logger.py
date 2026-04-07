# backend/vector_search/detailed_logger.py
# Comprehensive Document Processing Logger - Integrated with existing log system

import logging
import time
import json
import traceback
from functools import wraps
from typing import Any, Dict, Optional
from datetime import datetime
import uuid
import os
from pathlib import Path
import glob

# Create a specialized logger for document processing that integrates with Django's logging
doc_logger = logging.getLogger('vector_search.detailed_processing')
doc_logger.setLevel(logging.DEBUG)

# Don't create separate log files - use Django's existing logging system
# The detailed logs will appear in the backend log files created by start_improved.sh

# Add a handler only if none exists (to avoid duplicate logs)
if not doc_logger.handlers:
    # Create a console handler that will be captured by the existing log redirection
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Create detailed formatter that will stand out in the existing logs
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | DETAILED_PROCESSING | %(funcName)s:%(lineno)d | %(message)s'
    )
    console_handler.setFormatter(detailed_formatter)
    doc_logger.addHandler(console_handler)

class DocumentProcessingTracker:
    """Tracks document processing through all stages"""
    
    def __init__(self, document_id: str, document_name: str):
        self.document_id = document_id
        self.document_name = document_name
        self.session_id = str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.stages = {}
        self.current_stage = None
        
        doc_logger.info(f"🚀 PROCESSING SESSION STARTED | Session: {self.session_id} | Document: {document_name} | ID: {document_id}")
    
    def start_stage(self, stage_name: str, stage_data: Dict = None):
        """Start a new processing stage"""
        if self.current_stage:
            self.end_stage("interrupted")
            
        self.current_stage = stage_name
        stage_info = {
            'start_time': time.time(),
            'data': stage_data or {},
            'status': 'in_progress',
            'errors': [],
            'warnings': []
        }
        self.stages[stage_name] = stage_info
        
        doc_logger.info(f"📋 STAGE START | Session: {self.session_id} | Stage: {stage_name} | Document: {self.document_name}")
        if stage_data:
            doc_logger.debug(f"📊 STAGE DATA | Session: {self.session_id} | Stage: {stage_name} | Data: {json.dumps(stage_data, default=str)}")
    
    def log_stage_info(self, message: str, data: Dict = None):
        """Log information within current stage"""
        if self.current_stage:
            doc_logger.info(f"ℹ️  STAGE INFO | Session: {self.session_id} | Stage: {self.current_stage} | {message}")
            if data:
                doc_logger.debug(f"📊 STAGE INFO DATA | Session: {self.session_id} | Stage: {self.current_stage} | Data: {json.dumps(data, default=str)}")
    
    def log_stage_warning(self, message: str, data: Dict = None):
        """Log warning within current stage"""
        if self.current_stage:
            self.stages[self.current_stage]['warnings'].append(message)
            doc_logger.warning(f"⚠️  STAGE WARNING | Session: {self.session_id} | Stage: {self.current_stage} | {message}")
            if data:
                doc_logger.debug(f"📊 WARNING DATA | Session: {self.session_id} | Stage: {self.current_stage} | Data: {json.dumps(data, default=str)}")
    
    def log_stage_error(self, message: str, error: Exception = None, data: Dict = None):
        """Log error within current stage"""
        if self.current_stage:
            error_info = {
                'message': message,
                'error_type': type(error).__name__ if error else 'Unknown',
                'error_details': str(error) if error else 'No details',
                'traceback': traceback.format_exc() if error else None
            }
            self.stages[self.current_stage]['errors'].append(error_info)
            
            doc_logger.error(f"❌ STAGE ERROR | Session: {self.session_id} | Stage: {self.current_stage} | {message}")
            if error:
                doc_logger.error(f"🔥 ERROR DETAILS | Session: {self.session_id} | Error: {type(error).__name__}: {str(error)}")
                doc_logger.debug(f"📋 ERROR TRACEBACK | Session: {self.session_id} | Traceback:\n{traceback.format_exc()}")
            if data:
                doc_logger.debug(f"📊 ERROR DATA | Session: {self.session_id} | Stage: {self.current_stage} | Data: {json.dumps(data, default=str)}")
    
    def end_stage(self, status: str = "completed", result_data: Dict = None):
        """End current stage"""
        if self.current_stage and self.current_stage in self.stages:
            stage_info = self.stages[self.current_stage]
            stage_info['end_time'] = time.time()
            stage_info['duration'] = stage_info['end_time'] - stage_info['start_time']
            stage_info['status'] = status
            stage_info['result'] = result_data or {}
            
            doc_logger.info(f"✅ STAGE END | Session: {self.session_id} | Stage: {self.current_stage} | Status: {status} | Duration: {stage_info['duration']:.2f}s")
            if result_data:
                doc_logger.debug(f"📊 STAGE RESULT | Session: {self.session_id} | Stage: {self.current_stage} | Result: {json.dumps(result_data, default=str)}")
            
            # Log stage summary
            warnings_count = len(stage_info['warnings'])
            errors_count = len(stage_info['errors'])
            doc_logger.info(f"📈 STAGE SUMMARY | Session: {self.session_id} | Stage: {self.current_stage} | Warnings: {warnings_count} | Errors: {errors_count}")
            
            self.current_stage = None
    
    def finish_processing(self, final_status: str = "completed", summary_data: Dict = None):
        """Finish entire processing session"""
        if self.current_stage:
            self.end_stage("interrupted")
            
        total_duration = time.time() - self.start_time
        total_warnings = sum(len(stage['warnings']) for stage in self.stages.values())
        total_errors = sum(len(stage['errors']) for stage in self.stages.values())
        
        doc_logger.info(f"🏁 PROCESSING FINISHED | Session: {self.session_id} | Document: {self.document_name} | Status: {final_status} | Duration: {total_duration:.2f}s")
        doc_logger.info(f"📈 FINAL SUMMARY | Session: {self.session_id} | Stages: {len(self.stages)} | Total Warnings: {total_warnings} | Total Errors: {total_errors}")
        
        if summary_data:
            doc_logger.debug(f"📊 FINAL SUMMARY DATA | Session: {self.session_id} | Data: {json.dumps(summary_data, default=str)}")
        
        # Log detailed stage breakdown
        for stage_name, stage_info in self.stages.items():
            doc_logger.debug(f"📋 STAGE BREAKDOWN | Session: {self.session_id} | Stage: {stage_name} | Status: {stage_info['status']} | Duration: {stage_info.get('duration', 0):.2f}s | Warnings: {len(stage_info['warnings'])} | Errors: {len(stage_info['errors'])}")

def track_document_processing(func):
    """Decorator to automatically track document processing"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try to extract document info from args/kwargs
        document = None
        document_id = "unknown"
        document_name = "unknown"
        
        # Look for document in args
        for arg in args:
            if hasattr(arg, 'original_filename') and hasattr(arg, 'document_id'):
                document = arg
                document_id = str(arg.document_id)
                document_name = arg.original_filename
                break
        
        # Look for document in kwargs
        if not document:
            for key, value in kwargs.items():
                if hasattr(value, 'original_filename') and hasattr(value, 'document_id'):
                    document = value
                    document_id = str(value.document_id)
                    document_name = value.original_filename
                    break
        
        tracker = DocumentProcessingTracker(document_id, document_name)
        tracker.start_stage(func.__name__)
        
        try:
            result = func(*args, **kwargs)
            tracker.end_stage("completed", {"result_type": type(result).__name__})
            tracker.finish_processing("completed")
            return result
        except Exception as e:
            tracker.log_stage_error(f"Function {func.__name__} failed", e)
            tracker.end_stage("failed")
            tracker.finish_processing("failed")
            raise
    
    return wrapper

def log_data_state(tracker: DocumentProcessingTracker, stage: str, data_name: str, data: Any):
    """Log detailed state of data at any point"""
    data_info = {
        'data_name': data_name,
        'data_type': type(data).__name__,
        'data_size': len(str(data)) if data else 0
    }
    
    if isinstance(data, dict):
        data_info['dict_keys'] = list(data.keys())
        data_info['dict_size'] = len(data)
        
        # Log specific problematic fields
        problematic_fields = ['chunk_index', 'hierarchy_level', 'total_chunks', 'topic_word_count', 'summary_word_count', 'processing_time_ms']
        for field in problematic_fields:
            if field in data:
                field_value = data[field]
                data_info[f'{field}_value'] = field_value
                data_info[f'{field}_type'] = type(field_value).__name__
                
                # Check if it's a string that should be an integer
                if isinstance(field_value, str) and field_value.isdigit():
                    data_info[f'{field}_WARNING'] = "STRING_SHOULD_BE_INT"
    
    elif isinstance(data, (list, tuple)):
        data_info['sequence_length'] = len(data)
        if data:
            data_info['first_item_type'] = type(data[0]).__name__
    
    elif isinstance(data, str):
        data_info['string_length'] = len(data)
        data_info['string_preview'] = data[:100] + "..." if len(data) > 100 else data
    
    tracker.log_stage_info(f"Data State: {data_name}", data_info)

def log_vector_insertion_attempt(tracker: DocumentProcessingTracker, doc_info: Any):
    """Log detailed information about vector insertion attempt"""
    tracker.start_stage("vector_insertion_prep")
    
    # Log document info structure
    doc_info_data = {
        'has_content': hasattr(doc_info, 'content'),
        'content_length': len(doc_info.content) if hasattr(doc_info, 'content') and doc_info.content else 0,
        'has_embedding': hasattr(doc_info, 'embedding'),
        'embedding_shape': doc_info.embedding.shape if hasattr(doc_info, 'embedding') and doc_info.embedding is not None else None,
        'has_metadata': hasattr(doc_info, 'metadata'),
        'metadata_keys': list(doc_info.metadata.keys()) if hasattr(doc_info, 'metadata') and doc_info.metadata else []
    }
    
    tracker.log_stage_info("Document Info Structure", doc_info_data)
    
    # Log metadata in detail
    if hasattr(doc_info, 'metadata') and doc_info.metadata:
        log_data_state(tracker, "vector_insertion_prep", "metadata", doc_info.metadata)
        
        # Check each field type
        type_issues = {}
        expected_int_fields = ['chunk_index', 'hierarchy_level', 'total_chunks', 'topic_word_count', 'summary_word_count', 'processing_time_ms']
        
        for field in expected_int_fields:
            if field in doc_info.metadata:
                value = doc_info.metadata[field]
                if not isinstance(value, int):
                    type_issues[field] = {
                        'current_type': type(value).__name__,
                        'current_value': str(value),
                        'expected_type': 'int'
                    }
        
        if type_issues:
            tracker.log_stage_warning("Type mismatches detected", type_issues)
    
    tracker.end_stage("completed")

# Global instance for easy access
current_tracker = None

def get_current_tracker():
    """Get the current processing tracker"""
    return current_tracker

def set_current_tracker(tracker: DocumentProcessingTracker):
    """Set the current processing tracker"""
    global current_tracker
    current_tracker = tracker
