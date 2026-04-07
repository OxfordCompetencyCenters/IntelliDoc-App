"""
Template Versioning System
Phase 5: Advanced Template Management

Provides comprehensive version management for templates including:
- Semantic versioning (major.minor.patch)
- Version migration tools
- Backward compatibility tracking
- Version comparison and analysis
- Automated version upgrade paths
"""

import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from packaging import version

logger = logging.getLogger(__name__)


@dataclass
class TemplateVersion:
    """Template version information with semantic versioning"""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        """Standard semantic version string"""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build:
            version_str += f"+{self.build}"
        return version_str
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, TemplateVersion):
            return False
        return str(self) == str(other)
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, TemplateVersion):
            return NotImplemented
        return version.Version(str(self)) < version.Version(str(other))
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        return not self <= other
    
    def __ge__(self, other) -> bool:
        return not self < other


@dataclass
class VersionMigration:
    """Version migration configuration"""
    from_version: str
    to_version: str
    migration_script: str
    description: str
    breaking_changes: List[str]
    automated: bool = True
    rollback_supported: bool = True


@dataclass
class VersionCompatibility:
    """Version compatibility information"""
    template_id: str
    version: str
    compatible_versions: List[str]
    breaking_versions: List[str]
    deprecated_features: List[str]
    new_features: List[str]


class TemplateVersioningService:
    """Advanced template versioning service"""
    
    def __init__(self):
        self.template_base_path = Path("templates/template_definitions")
        logger.info("Initialized TemplateVersioningService")
    
    def parse_version(self, version_string: str) -> TemplateVersion:
        """Parse semantic version string into TemplateVersion object"""
        logger.info(f"Parsing version string: {version_string}")
        
        # Semantic version regex pattern
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        match = re.match(pattern, version_string)
        
        if not match:
            logger.error(f"Invalid semantic version format: {version_string}")
            raise ValueError(f"Invalid semantic version format: {version_string}")
        
        major, minor, patch, prerelease, build = match.groups()
        
        template_version = TemplateVersion(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build
        )
        
        logger.info(f"Parsed version: {template_version}")
        return template_version
    
    def get_template_version(self, template_id: str) -> TemplateVersion:
        """Get current version of a template"""
        logger.info(f"Getting version for template: {template_id}")
        
        try:
            metadata_path = self.template_base_path / template_id / "metadata.json"
            
            if not metadata_path.exists():
                logger.error(f"Metadata file not found for template: {template_id}")
                raise FileNotFoundError(f"Template metadata not found: {template_id}")
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            version_string = metadata.get('version', '1.0.0')
            template_version = self.parse_version(version_string)
            
            logger.info(f"Template {template_id} version: {template_version}")
            return template_version
            
        except Exception as e:
            logger.error(f"Error getting template version for {template_id}: {str(e)}")
            raise
    
    def compare_versions(self, version1: str, version2: str) -> str:
        """Compare two versions and return relationship"""
        logger.info(f"Comparing versions: {version1} vs {version2}")
        
        try:
            v1 = self.parse_version(version1)
            v2 = self.parse_version(version2)
            
            if v1 == v2:
                result = "equal"
            elif v1 < v2:
                result = "older"
            else:
                result = "newer"
            
            logger.info(f"Version comparison result: {version1} is {result} than {version2}")
            return result
            
        except Exception as e:
            logger.error(f"Error comparing versions {version1} and {version2}: {str(e)}")
            raise
    
    def increment_version(self, current_version: str, increment_type: str) -> str:
        """Increment version based on type (major, minor, patch)"""
        logger.info(f"Incrementing version {current_version} by {increment_type}")
        
        try:
            version_obj = self.parse_version(current_version)
            
            if increment_type == "major":
                version_obj.major += 1
                version_obj.minor = 0
                version_obj.patch = 0
            elif increment_type == "minor":
                version_obj.minor += 1
                version_obj.patch = 0
            elif increment_type == "patch":
                version_obj.patch += 1
            else:
                raise ValueError(f"Invalid increment type: {increment_type}")
            
            # Clear prerelease and build for standard increments
            version_obj.prerelease = None
            version_obj.build = None
            
            new_version = str(version_obj)
            logger.info(f"Version incremented from {current_version} to {new_version}")
            return new_version
            
        except Exception as e:
            logger.error(f"Error incrementing version {current_version}: {str(e)}")
            raise
    
    def get_version_history(self, template_id: str) -> List[Dict]:
        """Get version history for a template"""
        logger.info(f"Getting version history for template: {template_id}")
        
        try:
            history_path = self.template_base_path / template_id / "version_history.json"
            
            if not history_path.exists():
                logger.info(f"No version history found for template: {template_id}")
                return []
            
            with open(history_path, 'r') as f:
                history = json.load(f)
            
            logger.info(f"Retrieved {len(history)} version entries for template: {template_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error getting version history for {template_id}: {str(e)}")
            raise
    
    def create_version_migration(self, template_id: str, from_version: str, to_version: str, 
                                migration_config: Dict) -> VersionMigration:
        """Create version migration configuration"""
        logger.info(f"Creating version migration for {template_id}: {from_version} -> {to_version}")
        
        try:
            migration = VersionMigration(
                from_version=from_version,
                to_version=to_version,
                migration_script=migration_config.get('migration_script', ''),
                description=migration_config.get('description', ''),
                breaking_changes=migration_config.get('breaking_changes', []),
                automated=migration_config.get('automated', True),
                rollback_supported=migration_config.get('rollback_supported', True)
            )
            
            # Save migration configuration
            migration_path = self.template_base_path / template_id / "migrations"
            migration_path.mkdir(exist_ok=True)
            
            migration_file = migration_path / f"{from_version}_to_{to_version}.json"
            
            with open(migration_file, 'w') as f:
                json.dump({
                    'from_version': migration.from_version,
                    'to_version': migration.to_version,
                    'migration_script': migration.migration_script,
                    'description': migration.description,
                    'breaking_changes': migration.breaking_changes,
                    'automated': migration.automated,
                    'rollback_supported': migration.rollback_supported,
                    'created_at': datetime.now().isoformat()
                }, f, indent=2)
            
            logger.info(f"Version migration created successfully: {migration_file}")
            return migration
            
        except Exception as e:
            logger.error(f"Error creating version migration: {str(e)}")
            raise
    
    def check_version_compatibility(self, template_id: str, target_version: str) -> VersionCompatibility:
        """Check version compatibility for a template"""
        logger.info(f"Checking version compatibility for {template_id} -> {target_version}")
        
        try:
            current_version = str(self.get_template_version(template_id))
            
            # Load compatibility configuration
            compat_path = self.template_base_path / template_id / "compatibility.json"
            
            if compat_path.exists():
                with open(compat_path, 'r') as f:
                    compat_config = json.load(f)
            else:
                compat_config = {}
            
            compatibility = VersionCompatibility(
                template_id=template_id,
                version=target_version,
                compatible_versions=compat_config.get('compatible_versions', []),
                breaking_versions=compat_config.get('breaking_versions', []),
                deprecated_features=compat_config.get('deprecated_features', []),
                new_features=compat_config.get('new_features', [])
            )
            
            logger.info(f"Version compatibility check completed for {template_id}")
            return compatibility
            
        except Exception as e:
            logger.error(f"Error checking version compatibility: {str(e)}")
            raise
    
    def get_available_migrations(self, template_id: str, current_version: str) -> List[VersionMigration]:
        """Get available migrations from current version"""
        logger.info(f"Getting available migrations for {template_id} from version {current_version}")
        
        try:
            migrations_path = self.template_base_path / template_id / "migrations"
            available_migrations = []
            
            if not migrations_path.exists():
                logger.info(f"No migrations directory found for template: {template_id}")
                return available_migrations
            
            for migration_file in migrations_path.glob("*.json"):
                try:
                    with open(migration_file, 'r') as f:
                        migration_data = json.load(f)
                    
                    if migration_data['from_version'] == current_version:
                        migration = VersionMigration(
                            from_version=migration_data['from_version'],
                            to_version=migration_data['to_version'],
                            migration_script=migration_data['migration_script'],
                            description=migration_data['description'],
                            breaking_changes=migration_data['breaking_changes'],
                            automated=migration_data.get('automated', True),
                            rollback_supported=migration_data.get('rollback_supported', True)
                        )
                        available_migrations.append(migration)
                        
                except Exception as e:
                    logger.warning(f"Error reading migration file {migration_file}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(available_migrations)} available migrations")
            return available_migrations
            
        except Exception as e:
            logger.error(f"Error getting available migrations: {str(e)}")
            raise
    
    def update_template_version(self, template_id: str, new_version: str, 
                               changelog: Optional[str] = None) -> bool:
        """Update template version in metadata"""
        logger.info(f"Updating template {template_id} version to {new_version}")
        
        try:
            # Validate new version format
            self.parse_version(new_version)
            
            # Update metadata
            metadata_path = self.template_base_path / template_id / "metadata.json"
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            old_version = metadata.get('version', '1.0.0')
            metadata['version'] = new_version
            metadata['last_updated'] = datetime.now().isoformat()
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Update version history
            self._add_version_history_entry(template_id, old_version, new_version, changelog)
            
            logger.info(f"Template version updated successfully: {old_version} -> {new_version}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating template version: {str(e)}")
            raise
    
    def _add_version_history_entry(self, template_id: str, old_version: str, 
                                  new_version: str, changelog: Optional[str]) -> None:
        """Add entry to version history"""
        logger.info(f"Adding version history entry for {template_id}: {old_version} -> {new_version}")
        
        try:
            history_path = self.template_base_path / template_id / "version_history.json"
            
            # Load existing history
            if history_path.exists():
                with open(history_path, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            
            # Add new entry
            entry = {
                'from_version': old_version,
                'to_version': new_version,
                'timestamp': datetime.now().isoformat(),
                'changelog': changelog or f"Updated from {old_version} to {new_version}"
            }
            
            history.append(entry)
            
            # Save updated history
            with open(history_path, 'w') as f:
                json.dump(history, f, indent=2)
            
            logger.info(f"Version history entry added successfully")
            
        except Exception as e:
            logger.error(f"Error adding version history entry: {str(e)}")
            raise
