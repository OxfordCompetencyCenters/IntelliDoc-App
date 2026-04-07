try:
    from .hierarchical_config import HierarchicalProcessingConfig
except ImportError:
    # Fallback configuration if hierarchical_config is not available
    class HierarchicalProcessingConfig:
        @staticmethod
        def get_hierarchical_configuration():
            return {
                'hierarchical_processing': {},
                'document_organization': {},
                'search_capabilities': {},
                'content_reconstruction': {},
                'ai_processing': {},
                'performance_settings': {},
                'quality_control': {},
                'document_categories': [],
                'document_types': [],
                'chunk_types': [],
                'processing_endpoints': []
            }

class AICCIntelliDocTemplateDefinition:
    """Enhanced template definition for AICC-IntelliDoc with hierarchical processing capabilities"""
    
    def get_complete_configuration(self):
        """Return complete template configuration with hierarchical processing for project cloning"""
        hierarchical_config = HierarchicalProcessingConfig.get_hierarchical_configuration()
        
        return {
            'name': 'AICC-IntelliDoc v2',
            'template_type': 'aicc-intellidoc-v2',
            'description': 'Advanced AI-powered document analysis platform with hierarchical processing and agent orchestration',
            'instructions': '''Upload documents for advanced AI-powered analysis with hierarchical processing and agent orchestration capabilities.
            
Features:
• Complete content preservation with 35K chunk size
• Intelligent document categorization and organization
• Multi-level hierarchical search and filtering
• Full document reconstruction from chunks
• Advanced AI analysis with summary and topic generation
• Real-time processing with progress tracking
• Visual agent orchestration with custom workflow designer
• Multi-agent collaborative workflows
• Real-time execution monitoring and audit trails
• Database-persistent workflow management

Navigate through different pages to access various features and capabilities.''',
            'suggested_questions': [
                'What are the key themes across all my documents?',
                'Can you provide a hierarchical overview of my document collection?',
                'How are my documents organized by category and type?',
                'What are the main insights from documents in the legal category?',
                'Can you reconstruct the full content of this document?',
                'What topics are covered in technical documents?',
                'How do different document types relate to each other?',
                'What patterns exist in my document hierarchy?',
                'Create an agent workflow to analyze document summaries',
                'Set up a multi-agent conversation about document themes',
                'Design a workflow for collaborative document review',
                'Create agents that can extract and compare key insights',
            'Build custom agent interactions with visual designer',
            'Configure agent roles and responsibilities'
            ],
            'required_fields': ['document_upload'],
            'analysis_focus': 'Hierarchical document analysis with complete content preservation, intelligent categorization, advanced AI insights, and visual agent orchestration capabilities',
            'icon_class': 'fa-sitemap',
            'color_theme': 'oxford-blue',
            'has_navigation': True,
            'total_pages': 4,
            'navigation_pages': [
                {
                    'page_number': 1,
                    'name': 'Project Documents',
                    'short_name': 'Documents',
                    'icon': 'fa-home',
                    'description': 'Upload and manage documents',
                    'features': ['document_management', 'upload_interface', 'processing_status']
                },
                {
                    'page_number': 2,
                    'name': 'Agent Orchestration',
                    'short_name': 'Agents',
                    'icon': 'fa-sitemap',
                    'description': 'Design and run AI workflows',
                    'features': ['visual_workflow_designer', 'agent_management', 'real_time_execution', 'workflow_history']
                },
                {
                    'page_number': 3,
                    'name': 'Evaluation',
                    'short_name': 'Evaluation',
                    'icon': 'fa-clipboard-check',
                    'description': 'Test and compare results',
                    'features': ['workflow_evaluation', 'csv_upload', 'metrics_comparison', 'batch_testing']
                },
                {
                    'page_number': 4,
                    'name': 'Chatbot',
                    'short_name': 'Chat',
                    'icon': 'fa-comments',
                    'description': 'Chat with your AI workflows',
                    'features': ['in_app_chatbot']
                },
            ],
            'processing_capabilities': {
                'supports_ai_analysis': True,
                'supports_vector_search': True,
                'supports_hierarchical_processing': True,
                'supports_enhanced_processing': True,
                'supports_chunking': True,
                'content_preservation': 'complete',
                'processing_mode': 'enhanced_hierarchical',
                'max_file_size': 52428800,  # 50MB for large documents
                'max_chunk_size': 35000,
                'chunk_overlap': 200,
                'supported_formats': ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
                'supported_mime_types': [
                    'application/pdf',
                    'application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'text/plain',
                    'text/markdown',
                    'application/rtf'
                ],
                'ai_models': {
                    'content_analysis': 'gpt-4',
                    'embedding_model': 'text-embedding-ada-002',
                    'summarization_model': 'gpt-4',
                    'topic_extraction_model': 'gpt-4'
                },
                'vector_dimensions': 1536,
                'similarity_threshold': 0.7,
                'batch_processing': True,
                'parallel_processing': True,
                'max_concurrent_processes': 4,
                # Agent Orchestration Capabilities
                'supports_agent_orchestration': True,
                'max_agents_per_workflow': 10,
                'supported_agent_types': ['StartNode', 'UserProxyAgent', 'AssistantAgent', 'GroupChatManager', 'DelegateAgent', 'MCPServer', 'EndNode'],
                'supports_mcp_servers': True,
                'supports_real_time_streaming': True,
                'sandbox_execution': True,
                'workflow_validation': True,
                'agent_conversation_logging': True,
                'websocket_support': True,
                'database_persistence': True,
                'visual_workflow_designer': True,
                'supported_llm_models': ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet'],
                **hierarchical_config['hierarchical_processing'],
                **hierarchical_config['document_organization'],
                **hierarchical_config['search_capabilities'],
                **hierarchical_config['content_reconstruction'],
                **hierarchical_config['ai_processing'],
                **hierarchical_config['performance_settings']
            },
            'validation_rules': {
                'required_fields': ['document_upload'],
                'max_documents': 100,
                'max_total_size': 524288000,  # 500MB total
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
                'content_validation': True,
                'structure_validation': True,
                'integrity_checks': True,
                'duplicate_detection': True,
                **hierarchical_config['quality_control']
            },
            'ui_configuration': {
                'layout': 'hierarchical_multi_page_navigation',
                'theme': 'aicc_intellidoc_enhanced',
                'responsive': True,
                'dark_mode_support': True,
                'features': {
                    'drag_drop_upload': True,
                    'batch_upload': True,
                    'real_time_processing': True,
                    'hierarchical_navigation': True,
                    'category_filtering': True,
                    'advanced_search_interface': True,
                    'document_reconstruction': True,
                    'progress_tracking': True,
                    'error_handling': True,
                    'export_options': True,
                    'auto_save': True,
                    'keyboard_shortcuts': True
                },
                'customizations': {
                    'primary_color': '#002147',  # Oxford Blue
                    'accent_color': '#1e3a8a',
                    'success_color': '#10b981',
                    'warning_color': '#f59e0b',
                    'error_color': '#ef4444',
                    'header_style': 'elevated',
                    'card_style': 'elevated',
                    'animation_level': 'enhanced',
                    'border_radius': '8px',
                    'shadow_level': 'medium'
                },
                'accessibility': {
                    'keyboard_navigation': True,
                    'screen_reader_support': True,
                    'high_contrast_mode': True,
                    'focus_indicators': True,
                    'aria_labels': True
                }
            },
            # Enhanced hierarchical configuration
            'hierarchical_configuration': hierarchical_config,
            'document_categories': hierarchical_config['document_categories'],
            'document_types': hierarchical_config['document_types'],
            'chunk_types': hierarchical_config['chunk_types'],
            'processing_endpoints': hierarchical_config['processing_endpoints']
        }

    def get_hierarchical_search_capabilities(self):
        """Return available hierarchical search capabilities"""
        return {
            'category_search': True,
            'subcategory_search': True,
            'document_type_search': True,
            'hierarchy_level_search': True,
            'chunk_type_search': True,
            'content_length_search': True,
            'combined_filters': True,
            'full_content_reconstruction': True,
            'semantic_search': True,
            'contextual_search': True
        }
    
    def get_processing_recommendations(self):
        """Return processing recommendations based on template capabilities"""
        return {
            'recommended_for': [
                'Large documents (>35,000 characters)',
                'Documents with clear structure',
                'Multi-document projects',
                'Research collections',
                'Technical documentation',
                'Legal document analysis',
                'Medical record processing',
                'Complex document hierarchies'
            ],
            'optimal_use_cases': [
                'Document categorization and organization',
                'Hierarchical content analysis',
                'Multi-level document search',
                'Content reconstruction and navigation',
                'AI-powered document insights',
                'Large-scale document processing'
            ],
            'performance_benefits': [
                'Zero information loss - all content preserved',
                'Intelligent document organization',
                'Enhanced search precision',
                'Full content reconstruction',
                'Hierarchical navigation',
                'Category-based filtering',
                'Multi-level search options',
                'Contextual chunk access'
            ]
        }
