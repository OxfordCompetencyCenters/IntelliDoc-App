"""
Template Configuration Schema Validator

Provides JSON schema validation for template configurations to ensure
they match expected structure before cloning.
"""

import logging
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger(__name__)

# Try to import jsonschema, but don't fail if it's not installed
try:
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logger.warning("jsonschema not available - schema validation will be disabled")


# JSON Schema for template configuration
TEMPLATE_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["name", "template_type"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1
        },
        "template_type": {
            "type": "string",
            "minLength": 1
        },
        "description": {
            "type": "string"
        },
        "instructions": {
            "type": "string"
        },
        "suggested_questions": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "required_fields": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "analysis_focus": {
            "type": "string"
        },
        "icon_class": {
            "type": "string"
        },
        "color_theme": {
            "type": "string"
        },
        "has_navigation": {
            "type": "boolean"
        },
        "total_pages": {
            "type": "integer",
            "minimum": 1
        },
        "navigation_pages": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["page_number", "name"],
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "minimum": 1
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1
                    },
                    "short_name": {
                        "type": "string"
                    },
                    "icon": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "features": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "processing_capabilities": {
            "type": "object",
            "additionalProperties": True
        },
        "validation_rules": {
            "type": "object",
            "additionalProperties": True
        },
        "ui_configuration": {
            "type": "object",
            "additionalProperties": True
        }
    },
    "additionalProperties": True  # Allow additional fields for flexibility
}


def validate_template_config_schema(
    template_config: Dict[str, Any],
    template_id: Optional[str] = None,
    strict: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate template configuration against JSON schema.
    
    Args:
        template_config: Template configuration dictionary to validate
        template_id: Template identifier for logging (optional)
        strict: If True, fail on schema violations. If False, log warnings only.
        
    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if configuration is valid
        - error_messages: List of validation error messages
    """
    if not JSONSCHEMA_AVAILABLE:
        logger.warning("Schema validation skipped - jsonschema not installed")
        return True, []
    
    errors = []
    template_id_str = template_id or 'unknown'
    
    try:
        validate(instance=template_config, schema=TEMPLATE_CONFIG_SCHEMA)
        logger.debug(f"Template {template_id_str} configuration schema validation passed")
        return True, []
    except ValidationError as e:
        error_msg = f"Schema validation failed for template {template_id_str}: {e.message}"
        if e.path:
            error_msg += f" (path: {'/'.join(str(p) for p in e.path)})"
        
        errors.append(error_msg)
        logger.warning(error_msg)
        
        if strict:
            logger.error(f"Strict validation mode - template {template_id_str} rejected due to schema violation")
        else:
            logger.warning(f"Template {template_id_str} has schema violations but will proceed (non-strict mode)")
        
        return False, errors
    except Exception as e:
        error_msg = f"Unexpected error during schema validation for template {template_id_str}: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
        return False, errors


def validate_navigation_pages_structure(navigation_pages: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate navigation pages structure.
    
    Args:
        navigation_pages: List of navigation page dictionaries
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    if not isinstance(navigation_pages, list):
        errors.append("navigation_pages must be a list")
        return False, errors
    
    for idx, page in enumerate(navigation_pages):
        if not isinstance(page, dict):
            errors.append(f"navigation_pages[{idx}] must be a dictionary")
            continue
        
        if 'page_number' not in page:
            errors.append(f"navigation_pages[{idx}] missing required field 'page_number'")
        elif not isinstance(page['page_number'], int):
            errors.append(f"navigation_pages[{idx}].page_number must be an integer")
        
        if 'name' not in page:
            errors.append(f"navigation_pages[{idx}] missing required field 'name'")
        elif not isinstance(page['name'], str) or len(page['name']) == 0:
            errors.append(f"navigation_pages[{idx}].name must be a non-empty string")
    
    if errors:
        return False, errors
    
    return True, []


def get_schema_validation_summary(template_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of schema validation without failing.
    
    Args:
        template_config: Template configuration dictionary
        
    Returns:
        Dictionary with validation summary
    """
    summary = {
        'has_required_fields': True,
        'missing_fields': [],
        'navigation_pages_valid': True,
        'navigation_pages_errors': [],
        'schema_valid': True,
        'schema_errors': []
    }
    
    # Check required fields
    required_fields = ['name', 'template_type']
    missing = [f for f in required_fields if f not in template_config]
    if missing:
        summary['has_required_fields'] = False
        summary['missing_fields'] = missing
    
    # Validate navigation pages if present
    if 'navigation_pages' in template_config:
        nav_valid, nav_errors = validate_navigation_pages_structure(template_config['navigation_pages'])
        summary['navigation_pages_valid'] = nav_valid
        summary['navigation_pages_errors'] = nav_errors
    
    # Run schema validation (non-strict)
    if JSONSCHEMA_AVAILABLE:
        schema_valid, schema_errors = validate_template_config_schema(template_config, strict=False)
        summary['schema_valid'] = schema_valid
        summary['schema_errors'] = schema_errors
    
    return summary

