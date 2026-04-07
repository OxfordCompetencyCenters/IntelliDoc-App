"""
Migration Script: Convert content_filter to content_filters
============================================================

This script updates all existing workflows to use the new content_filters array format.

⚠️ BREAKING CHANGE: This migration is required for the multi-select content filter feature.

Usage:
    python manage.py shell
    >>> from migrations.migrate_content_filters import migrate_workflows
    >>> migrate_workflows()

Rollback:
    >>> from migrations.migrate_content_filters import rollback_migration
    >>> rollback_migration()
"""

import json
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def migrate_workflows():
    """
    Migrate all workflows from content_filter (string) to content_filters (array)

    Returns:
        dict: Migration results with counts
    """
    try:
        # Import Django models
        from users.models import WorkflowTemplate as Workflow

        logger.info("🔄 Starting workflow migration: content_filter → content_filters")
        print("╔════════════════════════════════════════════════╗")
        print("║   WORKFLOW MIGRATION: Multi-Select Filters    ║")
        print("╚════════════════════════════════════════════════╝")

        workflows = Workflow.objects.all()
        total_count = workflows.count()
        updated_count = 0
        error_count = 0
        nodes_migrated = 0

        logger.info(f"📊 Found {total_count} workflows to check")
        print(f"\n📊 Checking {total_count} workflows...\n")

        for workflow in workflows:
            try:
                # Parse workflow JSON
                if isinstance(workflow.graph_json, str):
                    graph_data = json.loads(workflow.graph_json)
                else:
                    graph_data = workflow.graph_json

                modified = False
                workflow_nodes_migrated = 0

                # Check all nodes in the workflow
                nodes = graph_data.get('nodes', [])
                for node in nodes:
                    node_data = node.get('data', {})
                    node_name = node_data.get('name', 'Unnamed')
                    node_type = node.get('type', 'Unknown')

                    # Check if node has old content_filter field
                    if 'content_filter' in node_data and 'content_filters' not in node_data:
                        old_filter = node_data['content_filter']

                        # Convert to array
                        if old_filter and old_filter.strip():
                            node_data['content_filters'] = [old_filter]
                            logger.info(f"   ✅ Migrated node '{node_name}' ({node_type}): '{old_filter}' → ['{old_filter}']")
                            print(f"   ✅ {node_name} ({node_type}): '{old_filter}' → ['{old_filter}']")
                        else:
                            node_data['content_filters'] = []
                            logger.info(f"   ✅ Migrated node '{node_name}' ({node_type}): empty → []")
                            print(f"   ✅ {node_name} ({node_type}): empty → []")

                        # Remove old field
                        del node_data['content_filter']
                        modified = True
                        workflow_nodes_migrated += 1

                # Save if modified
                if modified:
                    workflow.graph_json = json.dumps(graph_data)
                    workflow.save()
                    updated_count += 1
                    nodes_migrated += workflow_nodes_migrated
                    logger.info(f"✅ Updated workflow: {workflow.name} (ID: {workflow.id}) - {workflow_nodes_migrated} nodes")
                    print(f"\n✅ Updated workflow: {workflow.name}")
                    print(f"   📝 Migrated {workflow_nodes_migrated} node(s)")

            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error migrating workflow {workflow.id}: {e}")
                print(f"\n❌ Error in workflow {workflow.id}: {e}")

        # Final summary
        result = {
            'total': total_count,
            'updated': updated_count,
            'nodes_migrated': nodes_migrated,
            'errors': error_count
        }

        logger.info(f"""
╔════════════════════════════════════════════════╗
║         MIGRATION COMPLETE                     ║
╠════════════════════════════════════════════════╣
║  Total workflows checked:  {total_count:>4}                  ║
║  Workflows updated:        {updated_count:>4}                  ║
║  Nodes migrated:           {nodes_migrated:>4}                  ║
║  Errors encountered:       {error_count:>4}                  ║
╚════════════════════════════════════════════════╝
""")

        print(f"\n╔════════════════════════════════════════════════╗")
        print(f"║         MIGRATION COMPLETE                     ║")
        print(f"╠════════════════════════════════════════════════╣")
        print(f"║  Total workflows checked:  {total_count:>4}                  ║")
        print(f"║  Workflows updated:        {updated_count:>4}                  ║")
        print(f"║  Nodes migrated:           {nodes_migrated:>4}                  ║")
        print(f"║  Errors encountered:       {error_count:>4}                  ║")
        print(f"╚════════════════════════════════════════════════╝")

        if error_count == 0:
            print("\n✅ Migration successful! All workflows have been updated.")
        else:
            print(f"\n⚠️ Migration completed with {error_count} errors. Check logs for details.")

        return result

    except ImportError as e:
        error_msg = f"Failed to import Workflow model. Make sure you're running this in Django shell: {e}"
        logger.error(error_msg)
        print(f"\n❌ {error_msg}")
        print("\n💡 Run this script using:")
        print("   docker compose exec backend python manage.py shell")
        print("   >>> from migrations.migrate_content_filters import migrate_workflows")
        print("   >>> migrate_workflows()")
        return {'error': str(e)}

    except Exception as e:
        error_msg = f"Unexpected error during migration: {e}"
        logger.error(error_msg)
        print(f"\n❌ {error_msg}")
        import traceback
        print(traceback.format_exc())
        return {'error': str(e)}


def rollback_migration():
    """
    Rollback migration: Convert content_filters back to content_filter

    ⚠️ WARNING: This will lose multi-filter selections (only first filter kept)

    Returns:
        int: Number of workflows rolled back
    """
    try:
        from users.models import WorkflowTemplate as Workflow

        logger.info("⏪ Starting rollback: content_filters → content_filter")
        print("\n╔════════════════════════════════════════════════╗")
        print("║   ROLLBACK: Multi-Select Filters → Single     ║")
        print("╠════════════════════════════════════════════════╣")
        print("║  ⚠️  WARNING: Multi-filter selections will    ║")
        print("║      be lost! Only first filter will be kept. ║")
        print("╚════════════════════════════════════════════════╝")

        workflows = Workflow.objects.all()
        total_count = workflows.count()
        rolled_back_count = 0
        nodes_rolled_back = 0

        for workflow in workflows:
            try:
                if isinstance(workflow.graph_json, str):
                    graph_data = json.loads(workflow.graph_json)
                else:
                    graph_data = workflow.graph_json

                modified = False
                workflow_nodes = 0

                nodes = graph_data.get('nodes', [])
                for node in nodes:
                    node_data = node.get('data', {})
                    node_name = node_data.get('name', 'Unnamed')

                    if 'content_filters' in node_data:
                        filters = node_data['content_filters']

                        # Convert array to single string (take first filter)
                        if filters and len(filters) > 0:
                            node_data['content_filter'] = filters[0]
                            if len(filters) > 1:
                                logger.warning(f"   ⚠️ Multiple filters found in '{node_name}', keeping only first: {filters[0]}")
                                print(f"   ⚠️ {node_name}: Keeping only '{filters[0]}' (lost {len(filters)-1} filters)")
                            else:
                                print(f"   ⏪ {node_name}: Restored '{filters[0]}'")
                        else:
                            node_data['content_filter'] = ''
                            print(f"   ⏪ {node_name}: Restored empty filter")

                        del node_data['content_filters']
                        modified = True
                        workflow_nodes += 1

                if modified:
                    workflow.graph_json = json.dumps(graph_data)
                    workflow.save()
                    rolled_back_count += 1
                    nodes_rolled_back += workflow_nodes
                    print(f"\n⏪ Rolled back workflow: {workflow.name}")

            except Exception as e:
                logger.error(f"❌ Error rolling back workflow {workflow.id}: {e}")
                print(f"\n❌ Error in workflow {workflow.id}: {e}")

        logger.info(f"⏪ Rollback complete: {rolled_back_count} workflows, {nodes_rolled_back} nodes")
        print(f"\n╔════════════════════════════════════════════════╗")
        print(f"║         ROLLBACK COMPLETE                      ║")
        print(f"╠════════════════════════════════════════════════╣")
        print(f"║  Workflows rolled back:    {rolled_back_count:>4}                  ║")
        print(f"║  Nodes rolled back:        {nodes_rolled_back:>4}                  ║")
        print(f"╚════════════════════════════════════════════════╝")

        return rolled_back_count

    except Exception as e:
        error_msg = f"Error during rollback: {e}"
        logger.error(error_msg)
        print(f"\n❌ {error_msg}")
        return 0


def preview_migration(limit=5):
    """
    Preview what the migration would do without making changes

    Args:
        limit: Number of workflows to preview (default: 5)
    """
    try:
        from users.models import WorkflowTemplate as Workflow

        print("\n╔════════════════════════════════════════════════╗")
        print("║         MIGRATION PREVIEW (DRY RUN)            ║")
        print("╚════════════════════════════════════════════════╝\n")

        workflows = Workflow.objects.all()[:limit]

        for workflow in workflows:
            try:
                if isinstance(workflow.graph_json, str):
                    graph_data = json.loads(workflow.graph_json)
                else:
                    graph_data = workflow.graph_json

                print(f"📋 Workflow: {workflow.name} (ID: {workflow.id})")

                nodes = graph_data.get('nodes', [])
                has_old_format = False

                for node in nodes:
                    node_data = node.get('data', {})
                    node_name = node_data.get('name', 'Unnamed')

                    if 'content_filter' in node_data and 'content_filters' not in node_data:
                        old_filter = node_data['content_filter']
                        if old_filter:
                            print(f"   🔄 Node '{node_name}':")
                            print(f"      OLD: content_filter = '{old_filter}'")
                            print(f"      NEW: content_filters = ['{old_filter}']")
                        else:
                            print(f"   🔄 Node '{node_name}':")
                            print(f"      OLD: content_filter = ''")
                            print(f"      NEW: content_filters = []")
                        has_old_format = True

                if not has_old_format:
                    print("   ✅ Already using new format (no migration needed)")

                print()

            except Exception as e:
                print(f"   ❌ Error previewing workflow: {e}\n")

        print(f"📊 Previewed {limit} workflow(s)")
        print("\n💡 To run the actual migration:")
        print("   >>> from migrations.migrate_content_filters import migrate_workflows")
        print("   >>> migrate_workflows()")

    except Exception as e:
        print(f"\n❌ Error during preview: {e}")


# Allow running from command line for testing
if __name__ == "__main__":
    print("⚠️  This script should be run from Django shell context")
    print("\nUsage:")
    print("  docker compose exec backend python manage.py shell")
    print("  >>> from migrations.migrate_content_filters import migrate_workflows")
    print("  >>> migrate_workflows()")
