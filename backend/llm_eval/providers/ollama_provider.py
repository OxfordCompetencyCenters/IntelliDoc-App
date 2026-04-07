import asyncio
import aiohttp
import json
import time
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = 'http://127.0.0.1:11434'


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider with full tool calling support."""

    def __init__(self, api_key: str = '', model: str = 'gemma3:4b',
                 max_tokens: int = 4096, timeout: int = 900, base_url: str = None):
        super().__init__(api_key='local', model=model, max_tokens=max_tokens, timeout=timeout)
        self.base_url = base_url or OLLAMA_BASE_URL
        self.provider_name = 'ollama'
        self._last_tool_calls = None
        self._last_finish_reason = None

    def get_headers(self) -> Dict[str, str]:
        return {'Content-Type': 'application/json'}

    def format_request_body(self, prompt=None, messages=None, **kwargs) -> Dict[str, Any]:
        if messages:
            formatted = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                images = []

                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        if part.get('type') == 'text':
                            text_parts.append(part.get('text', ''))
                        elif part.get('type') == 'image_url':
                            url = part.get('image_url', {}).get('url', '')
                            if url.startswith('data:'):
                                b64 = url.split(',', 1)[-1] if ',' in url else url
                                images.append(b64)
                            else:
                                images.append(url)
                    content = '\n'.join(text_parts) if text_parts else str(content)

                entry = {'role': role, 'content': content}
                if images:
                    entry['images'] = images

                # Pass through tool_calls from assistant messages (for multi-turn tool calling)
                if role == 'assistant' and msg.get('tool_calls'):
                    entry['tool_calls'] = msg['tool_calls']

                formatted.append(entry)

                # Handle tool role messages (tool results)
                if role == 'tool':
                    # Ollama expects tool results as role: 'tool'
                    pass  # Already handled above
        else:
            formatted = [{'role': 'user', 'content': prompt or ''}]

        body = {
            'model': self.model,
            'messages': formatted,
            'stream': False,
            'options': {
                'num_predict': self.max_tokens,
            }
        }

        # Add tools if provided (OpenAI-compatible format)
        tools = kwargs.get('tools')
        if tools:
            body['tools'] = tools

        return body

    def parse_response(self, response_data: Dict[str, Any]) -> tuple:
        message = response_data.get('message', {})
        text = message.get('content', '') or ''
        eval_count = response_data.get('eval_count')

        # Parse tool calls from Ollama response
        # Ollama format: message.tool_calls = [{"function": {"name": "...", "arguments": {...}}}]
        raw_tool_calls = message.get('tool_calls')
        if raw_tool_calls:
            normalized = []
            for i, tc in enumerate(raw_tool_calls):
                fn = tc.get('function', {})
                args = fn.get('arguments', {})
                # Arguments may be a string or dict
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {'raw': args}
                normalized.append({
                    'id': tc.get('id', f'call_{i}_{int(time.time())}'),
                    'name': fn.get('name', ''),
                    'arguments': args,
                })
            self._last_tool_calls = normalized
            self._last_finish_reason = 'tool_calls'
            logger.info(f"🔧 OLLAMA: Parsed {len(normalized)} tool calls: {[tc['name'] for tc in normalized]}")
        else:
            self._last_tool_calls = None
            self._last_finish_reason = response_data.get('done_reason', 'stop')

        return text, eval_count

    async def generate_response(self, prompt=None, messages=None, **kwargs) -> LLMResponse:
        start_time = time.time()
        body = self.format_request_body(prompt=prompt, messages=messages, **kwargs)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/api/chat',
                    json=body,
                    headers=self.get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return LLMResponse(
                            text='', model=self.model, provider='ollama',
                            response_time_ms=int((time.time() - start_time) * 1000),
                            error=f'Ollama error {resp.status}: {error_text}'
                        )

                    data = await resp.json()
                    text, token_count = self.parse_response(data)
                    response_time_ms = int((time.time() - start_time) * 1000)

                    # If tool calls were returned, include them in the response
                    if self._last_tool_calls:
                        return LLMResponse(
                            text=text or '',
                            model=self.model,
                            provider='ollama',
                            response_time_ms=response_time_ms,
                            token_count=token_count,
                            cost_estimate=0.0,
                            tool_calls=self._last_tool_calls,
                            finish_reason=self._last_finish_reason,
                        )

                    return LLMResponse(
                        text=text,
                        model=self.model,
                        provider='ollama',
                        response_time_ms=response_time_ms,
                        token_count=token_count,
                        cost_estimate=0.0,
                        finish_reason=self._last_finish_reason or 'stop',
                    )
        except asyncio.TimeoutError:
            elapsed = int((time.time() - start_time) * 1000)
            return LLMResponse(
                text='', model=self.model, provider='ollama',
                response_time_ms=elapsed,
                error=f'Ollama timed out after {elapsed // 1000}s. The document may be too large for the model.'
            )
        except aiohttp.ClientError as e:
            return LLMResponse(
                text='', model=self.model, provider='ollama',
                response_time_ms=int((time.time() - start_time) * 1000),
                error=f'Ollama connection error: {str(e)}. Is the Docker container running?'
            )
        except Exception as e:
            return LLMResponse(
                text='', model=self.model, provider='ollama',
                response_time_ms=int((time.time() - start_time) * 1000),
                error=f'Ollama error: {type(e).__name__}: {str(e) or "Unknown error"}'
            )

    async def generate_response_stream(self, prompt=None, messages=None, **kwargs) -> AsyncGenerator[str, None]:
        body = self.format_request_body(prompt=prompt, messages=messages, **kwargs)
        body['stream'] = True

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/api/chat',
                    json=body,
                    headers=self.get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    async for line in resp.content:
                        line = line.decode('utf-8').strip()
                        if line:
                            try:
                                data = json.loads(line)
                                content = data.get('message', {}).get('content', '')
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f'Ollama stream error: {e}')
            yield f'[Error: {str(e)}]'
