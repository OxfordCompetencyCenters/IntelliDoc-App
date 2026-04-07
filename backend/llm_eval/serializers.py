from rest_framework import serializers
from users.models import LLMProvider, APIKeyConfig, LLMComparison, LLMResponse
from .encryption import encrypt_api_key

class LLMProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMProvider
        fields = ['id', 'name', 'provider_type', 'is_active', 'api_endpoint', 'max_tokens', 'timeout_seconds']

class APIKeyConfigSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, help_text="API key will be encrypted when stored")
    
    class Meta:
        model = APIKeyConfig
        fields = [
            'id', 'provider', 'key_name', 'api_key', 'usage_limit_daily', 
            'usage_count_today', 'is_active', 'created_at'
        ]
        read_only_fields = ['usage_count_today', 'created_at']
    
    def create(self, validated_data):
        # Encrypt the API key before saving
        api_key = validated_data.pop('api_key')
        validated_data['api_key'] = encrypt_api_key(api_key)
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class LLMResponseSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    
    class Meta:
        model = LLMResponse
        fields = [
            'id', 'provider_name', 'model_name', 'response_text', 
            'response_time_ms', 'token_count', 'cost_estimate', 
            'error_message', 'created_at'
        ]

class LLMComparisonSerializer(serializers.ModelSerializer):
    responses = LLMResponseSerializer(many=True, read_only=True)
    
    class Meta:
        model = LLMComparison
        fields = ['id', 'prompt', 'title', 'created_at', 'responses']
        read_only_fields = ['created_at']

class LLMComparisonCreateSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=10000)  # Increased for judge analysis
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    provider_configs = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=10,
        help_text="List of provider configurations with provider_id and model_name"
    )
    temperature = serializers.FloatField(min_value=0.0, max_value=2.0, default=0.7)
    
    def validate_provider_configs(self, value):
        """Validate that each provider config has required fields"""
        if not value:
            raise serializers.ValidationError("provider_configs cannot be empty")
            
        for i, config in enumerate(value):
            if not isinstance(config, dict):
                raise serializers.ValidationError(f"provider_configs[{i}] must be a dictionary")
                
            if 'provider_id' not in config:
                raise serializers.ValidationError(f"provider_configs[{i}] must have 'provider_id'")
                
            if 'model_name' not in config:
                raise serializers.ValidationError(f"provider_configs[{i}] must have 'model_name'")
                
            if not isinstance(config['provider_id'], int):
                raise serializers.ValidationError(f"provider_configs[{i}]['provider_id'] must be an integer")
                
            if not isinstance(config['model_name'], str) or not config['model_name'].strip():
                raise serializers.ValidationError(f"provider_configs[{i}]['model_name'] must be a non-empty string")
                
        return value
