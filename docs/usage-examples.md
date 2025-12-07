# Usage Examples

This document provides comprehensive usage examples for the LiteLLM Codex OAuth Provider, covering basic usage, advanced patterns, and integration scenarios.

## Quick Start

### Basic Setup

```python
from litellm_codex_oauth_provider import CodexAuthProvider

# Initialize the provider
provider = CodexAuthProvider()

# Make a simple completion request
response = provider.completion(
    model="codex/gpt-5.1-codex",
    messages=[
        {"role": "user", "content": "Explain quantum computing in simple terms"}
    ]
)

print(response.choices[0].message.content)
```

### With LiteLLM Proxy

```python
import litellm
from litellm_codex_oauth_provider import CodexAuthProvider

# Set up the custom provider
litellm.register_provider("codex", CodexAuthProvider())

# Use with LiteLLM
response = litellm.completion(
    model="codex/gpt-5.1-codex-max",
    messages=[{"role": "user", "content": "Write a Python function"}]
)
```

## Complete Use Cases

### Use Case 1: Code Generation with Tools

This example demonstrates using the provider with function calling for enhanced code generation.

```python
from litellm_codex_oauth_provider import CodexAuthProvider
import json

provider = CodexAuthProvider()

# Define tools for file operations
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"}
                },
                "required": ["command"]
            }
        }
    }
]

# Make a request with tools
response = provider.completion(
    model="codex/gpt-5.1-codex-max",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful coding assistant. Use the provided tools to complete tasks."
        },
        {
            "role": "user",
            "content": "Create a Python script that reads a CSV file and prints basic statistics"
        }
    ],
    tools=tools,
    tool_choice="auto",
    temperature=0.3
)

print("Response:", response.choices[0].message.content)

# Handle tool calls if present
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"Tool call: {function_name}({arguments})")

        # Simulate tool execution
        if function_name == "create_file":
            print(f"Would create file: {arguments['path']}")
            print(f"Content: {arguments['content'][:100]}...")
        elif function_name == "run_command":
            print(f"Would run command: {arguments['command']}")
```

### Use Case 2: Streaming Code Review

This example shows how to use streaming for interactive code review.

```python
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()

# Code to review
code_to_review = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''

# Set up streaming request
stream = provider.streaming(
    model="codex/gpt-5.1-codex-mini",
    messages=[
        {
            "role": "system",
            "content": "You are an expert code reviewer. Provide detailed feedback on code quality, performance, and best practices."
        },
        {
            "role": "user",
            "content": f"Please review this Python code:\n\n```{code_to_review}```\n\nProvide suggestions for improvement."
        }
    ],
    temperature=0.2,
    max_output_tokens=1000
)

print("Code Review (streaming):")
print("-" * 50)

# Process streaming response
full_response = ""
for chunk in stream:
    if chunk.text:
        print(chunk.text, end="", flush=True)
        full_response += chunk.text

print("\n" + "-" * 50)
print(f"Total tokens: {stream.response.usage.total_tokens}")
```

### Use Case 3: Async Batch Processing

This example demonstrates async usage for processing multiple requests concurrently.

```python
import asyncio
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()

async def process_single_request(prompt: str, model: str = "codex/gpt-5.1-codex"):
    """Process a single completion request asynchronously."""
    response = await provider.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    return {
        "prompt": prompt,
        "response": response.choices[0].message.content,
        "tokens": response.usage.total_tokens
    }

async def batch_process_prompts(prompts: list[str]):
    """Process multiple prompts concurrently."""
    tasks = [process_single_request(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Error processing prompt {i}: {result}")
        else:
            successful_results.append(result)

    return successful_results

# Example usage
async def main():
    prompts = [
        "Explain the difference between lists and tuples in Python",
        "What are decorators and how do they work?",
        "How does Python's garbage collection work?",
        "Explain list comprehensions with examples",
        "What is the difference between @staticmethod and @classmethod?"
    ]

    print("Processing prompts concurrently...")
    results = await batch_process_prompts(prompts)

    print(f"\nProcessed {len(results)} prompts successfully:")
    for result in results:
        print(f"\nPrompt: {result['prompt'][:50]}...")
        print(f"Response: {result['response'][:100]}...")
        print(f"Tokens: {result['tokens']}")

# Run the async example
if __name__ == "__main__":
    asyncio.run(main())
```

### Use Case 4: Custom Model Configuration

This example shows how to use different model configurations for various tasks.

```python
from litellm_codex_oauth_provider import CodexAuthProvider

provider = CodexAuthProvider()

# Configuration for different tasks
model_configs = {
    "creative_writing": {
        "model": "codex/gpt-5.1-codex-max",
        "temperature": 0.9,
        "max_tokens": 2000,
        "top_p": 0.95
    },
    "code_generation": {
        "model": "codex/gpt-5.1-codex-max",
        "temperature": 0.3,
        "max_tokens": 1500,
        "frequency_penalty": 0.1
    },
    "analysis": {
        "model": "codex/gpt-5.1-codex",
        "temperature": 0.2,
        "max_tokens": 1000,
        "presence_penalty": 0.1
    },
    "efficient": {
        "model": "codex/gpt-5.1-codex-mini",
        "temperature": 0.5,
        "max_tokens": 800
    }
}

def make_request(task_type: str, prompt: str):
    """Make a request with task-specific configuration."""
    config = model_configs[task_type]

    response = provider.completion(
        messages=[{"role": "user", "content": prompt}],
        **config
    )

    return {
        "task": task_type,
        "model": config["model"],
        "response": response.choices[0].message.content,
        "usage": response.usage
    }

# Example usage
examples = [
    ("creative_writing", "Write a short story about a time-traveling programmer"),
    ("code_generation", "Create a Python class for managing a database connection"),
    ("analysis", "Analyze the pros and cons of microservices architecture"),
    ("efficient", "Summarize the key features of Python 3.11")
]

for task_type, prompt in examples:
    result = make_request(task_type, prompt)
    print(f"\nTask: {result['task']}")
    print(f"Model: {result['model']}")
    print(f"Response: {result['response'][:150]}...")
    print(f"Tokens used: {result['usage'].total_tokens}")
```

### Use Case 5: Error Handling and Retry Logic

This example demonstrates robust error handling and retry mechanisms.

```python
import time
import random
from litellm_codex_oauth_provider import CodexAuthProvider
from litellm_codex_oauth_provider.exceptions import CodexAuthTokenExpiredError

provider = CodexAuthProvider()

class RetryableError(Exception):
    """Custom exception for retryable errors."""
    pass

def make_request_with_retry(prompt: str, max_retries: int = 3, base_delay: float = 1.0):
    """Make a request with exponential backoff retry logic."""

    for attempt in range(max_retries + 1):
        try:
            response = provider.completion(
                model="codex/gpt-5.1-codex",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            return response

        except RuntimeError as e:
            error_msg = str(e)

            # Handle specific error types
            if "401" in error_msg:
                print("Authentication error - token may be expired")
                raise CodexAuthTokenExpiredError("Token expired") from e

            elif "429" in error_msg:
                # Rate limiting - retry with backoff
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Rate limited. Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise RetryableError(f"Max retries exceeded for rate limiting: {error_msg}")

            elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
                # Server errors - retry with backoff
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Server error. Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise RetryableError(f"Max retries exceeded for server error: {error_msg}")

            else:
                # Non-retryable error
                raise RuntimeError(f"Non-retryable error: {error_msg}")

        except Exception as e:
            # Unexpected error
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"Unexpected error. Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                continue
            else:
                raise RuntimeError(f"Max retries exceeded for unexpected error: {e}")

# Example usage with error handling
def robust_completion_example():
    """Example of robust completion with comprehensive error handling."""

    prompts = [
        "Explain machine learning",
        "Write a Python function",
        "Describe quantum computing",
        "What is Docker?",
        "How does blockchain work?"
    ]

    results = []

    for i, prompt in enumerate(prompts, 1):
        try:
            print(f"\nProcessing request {i}/{len(prompts)}")
            response = make_request_with_retry(prompt)

            results.append({
                "prompt": prompt,
                "response": response.choices[0].message.content,
                "success": True
            })

            print(f"✓ Success: {response.choices[0].message.content[:100]}...")

        except CodexAuthTokenExpiredError:
            print("✗ Authentication failed - please run 'codex login'")
            results.append({
                "prompt": prompt,
                "response": None,
                "success": False,
                "error": "Authentication failed"
            })

        except RetryableError as e:
            print(f"✗ Retryable error: {e}")
            results.append({
                "prompt": prompt,
                "response": None,
                "success": False,
                "error": str(e)
            })

        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            results.append({
                "prompt": prompt,
                "response": None,
                "success": False,
                "error": f"Unexpected: {e}"
            })

    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\nSummary: {successful}/{len(results)} requests successful")

    return results

# Run the robust example
if __name__ == "__main__":
    robust_completion_example()
```

### Use Case 6: Integration with LiteLLM Proxy

This example shows how to integrate with LiteLLM proxy for production use.

```python
# client_example.py - Example client for LiteLLM proxy
import openai
import os

# Configure client to use proxy
client = openai.OpenAI(
    base_url="http://localhost:4000/v1",  # LiteLLM proxy URL
    api_key="sk-your-master-key-12345"   # Proxy master key
)

def chat_completion_example():
    """Example chat completion through proxy."""

    response = client.chat.completions.create(
        model="chatgpt-plus-gpt-5.1-codex-max",  # Model alias from config
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant specialized in Python programming."
            },
            {
                "role": "user",
                "content": "Write a Python function to parse JSON data safely"
            }
        ],
        temperature=0.3,
        max_tokens=1000
    )

    return response

def streaming_example():
    """Example streaming completion through proxy."""

    stream = client.chat.completions.create(
        model="chatgpt-plus-gpt-5.1-codex-mini",
        messages=[
            {"role": "user", "content": "Explain async/await in Python with examples"}
        ],
        stream=True,
        temperature=0.7
    )

    print("Streaming response:")
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()

# Example proxy configuration (config.yaml)
proxy_config = '''
general_settings:
  master_key: sk-your-master-key-12345

model_list:
  - model_name: chatgpt-plus-gpt-5.1-codex-max
    litellm_params:
      model: codex/gpt-5.1-codex-max
  - model_name: chatgpt-plus-gpt-5.1-codex
    litellm_params:
      model: codex/gpt-5.1-codex
  - model_name: chatgpt-plus-gpt-5.1-codex-mini
    litellm_params:
      model: codex/gpt-5.1-codex-mini

litellm_settings:
  custom_provider_map:
    - provider: codex
      custom_handler: litellm_codex_oauth_provider.provider.CodexAuthProvider
  database_url: postgresql://user:pass@localhost/db
  redis_url: redis://localhost:6379
  general_request_timeout: 60
  max_request_timeout: 300

router_settings:
  routing_strategy: "latency-based-routing"
  fallback_models:
    - model_name: chatgpt-plus-gpt-5.1-codex-mini
  model_group:
    - model_group_name: "codex-models"
      models:
        - chatgpt-plus-gpt-5.1-codex-max
        - chatgpt-plus-gpt-5.1-codex
        - chatgpt-plus-gpt-5.1-codex-mini
      routing_strategy: "latency-based-routing"
'''

if __name__ == "__main__":
    # Example usage
    print("=== Chat Completion Example ===")
    response = chat_completion_example()
    print(f"Response: {response.choices[0].message.content[:200]}...")

    print("\n=== Streaming Example ===")
    streaming_example()
```

## Advanced Patterns

### Custom Response Processing

```python
from litellm_codex_oauth_provider import CodexAuthProvider
from litellm import ModelResponse

class CustomCodexProvider(CodexAuthProvider):
    """Extended provider with custom response processing."""

    def _transform_response(self, openai_response: dict[str, Any], model: str) -> ModelResponse:
        """Custom response transformation with additional processing."""

        # Call parent transformation
        response = super()._transform_response(openai_response, model)

        # Add custom processing
        if response.choices:
            choice = response.choices[0]

            # Add metadata
            response.system_fingerprint = f"custom-{response.system_fingerprint}"

            # Process content
            if choice.message.content:
                # Add custom formatting or processing
                processed_content = self._custom_content_processing(choice.message.content)
                choice.message.content = processed_content

        return response

    def _custom_content_processing(self, content: str) -> str:
        """Custom content processing logic."""
        # Example: Add custom formatting
        if content.startswith("```"):
            # Ensure code blocks are properly formatted
            content = content.replace("```python", "```")

        return content

# Usage
custom_provider = CustomCodexProvider()
response = custom_provider.completion(
    model="codex/gpt-5.1-codex",
    messages=[{"role": "user", "content": "Write a Python function"}]
)
```

### Batch Processing with Rate Limiting

```python
import asyncio
import time
from litellm_codex_oauth_provider import CodexAuthProvider

class RateLimitedProvider:
    """Provider wrapper with built-in rate limiting."""

    def __init__(self, requests_per_minute: int = 60):
        self.provider = CodexAuthProvider()
        self.rate_limit = requests_per_minute
        self.request_times = []

    async def completion(self, *args, **kwargs):
        """Rate-limited completion."""
        await self._wait_for_rate_limit()

        start_time = time.time()
        response = await self.provider.acompletion(*args, **kwargs)

        # Record request time
        self.request_times.append(start_time)

        return response

    async def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()

        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        # If at limit, wait
        if len(self.request_times) >= self.rate_limit:
            sleep_time = 60 - (now - self.request_times[0]) + 0.1
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

# Usage
async def batch_with_rate_limiting():
    provider = RateLimitedProvider(requests_per_minute=30)  # 30 requests per minute

    prompts = [f"Question {i}: Explain topic {i}" for i in range(10)]

    tasks = []
    for prompt in prompts:
        task = provider.completion(
            model="codex/gpt-5.1-codex-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        tasks.append(task)

    # Process with rate limiting
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return results

# Run
# results = asyncio.run(batch_with_rate_limiting())
```

## Performance Tips

### 1. Connection Reuse

```python
# Good: Reuse provider instance
provider = CodexAuthProvider()
for i in range(10):
    response = provider.completion(
        model="codex/gpt-5.1-codex",
        messages=[{"role": "user", "content": f"Question {i}"}]
    )

# Avoid: Creating new provider for each request
# for i in range(10):
#     provider = CodexAuthProvider()  # Don't do this
#     response = provider.completion(...)
```

### 2. Async for Multiple Requests

```python
# Good: Use async for concurrent requests
async def process_multiple():
    provider = CodexAuthProvider()
    tasks = [
        provider.acompletion(model="codex/gpt-5.1-codex", messages=[{"role": "user", "content": f"Q{i}"}])
        for i in range(5)
    ]
    return await asyncio.gather(*tasks)

# Avoid: Sequential requests for independent tasks
# responses = []
# for i in range(5):
#     response = provider.completion(...)  # Slower
#     responses.append(response)
```

### 3. Appropriate Model Selection

```python
# Use mini for simple tasks
response = provider.completion(
    model="codex/gpt-5.1-codex-mini",  # Faster, cheaper
    messages=[{"role": "user", "content": "Simple question"}]
)

# Use max for complex reasoning
response = provider.completion(
    model="codex/gpt-5.1-codex-max",  # More capable
    messages=[{"role": "user", "content": "Complex analysis task"}]
)
```

### 4. Token Management

```python
# Set appropriate max_tokens
response = provider.completion(
    model="codex/gpt-5.1-codex",
    messages=[{"role": "user", "content": "Brief summary"}],
    max_tokens=200  # Don't request more than needed
)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Errors

```python
# Error: CodexAuthFileNotFoundError
# Solution: Run 'codex login' first

# Error: CodexAuthTokenExpiredError
# Solution: Token expired, run 'codex login' to refresh
```

#### 2. Model Not Found

```python
# Error: Model not recognized
# Solution: Check model name format
response = provider.completion(
    model="codex/gpt-5.1-codex",  # Correct format
    messages=[{"role": "user", "content": "Hello"}]
)
```

#### 3. Rate Limiting

```python
# Error: 429 Too Many Requests
# Solution: Implement retry with backoff
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RuntimeError as e:
            if "429" in str(e) and attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            raise
```

#### 4. Network Issues

```python
# Handle network timeouts and errors
try:
    response = provider.completion(...)
except RuntimeError as e:
    if "timeout" in str(e).lower():
        print("Request timed out - try again later")
    elif "connection" in str(e).lower():
        print("Network connection issue")
    else:
        print(f"Network error: {e}")
```
