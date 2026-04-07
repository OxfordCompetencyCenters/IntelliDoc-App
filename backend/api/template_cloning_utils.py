# Template cloning utilities — DEPRECATED for Electron desktop version.
# Projects now reference the template at runtime instead of deep-copying config.
# These stubs exist to prevent import errors from any remaining references.


def validate_template_config(template_config, template_id):
    """Stub — validation no longer needed."""
    return []


def clone_template_configuration(template_config, template_metadata, include_audit_trail=False):
    """Stub — deep copy no longer used."""
    return template_config, {} if include_audit_trail else None


def deep_clone_configuration_field(value):
    """Stub — deep copy no longer used."""
    return value
