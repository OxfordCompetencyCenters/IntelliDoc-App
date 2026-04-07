# Updated Prompt Structure Examples

## New Structured Format

### Scenario 1: With ChromaDB Context (Most Common)

**Input Components:**
- System Prompt: "You are a helpful assistant providing accurate, concise responses."
- User Message: "What about deep learning specifically?"
- ChromaDB Results: 2 knowledge entries about AI and deep learning
- Conversation History: Previous exchanges about AI

**Final Assembled Prompt:**
```
System: You are a helpful assistant providing accurate, concise responses.

Knowledge Base: [1] Deep Learning Fundamentals (Score: 0.912)
Deep learning is a specialized subset of machine learning that uses artificial neural networks with multiple layers to model and understand complex patterns in large amounts of data. Unlike traditional machine learning algorithms, deep learning models can automatically discover representations from data without manual feature engineering.

[2] Neural Network Architecture (Score: 0.887)
Neural networks in deep learning consist of interconnected nodes (neurons) organized in layers. The input layer receives data, hidden layers process information through weighted connections and activation functions, and the output layer provides results.

User: What is artificial intelligence?
Assistant: AI refers to computer systems designed to perform tasks that typically require human intelligence, such as learning, reasoning, perception, and decision-making.
User: Can you give me examples?
Assistant: Sure! Examples include virtual assistants like Siri, recommendation systems on Netflix, image recognition in photos, language translation, autonomous vehicles, and medical diagnosis systems.
User: What about deep learning specifically?

Please provide a helpful response based on the available information and conversation context.
```

### Scenario 2: Without ChromaDB Context (Fallback)

**Input Components:**
- System Prompt: "You are a helpful assistant providing accurate, concise responses."
- User Message: "Tell me about machine learning"
- ChromaDB Results: None (vector search failed or disabled)
- Conversation History: None (first message)

**Final Assembled Prompt:**
```
System: You are a helpful assistant providing accurate, concise responses.

User: Tell me about machine learning

Please provide a helpful response.
```

### Scenario 3: Custom System Prompt Example

**Input Components:**
- System Prompt: "You are a technical specialist with deep expertise in computer science and AI. Provide detailed, accurate explanations with examples when helpful."
- User Message: "How do transformers work in NLP?"
- ChromaDB Results: 1 knowledge entry about transformers
- Conversation History: Previous technical discussion

**Final Assembled Prompt:**
```
System: You are a technical specialist with deep expertise in computer science and AI. Provide detailed, accurate explanations with examples when helpful.

Knowledge Base: [1] Transformer Architecture (Score: 0.945)
Transformers are a type of deep learning architecture that relies entirely on self-attention mechanisms to draw global dependencies between input and output. They were introduced in the paper "Attention Is All You Need" and have revolutionized natural language processing.

User: What's the difference between RNNs and CNNs?
Assistant: RNNs process sequential data step-by-step and maintain memory through hidden states, making them ideal for time series and text. CNNs use convolutional layers to detect local patterns and are excellent for image processing and spatial data.
User: How do transformers work in NLP?

Please provide a helpful response based on the available information and conversation context.
```

## Key Improvements in New Structure

1. **🏷️ Clear Section Labels**: 
   - `System:` - AI personality and behavior
   - `Knowledge Base:` - ChromaDB context (when available)  
   - `User:` / `Assistant:` - Conversation flow

2. **📚 Separated Knowledge Base**: 
   - ChromaDB content is clearly labeled as "Knowledge Base"
   - Makes it obvious to the AI what information is available
   - Easier to reference specific knowledge entries

3. **🧠 Better Conversation Flow**:
   - Natural conversation format with User/Assistant labels
   - Clear separation between system instructions and conversation

4. **⚙️ Configurable System Behavior**:
   - System prompt is prominently displayed
   - Can be changed via Django admin in real-time
   - Different personalities for different use cases

## Provider-Specific Handling

The structured prompt is sent as the user message, with a minimal system prompt to avoid duplication:

**OpenAI:**
```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},  # Minimal
    {"role": "user", "content": structured_prompt}  # Contains full context
]
```

**Anthropic:**
```python
client.messages.create(
    system="You are a helpful assistant.",  # Minimal
    messages=[{"role": "user", "content": structured_prompt}]
)
```

**Gemini:**
```python
final_prompt = f"You are a helpful assistant.\n\n{structured_prompt}"
```

This ensures the AI gets clear, well-organized instructions while maintaining compatibility across all LLM providers.