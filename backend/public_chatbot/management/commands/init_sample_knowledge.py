"""
Management command to initialize sample public knowledge for testing
Creates basic knowledge entries for the public chatbot
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from public_chatbot.models import PublicKnowledgeDocument
import uuid


class Command(BaseCommand):
    help = 'Initialize sample public knowledge documents for testing (isolated from main system)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing sample documents before creating new ones'
        )
    
    def handle(self, *args, **options):
        """Execute the initialization command"""
        self.stdout.write(self.style.SUCCESS('🚀 Initializing sample public knowledge base'))
        
        # Clear existing if requested
        if options['clear_existing']:
            deleted_count = PublicKnowledgeDocument.objects.filter(
                created_by='system_init'
            ).count()
            PublicKnowledgeDocument.objects.filter(created_by='system_init').delete()
            self.stdout.write(f"🗑️ Cleared {deleted_count} existing sample documents")
        
        # Sample knowledge documents
        sample_documents = [
            {
                'title': 'Welcome to the Public Chatbot',
                'category': 'general',
                'subcategory': 'introduction',
                'content': '''Welcome to our AI-powered chatbot! This chatbot is designed to help answer your questions using our curated knowledge base.

Key features:
- Intelligent responses based on relevant information
- Fast and accurate search through our knowledge base
- Support for various topics and categories
- Secure and privacy-focused design

Feel free to ask questions about any topic, and I'll do my best to provide helpful information based on the available knowledge.''',
                'tags': 'welcome, introduction, features, help'
            },
            {
                'title': 'How to Use the Chatbot Effectively',
                'category': 'general',
                'subcategory': 'instructions',
                'content': '''To get the best results from this chatbot, consider these tips:

1. Be specific in your questions - clearer questions lead to better answers
2. Use complete sentences when possible
3. If you don't get the answer you're looking for, try rephrasing your question
4. Ask follow-up questions to dive deeper into topics
5. The chatbot works best with factual questions rather than creative writing tasks

Examples of good questions:
- "What are the benefits of renewable energy?"
- "How does machine learning work?"
- "What are the key principles of project management?"

The chatbot draws from a curated knowledge base to provide accurate, helpful responses.''',
                'tags': 'instructions, tips, usage, help, examples'
            },
            {
                'title': 'Artificial Intelligence Basics',
                'category': 'technology',
                'subcategory': 'ai',
                'content': '''Artificial Intelligence (AI) refers to the development of computer systems that can perform tasks that typically require human intelligence.

Key concepts:
- Machine Learning: Systems that learn from data without explicit programming
- Deep Learning: Neural networks with multiple layers that can recognize complex patterns
- Natural Language Processing: AI's ability to understand and generate human language
- Computer Vision: AI systems that can interpret and analyze visual information

Common AI applications:
- Virtual assistants (like chatbots)
- Image recognition
- Recommendation systems
- Autonomous vehicles
- Medical diagnosis assistance

AI is transforming many industries by automating complex tasks and providing intelligent insights from large amounts of data.''',
                'tags': 'artificial intelligence, machine learning, deep learning, technology, automation'
            },
            {
                'title': 'Renewable Energy Sources',
                'category': 'environment',
                'subcategory': 'energy',
                'content': '''Renewable energy comes from naturally replenishing sources that are virtually inexhaustible.

Major types of renewable energy:

Solar Energy:
- Harnesses sunlight using photovoltaic panels or solar thermal collectors
- Clean, abundant, and costs continue to decrease
- Can be deployed at residential or utility scale

Wind Energy:
- Uses wind turbines to generate electricity
- Highly efficient in windy areas
- Both onshore and offshore installations

Hydroelectric:
- Generates power from flowing water
- Reliable and long-lasting infrastructure
- Can provide grid stability services

Geothermal:
- Uses heat from the Earth's core
- Provides consistent, baseload power
- Low environmental footprint

Benefits of renewable energy include reduced greenhouse gas emissions, energy independence, and long-term cost savings.''',
                'tags': 'renewable energy, solar, wind, hydroelectric, geothermal, sustainability, environment'
            },
            {
                'title': 'Healthy Eating Guidelines',
                'category': 'health',
                'subcategory': 'nutrition',
                'content': '''Maintaining a balanced diet is essential for good health and well-being.

Key principles of healthy eating:

Balanced Macronutrients:
- Carbohydrates: 45-65% of daily calories (focus on complex carbs)
- Proteins: 10-35% of daily calories (lean sources preferred)
- Fats: 20-35% of daily calories (emphasize healthy fats)

Essential food groups:
- Fruits and vegetables: At least 5 servings daily
- Whole grains: Choose brown rice, whole wheat, oats
- Lean proteins: Fish, poultry, beans, nuts
- Dairy or alternatives: Low-fat options preferred

Important tips:
- Stay hydrated with plenty of water
- Limit processed foods and added sugars
- Practice portion control
- Eat regular meals throughout the day
- Consider individual dietary needs and restrictions

A balanced diet supports immune function, maintains healthy weight, and reduces risk of chronic diseases.''',
                'tags': 'nutrition, healthy eating, diet, balanced, health, wellness, food groups'
            },
            {
                'title': 'Project Management Fundamentals',
                'category': 'business',
                'subcategory': 'management',
                'content': '''Project management involves planning, executing, and controlling resources to achieve specific goals within defined constraints.

Key project management phases:

1. Initiation:
   - Define project scope and objectives
   - Identify stakeholders
   - Assess feasibility and risks

2. Planning:
   - Create detailed project plan
   - Allocate resources and timeline
   - Develop risk management strategy

3. Execution:
   - Coordinate team activities
   - Implement project deliverables
   - Monitor progress and quality

4. Monitoring & Control:
   - Track performance against plan
   - Manage changes and issues
   - Ensure quality standards

5. Closure:
   - Complete final deliverables
   - Document lessons learned
   - Release project resources

Essential skills:
- Communication and leadership
- Time and resource management
- Risk assessment and mitigation
- Stakeholder engagement
- Problem-solving and adaptability

Successful project management balances scope, time, cost, and quality to deliver value.''',
                'tags': 'project management, planning, execution, leadership, business, organization, methodology'
            }
        ]
        
        # Create documents
        created_count = 0
        for doc_data in sample_documents:
            try:
                # Check if document with similar title already exists
                existing = PublicKnowledgeDocument.objects.filter(
                    title=doc_data['title']
                ).first()
                
                if existing and not options['clear_existing']:
                    self.stdout.write(f"⏭️ Skipped existing: {doc_data['title']}")
                    continue
                
                # Create new document
                doc = PublicKnowledgeDocument.objects.create(
                    title=doc_data['title'],
                    category=doc_data['category'],
                    subcategory=doc_data['subcategory'],
                    content=doc_data['content'],
                    tags=doc_data['tags'],
                    
                    # Approval settings (auto-approve for samples)
                    is_approved=True,
                    security_reviewed=True,
                    quality_score=85,  # Good quality score
                    
                    # Metadata
                    language='en',
                    created_by='system_init',
                    approved_by='system_init',
                    source_url='',
                )
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Created: {doc.title} ({doc.category})")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to create {doc_data['title']}: {e}")
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n🎯 Sample knowledge initialization completed:"))
        self.stdout.write(f"  ✅ Created documents: {created_count}")
        self.stdout.write(f"  📊 Total approved documents: {PublicKnowledgeDocument.objects.filter(is_approved=True).count()}")
        
        # Next steps
        self.stdout.write(self.style.WARNING(f"\n📋 Next steps:"))
        self.stdout.write("1. Start ChromaDB container: docker-compose -f docker-compose-chroma-addon.yml up -d")
        self.stdout.write("2. Sync to ChromaDB: python manage.py sync_public_knowledge")
        self.stdout.write("3. Test the API: curl -X POST http://localhost:8000/api/public-chatbot/ -H 'Content-Type: application/json' -d '{\"message\":\"What is AI?\"}'")
        
        self.stdout.write(self.style.SUCCESS("\n🚀 Sample knowledge base ready for testing!"))