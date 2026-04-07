"""
Pure content filter expression builder (no Django/DB).
Used by EnhancedDocAwareAgentService and by unit tests.
"""
import re


def build_content_filter_expression_impl(content_filter: str) -> str:
    """
    Build Milvus filter expression from a single content filter ID.

    Args:
        content_filter: e.g. "folder_Reports/Financial" or "file_doc123"

    Returns:
        Milvus filter expression string, or "" if invalid/empty.
    """
    if not content_filter:
        return ""
    if content_filter.startswith('folder_'):
        folder_path = content_filter[7:].strip('/').strip()
        folder_path = re.sub(r'/+/', '/', folder_path)
        if not folder_path:
            return ""
        escaped_path = folder_path.replace("'", "''")
        return f"hierarchical_path like '{escaped_path}%'"
    if content_filter.startswith('file_'):
        document_id = content_filter[5:].strip()
        if not document_id:
            return ""
        escaped_doc_id = document_id.replace("'", "''")
        return f"document_id == '{escaped_doc_id}'"
    return ""
