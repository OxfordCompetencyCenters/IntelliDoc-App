class HierarchicalProcessingConfig:
    """Hierarchical processing configuration for AICC-IntelliDoc template"""
    
    @staticmethod
    def get_hierarchical_configuration():
        """Return hierarchical processing configuration for enhanced document analysis"""
        return {
            # Core hierarchical processing capabilities
            'hierarchical_processing': {
                'enabled': True,
                'processing_mode': 'enhanced',
                'chunk_strategy': 'intelligent_hierarchical',
                'content_preservation': 'complete',
                'max_chunk_size': 35000,
                'boundary_aware_splitting': True,
                'section_detection': True,
                'hierarchy_detection': True,
                'category_auto_classification': True,
                'document_type_classification': True
            },
            
            # Document organization capabilities
            'document_organization': {
                'virtual_folder_structure': True,
                'filename_based_categorization': True,
                'automatic_category_detection': True,
                'subcategory_recognition': True,
                'hierarchy_level_assignment': True,
                'organizational_pattern_detection': True,
                'version_tracking_hints': True
            },
            
            # Search and retrieval capabilities
            'search_capabilities': {
                'document_level_search': True,
                'chunk_level_search': True,
                'hybrid_search': True,
                'category_filtered_search': True,
                'hierarchy_filtered_search': True,
                'content_type_filtered_search': True,
                'multi_filter_search': True,
                'contextual_search': True,
                'semantic_search': True,
                'similarity_threshold': 0.7
            },
            
            # Content reconstruction capabilities
            'content_reconstruction': {
                'full_document_rebuild': True,
                'ordered_chunk_combination': True,
                'section_separator_handling': True,
                'content_integrity_maintained': True,
                'original_structure_preserved': True,
                'hierarchical_navigation': True
            },
            
            # AI processing capabilities
            'ai_processing': {
                'summary_generation': True,
                'topic_extraction': True,
                'content_analysis': True,
                'entity_recognition': True,
                'sentiment_analysis': True,
                'key_phrase_extraction': True,
                'document_classification': True,
                'relationship_mapping': True
            },
            
            # Processing endpoints configuration
            'processing_endpoints': {
                'enhanced_processing': '/api/projects/{project_id}/digest-enhanced/',
                'enhanced_search': '/api/projects/{project_id}/search-enhanced/',
                'hierarchical_overview': '/api/projects/{project_id}/hierarchy-overview/',
                'document_reconstruction': '/api/projects/{project_id}/documents/{document_id}/full-content/',
                'category_search': '/api/projects/{project_id}/search-by-category/',
                'advanced_search': '/api/projects/{project_id}/advanced-search/'
            },
            
            # Supported document categories
            'document_categories': [
                {
                    'id': 'legal',
                    'name': 'Legal Documents',
                    'description': 'Contracts, agreements, legal papers',
                    'subcategories': [
                        {'id': 'contracts', 'name': 'Contracts'},
                        {'id': 'policies', 'name': 'Policies'},
                        {'id': 'compliance', 'name': 'Compliance'}
                    ]
                },
                {
                    'id': 'medical',
                    'name': 'Medical Documents',
                    'description': 'Health records, clinical documents',
                    'subcategories': [
                        {'id': 'reports', 'name': 'Medical Reports'},
                        {'id': 'records', 'name': 'Medical Records'},
                        {'id': 'procedures', 'name': 'Medical Procedures'}
                    ]
                },
                {
                    'id': 'technical',
                    'name': 'Technical Documents',
                    'description': 'Specifications, manuals, guides',
                    'subcategories': [
                        {'id': 'specifications', 'name': 'Specifications'},
                        {'id': 'manuals', 'name': 'Manuals'},
                        {'id': 'documentation', 'name': 'Documentation'}
                    ]
                },
                {
                    'id': 'research',
                    'name': 'Research Documents',
                    'description': 'Papers, studies, analysis',
                    'subcategories': [
                        {'id': 'papers', 'name': 'Research Papers'},
                        {'id': 'reports', 'name': 'Research Reports'},
                        {'id': 'data', 'name': 'Research Data'}
                    ]
                },
                {
                    'id': 'financial',
                    'name': 'Financial Documents',
                    'description': 'Financial reports, budgets, invoices',
                    'subcategories': [
                        {'id': 'budgets', 'name': 'Budgets'},
                        {'id': 'invoices', 'name': 'Invoices'},
                        {'id': 'reports', 'name': 'Financial Reports'}
                    ]
                },
                {
                    'id': 'general',
                    'name': 'General Documents',
                    'description': 'Miscellaneous documents',
                    'subcategories': []
                }
            ],
            
            # Document types for classification
            'document_types': [
                {'id': 'report', 'name': 'Report', 'description': 'Reports and summaries'},
                {'id': 'manual', 'name': 'Manual', 'description': 'Manuals and guides'},
                {'id': 'specification', 'name': 'Specification', 'description': 'Technical specifications'},
                {'id': 'policy', 'name': 'Policy', 'description': 'Policies and procedures'},
                {'id': 'presentation', 'name': 'Presentation', 'description': 'Presentations and slides'},
                {'id': 'correspondence', 'name': 'Correspondence', 'description': 'Emails and letters'},
                {'id': 'document', 'name': 'General Document', 'description': 'General documents'}
            ],
            
            # Chunk types for advanced filtering
            'chunk_types': [
                {'id': 'complete_document', 'name': 'Complete Document', 'description': 'Documents that fit in single chunk'},
                {'id': 'introduction', 'name': 'Introduction', 'description': 'Document introductions'},
                {'id': 'section', 'name': 'Section', 'description': 'Document sections'},
                {'id': 'section_part', 'name': 'Section Part', 'description': 'Parts of large sections'},
                {'id': 'content', 'name': 'Content', 'description': 'General content chunks'},
                {'id': 'content_part', 'name': 'Content Part', 'description': 'Parts of sequential content'}
            ],
            
            # Performance and optimization settings
            'performance_settings': {
                'batch_processing': True,
                'parallel_processing': True,
                'max_concurrent_processes': 4,
                'memory_optimization': True,
                'cache_embeddings': True,
                'background_processing': True,
                'progress_tracking': True,
                'error_recovery': True
            },
            
            # Validation and quality control
            'quality_control': {
                'content_validation': True,
                'structure_validation': True,
                'integrity_checks': True,
                'duplicate_detection': True,
                'consistency_validation': True,
                'error_detection': True,
                'quality_scoring': True
            }
        }
