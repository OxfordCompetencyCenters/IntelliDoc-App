"""
Agent Orchestration Serializers - FIXED VERSION
Template Independent Agent Workflow Serializers with defensive field handling
"""

from rest_framework import serializers
from users.models import AgentWorkflow, SimulationRun, AgentMessage


class AgentWorkflowSerializer(serializers.ModelSerializer):
    """Template-independent agent workflow serializer with safe field access"""
    
    # Basic computed fields that work with any model structure
    node_count = serializers.SerializerMethodField()
    edge_count = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    last_execution_status = serializers.SerializerMethodField()
    
    def get_node_count(self, obj):
        """Get number of nodes in workflow graph"""
        try:
            return len(obj.graph_json.get('nodes', []))
        except (AttributeError, TypeError):
            return 0
    
    def get_edge_count(self, obj):
        """Get number of edges in workflow graph"""
        try:
            return len(obj.graph_json.get('edges', []))
        except (AttributeError, TypeError):
            return 0
    
    def get_execution_count(self, obj):
        """Get total number of executions (simulation runs)"""
        try:
            # Try different possible related names
            if hasattr(obj, 'simulation_runs'):
                return obj.simulation_runs.count()
            elif hasattr(obj, 'runs'):
                return obj.runs.count()
            else:
                # Fallback to reverse foreign key lookup
                return obj.simulationrun_set.count()
        except (AttributeError, TypeError):
            return 0
    
    def get_last_execution_status(self, obj):
        """Get status of last execution"""
        try:
            # Try different possible related names
            if hasattr(obj, 'simulation_runs'):
                last_run = obj.simulation_runs.order_by('-start_time').first()
            elif hasattr(obj, 'runs'):
                last_run = obj.runs.order_by('-start_time').first()
            else:
                # Fallback to reverse foreign key lookup
                last_run = obj.simulationrun_set.order_by('-start_time').first()
            
            return last_run.status if last_run else 'never_executed'
        except (AttributeError, TypeError):
            return 'never_executed'
    
    def to_representation(self, instance):
        """Custom serialization with safe field access"""
        data = {}
        
        # Core fields that should always exist
        safe_fields = {
            'workflow_id': 'workflow_id',
            'name': 'name', 
            'description': 'description',
            'graph_json': 'graph_json',
            'version': 'version',
            'status': 'status',
            'created_at': 'created_at',
            'updated_at': 'updated_at'
        }
        
        # Optional fields that may or may not exist
        optional_fields = {
            'max_agents_limit': 'max_agents_limit',
            'supports_function_tools': 'supports_function_tools',
            'supports_real_time_streaming': 'supports_real_time_streaming',
            'sandbox_execution_enabled': 'sandbox_execution_enabled',
            'tags': 'tags',
            'last_executed_at': 'last_executed_at',
            'custom_config': 'custom_config',
            'supports_rag': 'supports_rag',
            'vector_collections': 'vector_collections',
            'generated_code': 'generated_code',
            'code_generation_timestamp': 'code_generation_timestamp'
        }
        
        # Add safe fields
        for key, attr_name in safe_fields.items():
            try:
                data[key] = getattr(instance, attr_name)
            except AttributeError:
                data[key] = None
        
        # Add optional fields if they exist
        for key, attr_name in optional_fields.items():
            if hasattr(instance, attr_name):
                try:
                    data[key] = getattr(instance, attr_name)
                except (AttributeError, TypeError):
                    pass  # Skip if there's any issue
        
        # Add computed fields
        data['node_count'] = self.get_node_count(instance)
        data['edge_count'] = self.get_edge_count(instance)
        data['execution_count'] = self.get_execution_count(instance)
        data['last_execution_status'] = self.get_last_execution_status(instance)
        
        return data
    
    class Meta:
        model = AgentWorkflow
        fields = '__all__'  # We'll handle field filtering in to_representation
        read_only_fields = ['workflow_id', 'created_at', 'updated_at']


class SimulationRunSerializer(serializers.ModelSerializer):
    """Template-independent simulation run serializer"""
    
    formatted_duration = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    workflow_name = serializers.SerializerMethodField()
    
    def get_formatted_duration(self, obj):
        """Get human-readable duration"""
        try:
            if hasattr(obj, 'duration_seconds') and obj.duration_seconds:
                if obj.duration_seconds < 60:
                    return f"{obj.duration_seconds:.1f}s"
                elif obj.duration_seconds < 3600:
                    minutes = obj.duration_seconds / 60
                    return f"{minutes:.1f}m"
                else:
                    hours = obj.duration_seconds / 3600
                    return f"{hours:.1f}h"
        except (AttributeError, TypeError):
            pass
        return 'N/A'
    
    def get_is_active(self, obj):
        """Check if run is currently active"""
        try:
            return obj.status in ['pending', 'running']
        except AttributeError:
            return False
    
    def get_workflow_name(self, obj):
        """Get workflow name safely"""
        try:
            return obj.workflow.name if obj.workflow else 'Unknown'
        except AttributeError:
            return 'Unknown'
    
    class Meta:
        model = SimulationRun
        fields = '__all__'
        read_only_fields = ['run_id', 'start_time', 'end_time', 'duration_seconds']


class AgentMessageSerializer(serializers.ModelSerializer):
    """Template-independent agent message serializer"""
    
    formatted_timestamp = serializers.SerializerMethodField()
    is_function_call = serializers.SerializerMethodField()
    is_user_message = serializers.SerializerMethodField()
    
    def get_formatted_timestamp(self, obj):
        """Get human-readable timestamp"""
        try:
            return obj.timestamp.strftime('%H:%M:%S')
        except (AttributeError, ValueError):
            return 'N/A'
    
    def get_is_function_call(self, obj):
        """Check if message is a function call"""
        try:
            return obj.message_type == 'function_call'
        except AttributeError:
            return False
    
    def get_is_user_message(self, obj):
        """Check if message is from user"""
        try:
            return (obj.message_type == 'user_input' or 
                   obj.agent_type == 'UserProxyAgent')
        except AttributeError:
            return False
    
    class Meta:
        model = AgentMessage
        fields = '__all__'
        read_only_fields = ['message_id', 'timestamp']


class WorkflowValidationSerializer(serializers.Serializer):
    """Serializer for workflow validation requests"""
    
    graph_json = serializers.JSONField()
    project_capabilities = serializers.JSONField(required=False)
    
    def validate_graph_json(self, value):
        """Validate graph JSON structure"""
        required_keys = ['nodes', 'edges']
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"Graph JSON must contain '{key}' field")
        
        # Validate nodes structure
        nodes = value.get('nodes', [])
        if not isinstance(nodes, list):
            raise serializers.ValidationError("'nodes' must be a list")
        
        # Validate edges structure
        edges = value.get('edges', [])
        if not isinstance(edges, list):
            raise serializers.ValidationError("'edges' must be a list")
        
        return value


class AgentWorkflowCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new agent workflows"""
    
    class Meta:
        model = AgentWorkflow
        fields = [
            'name',
            'description', 
            'graph_json',
            'version',
            'status',
            'tags',
            'custom_config',
            'supports_rag',
            'vector_collections',
            'max_agents_limit',
            'supports_function_tools',
            'supports_real_time_streaming',
            'sandbox_execution_enabled',
            'total_executions',
            'successful_executions',
            'average_execution_time'
        ]
    
    def to_internal_value(self, data):
        """Set default values for required fields"""
        # Set defaults for execution tracking fields
        data = data.copy() if isinstance(data, dict) else {}
        data.setdefault('total_executions', 0)
        data.setdefault('successful_executions', 0)
        data.setdefault('average_execution_time', None)
        return super().to_internal_value(data)
    
    def validate_graph_json(self, value):
        """Validate graph JSON structure for creation"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("graph_json must be a dictionary")
        
        if 'nodes' not in value or 'edges' not in value:
            raise serializers.ValidationError("graph_json must contain 'nodes' and 'edges' keys")
        
        if not isinstance(value['nodes'], list) or not isinstance(value['edges'], list):
            raise serializers.ValidationError("'nodes' and 'edges' must be lists")
        
        # Validate node structure
        for i, node in enumerate(value['nodes']):
            if not isinstance(node, dict):
                raise serializers.ValidationError(f"Node {i} must be a dictionary")
            
            required_fields = ['id', 'type', 'position', 'data']
            for field in required_fields:
                if field not in node:
                    raise serializers.ValidationError(f"Node {i} missing required field: {field}")
        
        return value


class WorkflowExecutionSerializer(serializers.Serializer):
    """Serializer for workflow execution requests"""
    
    workflow_id = serializers.UUIDField()
    execution_parameters = serializers.JSONField(required=False, default=dict)
    environment = serializers.CharField(max_length=50, default='production')
    
    def validate_workflow_id(self, value):
        """Validate workflow exists and is accessible"""
        try:
            workflow = AgentWorkflow.objects.get(workflow_id=value)
            return value
        except AgentWorkflow.DoesNotExist:
            raise serializers.ValidationError("Workflow not found")
