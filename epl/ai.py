"""
EPL AI Module (v1.2)
Integration with Ollama for local AI capabilities.
Supports: chat, generate, code assist, error explanation, code generation,
embeddings, streaming, and custom EPL-trained model creation.
"""

import json
import sys
import urllib.error
import urllib.request

from epl import _debug_log

# ─── Configuration ───────────────────────────────────────
OLLAMA_HOST = 'http://localhost:11434'
DEFAULT_MODEL = 'llama3.2'

# ─── Cloud Provider Configuration ────────────────────────
CLOUD_PROVIDER = None  # 'gemini', 'groq', or None (use Ollama)
CLOUD_API_KEY = None
CLOUD_MODEL = None  # Override cloud model (auto-selected if None)

GROQ_BASE_URL = 'https://api.groq.com/openai/v1'
GROQ_DEFAULT_MODEL = 'llama-3.3-70b-versatile'

GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
GEMINI_DEFAULT_MODEL = 'gemini-2.0-flash'  # Fast, free, works globally

# Available free Groq models
GROQ_MODELS = [
    ('llama-3.3-70b-versatile', 'Llama 3.3 70B — best quality'),
    ('llama-3.1-8b-instant', 'Llama 3.1 8B — fastest'),
    ('gemma2-9b-it', 'Gemma 2 9B — Google, good quality'),
    ('mixtral-8x7b-32768', 'Mixtral 8x7B — 32K context'),
]

# Available free Gemini models
GEMINI_MODELS = [
    ('gemini-2.0-flash', 'Gemini 2.0 Flash — fast, recommended'),
    ('gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite — fastest'),
    ('gemini-1.5-flash', 'Gemini 1.5 Flash — stable'),
    ('gemini-1.5-pro', 'Gemini 1.5 Pro — best quality'),
]

_CONFIG_PATH = None  # Set lazily
_CONFIG_LOADED = False  # Cache flag — avoid re-reading disk on every call

# Keyring service identifier — stable across versions; do not rename without a migration.
_KEYRING_SERVICE = 'epl-lang'
_KEYRING_USER = 'cloud_api_key'


def _try_keyring():
    """Return the `keyring` module if usable on this system, else None.

    Keyring backends can fail to initialise on headless Linux without a
    DBus/Secret Service, in CI containers, or on locked-down Windows. We
    catch every failure path so callers can fall back to the JSON store.
    """
    try:
        import keyring  # type: ignore
    except ImportError:
        return None
    try:
        # Probing the backend forces it to initialise; the fail-backend
        # (no usable store) raises here, so we can detect it cleanly.
        backend = keyring.get_keyring()
        cls_name = type(backend).__name__
        if 'fail' in cls_name.lower() or 'null' in cls_name.lower():
            return None
    except Exception:
        _debug_log.suppressed('ai:69')
        return None
    return keyring


def _get_config_path():
    """Get path to the EPL AI config file.

    Uses an XDG-aware per-user directory:
      - Windows: %APPDATA%\\epl\\ai_config.json
      - POSIX:   $XDG_CONFIG_HOME/epl/ai_config.json (default ~/.config/epl/...)

    Legacy path (epl/.ai_config.json inside the package) is migrated on first
    access so existing users do not lose their config.
    """
    global _CONFIG_PATH
    if _CONFIG_PATH is None:
        import os

        if os.name == 'nt':
            base = os.environ.get('APPDATA') or os.path.join(
                os.path.expanduser('~'), 'AppData', 'Roaming'
            )
        else:
            base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(
                os.path.expanduser('~'), '.config'
            )
        cfg_dir = os.path.join(base, 'epl')
        try:
            os.makedirs(cfg_dir, exist_ok=True)
        except OSError:
            pass
        _CONFIG_PATH = os.path.join(cfg_dir, 'ai_config.json')

        # One-shot migration from the legacy in-package location.
        legacy = os.path.join(os.path.dirname(__file__), '.ai_config.json')
        if os.path.exists(legacy) and not os.path.exists(_CONFIG_PATH):
            try:
                with (
                    open(legacy, 'r', encoding='utf-8') as src,
                    open(_CONFIG_PATH, 'w', encoding='utf-8') as dst,
                ):
                    dst.write(src.read())
                _chmod_secret(_CONFIG_PATH)
                os.remove(legacy)
            except OSError:
                pass
    return _CONFIG_PATH


def _chmod_secret(path):
    """Best-effort: restrict config file to owner-only read/write."""
    import os

    if os.name != 'nt':
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _load_config(force=False):
    """Load saved cloud config from disk + keyring.

    Cached after first call (configure_cloud/clear_cloud invalidate the cache),
    so we don't hit disk on every prompt.

    Storage layout (since v9.2.0):
      - Non-secret fields (provider, model) live in JSON on disk.
      - The API key lives in the OS keyring under (epl-lang, cloud_api_key).
      - Legacy plaintext `api_key` in JSON is auto-migrated to keyring on read
        and the field is wiped from JSON. If no keyring is available, JSON
        remains the fallback store.
    """
    global CLOUD_PROVIDER, CLOUD_API_KEY, CLOUD_MODEL, _CONFIG_LOADED
    if _CONFIG_LOADED and not force:
        return
    path = _get_config_path()
    cfg = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        CLOUD_PROVIDER = cfg.get('provider')
        CLOUD_MODEL = cfg.get('model')
    except FileNotFoundError:
        pass  # no config yet — expected on first run
    except json.JSONDecodeError as e:
        sys.stderr.write(f'[EPL] warning: ignoring corrupt AI config at {path}: {e}\n')
    except OSError as e:
        _debug_log.suppressed('ai:156', e)

    kr = _try_keyring()
    legacy_key = cfg.get('api_key') if isinstance(cfg, dict) else None
    if kr is not None:
        try:
            stored = kr.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            stored = None
        if stored:
            CLOUD_API_KEY = stored
        elif legacy_key:
            # Migrate plaintext → keyring, then scrub the JSON file.
            try:
                kr.set_password(_KEYRING_SERVICE, _KEYRING_USER, legacy_key)
                CLOUD_API_KEY = legacy_key
                cfg.pop('api_key', None)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2)
                _chmod_secret(path)
            except Exception:
                CLOUD_API_KEY = legacy_key
        else:
            CLOUD_API_KEY = None
    else:
        # No keyring → JSON is the only store.
        CLOUD_API_KEY = legacy_key

    _CONFIG_LOADED = True


def _save_config():
    """Save cloud config to disk (non-secret) and keyring (secret).

    The on-disk JSON never contains the API key when a keyring is available.
    If keyring is unavailable, the key falls back to JSON with 0600 perms —
    not ideal, but documented and the only portable option on locked-down hosts.
    """
    path = _get_config_path()
    cfg = {
        'provider': CLOUD_PROVIDER,
        'model': CLOUD_MODEL,
    }
    kr = _try_keyring()
    if kr is not None and CLOUD_API_KEY:
        try:
            kr.set_password(_KEYRING_SERVICE, _KEYRING_USER, CLOUD_API_KEY)
        except Exception:
            # Keyring write failed — fall back to JSON so the user does not
            # lose their key. We log nothing here; configure_cloud is the
            # right place for any UI feedback.
            cfg['api_key'] = CLOUD_API_KEY
    elif kr is None and CLOUD_API_KEY:
        cfg['api_key'] = CLOUD_API_KEY

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    _chmod_secret(path)


def configure_cloud(provider, api_key, model=None):
    """Configure a cloud AI provider.

    Args:
        provider: 'gemini' or 'groq'
        api_key: API key string
        model: Optional model override
    """
    global CLOUD_PROVIDER, CLOUD_API_KEY, CLOUD_MODEL, _CONFIG_LOADED
    CLOUD_PROVIDER = provider
    CLOUD_API_KEY = api_key
    CLOUD_MODEL = model
    _CONFIG_LOADED = True  # in-memory state is authoritative
    _save_config()


def clear_cloud():
    """Remove cloud provider, revert to Ollama. Wipes both JSON and keyring."""
    global CLOUD_PROVIDER, CLOUD_API_KEY, CLOUD_MODEL, _CONFIG_LOADED
    CLOUD_PROVIDER = None
    CLOUD_API_KEY = None
    CLOUD_MODEL = None
    _CONFIG_LOADED = True
    import os

    kr = _try_keyring()
    if kr is not None:
        try:
            kr.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            # Entry didn't exist or backend refused; safe to ignore.
            pass

    path = _get_config_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _mask_key(key):
    """Mask an API key for safe display. Always shows at most 4 chars of either end."""
    if not key:
        return ''
    if len(key) <= 12:
        return '*' * len(key)
    return key[:4] + '...' + key[-4:]


def get_cloud_status():
    """Return current cloud configuration status."""
    _load_config()
    if CLOUD_PROVIDER and CLOUD_API_KEY:
        masked = _mask_key(CLOUD_API_KEY)
        model = CLOUD_MODEL or _get_cloud_default_model()
        return {'provider': CLOUD_PROVIDER, 'key_masked': masked, 'model': model, 'active': True}
    return {'provider': None, 'active': False}


def _get_cloud_default_model():
    """Get the default model for the current cloud provider."""
    if CLOUD_PROVIDER == 'groq':
        return GROQ_DEFAULT_MODEL
    if CLOUD_PROVIDER == 'gemini':
        return GEMINI_DEFAULT_MODEL
    return None


def _use_cloud():
    """Check if cloud provider is configured and should be used."""
    _load_config()
    return bool(CLOUD_PROVIDER and CLOUD_API_KEY)


# ─── Cloud API ───────────────────────────────────────────


def _cloud_request(messages, system=None, temperature=0.7, max_tokens=2048):
    """Make a request to the configured cloud provider.
    Dispatches to Groq (OpenAI-compatible) or Gemini (Google) API.

    Returns:
        Response text string, or error string prefixed with 'Error:'
    """
    _load_config()

    if CLOUD_PROVIDER == 'gemini':
        return _gemini_request(
            messages, system=system, temperature=temperature, max_tokens=max_tokens
        )
    elif CLOUD_PROVIDER == 'groq':
        return _groq_request(
            messages, system=system, temperature=temperature, max_tokens=max_tokens
        )
    else:
        return f'Error: Unknown cloud provider: {CLOUD_PROVIDER}'


def _gemini_request(messages, system=None, temperature=0.7, max_tokens=2048):
    """Make a request to Google Gemini API.

    Gemini uses its own format:
    - POST /v1beta/models/{model}:generateContent?key=API_KEY
    - Body: {contents: [{parts: [{text: ...}]}], systemInstruction: ...}
    """
    model = CLOUD_MODEL or GEMINI_DEFAULT_MODEL
    # Use header-based auth so the key never appears in URLs / proxy logs / shell history.
    url = f'{GEMINI_BASE_URL}/models/{model}:generateContent'

    # Build contents array
    contents = []
    if isinstance(messages, str):
        contents.append({'role': 'user', 'parts': [{'text': messages}]})
    else:
        for msg in messages:
            role = msg.get('role', 'user')
            text = msg.get('content', '')
            # Gemini uses 'user' and 'model' (not 'assistant')
            if role == 'assistant':
                role = 'model'
            if role == 'system':
                continue  # handled separately
            contents.append({'role': role, 'parts': [{'text': text}]})

    payload = {
        'contents': contents,
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        },
    }

    # Add system instruction
    if system:
        payload['systemInstruction'] = {'parts': [{'text': system}]}

    try:
        body = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': CLOUD_API_KEY or '',
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            candidates = result.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', '')
            # Check for errors in response
            if 'error' in result:
                msg = result['error'].get('message', 'Unknown error')
                return f'Error: Gemini API: {msg}'
            return 'Error: No response from Gemini API'
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        try:
            err = json.loads(body)
            msg = err.get('error', {}).get('message', body[:200])
        except json.JSONDecodeError:
            msg = body[:200]
        return f'Error: Gemini API error ({e.code}): {msg}'
    except urllib.error.URLError as e:
        return f'Error: Cannot reach Gemini API: {e.reason}'
    except Exception as e:
        return f'Error: {e}'


def _groq_request(messages, system=None, temperature=0.7, max_tokens=2048):
    """Make a request to Groq API (OpenAI-compatible format)."""
    model = CLOUD_MODEL or GROQ_DEFAULT_MODEL
    url = f'{GROQ_BASE_URL}/chat/completions'

    # Build messages array
    msgs = []
    if system:
        msgs.append({'role': 'system', 'content': system})
    if isinstance(messages, str):
        msgs.append({'role': 'user', 'content': messages})
    else:
        if system:
            msgs = [{'role': 'system', 'content': system}]
        msgs.extend(messages)

    payload = {
        'model': model,
        'messages': msgs,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CLOUD_API_KEY}',
        'User-Agent': 'EPL/1.3',
    }

    try:
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            choices = result.get('choices', [])
            if choices:
                return choices[0].get('message', {}).get('content', '')
            return 'Error: No response from Groq API'
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        try:
            err = json.loads(body)
            msg = err.get('error', {}).get('message', body[:200])
        except json.JSONDecodeError:
            msg = body[:200]
        return f'Error: Groq API error ({e.code}): {msg}'
    except urllib.error.URLError as e:
        return f'Error: Cannot reach Groq API: {e.reason}'
    except Exception as e:
        return f'Error: {e}'


def set_host(host):
    """Set the Ollama API host."""
    global OLLAMA_HOST
    OLLAMA_HOST = host


def set_model(model):
    """Set the default model."""
    global DEFAULT_MODEL
    DEFAULT_MODEL = model


# ─── Core API ────────────────────────────────────────────


def _request(endpoint, data=None, method='POST', timeout=600):
    """Make an HTTP request to Ollama API.

    Args:
        endpoint: API endpoint path (e.g., '/api/generate')
        data: Request body dict (will be JSON-encoded)
        method: HTTP method
        timeout: Request timeout in seconds (default: 600s for CPU inference)
    """
    url = f'{OLLAMA_HOST}{endpoint}'
    try:
        if data:
            body = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                url, data=body, headers={'Content-Type': 'application/json'}, method=method
            )
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (TimeoutError, OSError) as e:
        if 'timed out' in str(e).lower():
            return {
                'error': f'Request timed out after {timeout}s. The model may still be loading — try again shortly.'
            }
        return {'error': f'Cannot connect to Ollama at {OLLAMA_HOST}. Is Ollama running? ({e})'}
    except urllib.error.URLError as e:
        reason = getattr(e, 'reason', e)
        if 'timed out' in str(reason).lower():
            return {
                'error': f'Request timed out after {timeout}s. The model may still be loading — try again shortly.'
            }
        return {
            'error': f'Cannot connect to Ollama at {OLLAMA_HOST}. Is Ollama running? ({reason})'
        }
    except Exception as e:
        return {'error': str(e)}


def _stream_request(endpoint, data, timeout=600):
    """Make a streaming request to Ollama API, yield chunks."""
    url = f'{OLLAMA_HOST}{endpoint}'
    data['stream'] = True
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            buffer = ''
            while True:
                chunk = resp.read(1)
                if not chunk:
                    break
                c = chunk.decode('utf-8', errors='ignore')
                buffer += c
                if c == '\n' and buffer.strip():
                    try:
                        obj = json.loads(buffer.strip())
                        yield obj
                    except json.JSONDecodeError:
                        _debug_log.suppressed('ai:512:stream')
                    buffer = ''
    except Exception as e:
        yield {'error': str(e)}


# ─── High-Level Functions ────────────────────────────────


def _clean_response(text):
    """Strip thinking blocks and clean up model output.
    Qwen3 models include <think>...</think> blocks that should be removed."""
    import re

    # Remove <think>...</think> blocks (qwen3 thinking mode)
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Remove "Thinking..." prefix lines
    cleaned = re.sub(r'^\s*Thinking\.{3}\s*\n?', '', cleaned)
    return cleaned.strip()


def generate(prompt, model=None, system=None, temperature=0.7, max_tokens=2048, timeout=600):
    """Generate text from a prompt.
    Uses cloud provider (Groq) if configured, otherwise falls back to Ollama.

    Args:
        prompt: The text prompt
        model: Model name (default: auto-selected)
        system: System prompt override
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Max tokens to generate
        timeout: Request timeout in seconds (for Ollama only)
    """
    # ── Cloud path (fast) ──
    if _use_cloud():
        result = _cloud_request(
            prompt, system=system, temperature=temperature, max_tokens=max_tokens
        )
        return _clean_response(result)

    # ── Ollama path (local) ──
    use_model = model or DEFAULT_MODEL
    data = {
        'model': use_model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': temperature,
            'num_predict': max_tokens,
        },
    }
    if system:
        data['system'] = system
    result = _request('/api/generate', data, timeout=timeout)
    if 'error' in result:
        return result['error']
    response = result.get('response', '')
    # If response is empty but thinking exists (qwen3 ran out of tokens on thinking),
    # extract useful content from thinking field as fallback
    if not response.strip() and result.get('thinking'):
        response = (
            '(Model used all tokens for reasoning. Try a simpler prompt or increase max_tokens.)'
        )
    return _clean_response(response)


def chat(messages, model=None, system=None, temperature=0.7, timeout=600):
    """Chat with a model. Messages: [{"role": "user", "content": "..."}].
    Uses cloud provider if configured, otherwise Ollama."""
    # ── Cloud path ──
    if _use_cloud():
        result = _cloud_request(messages, system=system, temperature=temperature)
        return _clean_response(result)

    # ── Ollama path ──
    msgs = list(messages)
    if system:
        msgs.insert(0, {'role': 'system', 'content': system})
    data = {
        'model': model or DEFAULT_MODEL,
        'messages': msgs,
        'stream': False,
        'options': {'temperature': temperature},
    }
    result = _request('/api/chat', data, timeout=timeout)
    if 'error' in result:
        return result['error']
    return _clean_response(result.get('message', {}).get('content', ''))


def embed(text, model=None):
    """Get embeddings for text."""
    data = {'model': model or DEFAULT_MODEL, 'prompt': text}
    result = _request('/api/embeddings', data)
    if 'error' in result:
        return []
    return result.get('embedding', [])


def list_models():
    """List available Ollama models."""
    result = _request('/api/tags', method='GET', timeout=10)
    if 'error' in result:
        return []
    models = result.get('models', [])
    return [m.get('name', '') for m in models]


def pull_model(name):
    """Pull/download a model."""
    data = {'name': name, 'stream': False}
    result = _request('/api/pull', data)
    return 'error' not in result


def is_available():
    """Check if Ollama is running and accessible."""
    try:
        req = urllib.request.Request(f'{OLLAMA_HOST}/api/tags')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ─── Code Assistant ──────────────────────────────────────


def code_assist(prompt, language='EPL'):
    """Get AI code assistance. Prefers the custom EPL-Coder model if available."""
    model = None
    if language == 'EPL' and model_exists():
        model = EPL_MODEL_NAME
    if language == 'EPL':
        from epl.syntax_reference import get_syntax_text

        syntax_guide = get_syntax_text()
        system = (
            'You are an expert EPL programming assistant. '
            'Write clean, working, parser-valid EPL code. '
            'Prefer the authoritative syntax forms below and output only code unless asked for explanations.\n\n'
            f'{syntax_guide}'
        )
    else:
        system = f'You are an expert {language} programming assistant. Write clean, working code. Be concise and helpful.'
    return generate(prompt, model=model, system=system)


def explain_code(code, language='EPL'):
    """Explain what a piece of code does."""
    return generate(
        f'Explain what this {language} code does:\n\n{code}',
        system='You are a helpful programming tutor. Explain code clearly and concisely.',
    )


def fix_code(code, error_message='', language='EPL'):
    """Fix code that has errors."""
    prompt = f'Fix this {language} code'
    if error_message:
        prompt += f' (error: {error_message})'
    prompt += f':\n\n{code}'
    return generate(
        prompt,
        system=f'You are an expert {language} debugger. Fix the code and explain what was wrong.',
    )


def improve_code(code, language='EPL'):
    """Suggest improvements for code."""
    return generate(
        f'Improve this {language} code (make it more efficient, readable, or idiomatic):\n\n{code}',
        system=f'You are an expert {language} code reviewer. Suggest improvements.',
    )


# ─── AI Error Explanation ────────────────────────────────


def explain_error(error_message, source_code=None, language='EPL'):
    """Use AI to explain an EPL error and suggest a fix.

    Args:
        error_message: The EPL error string (e.g., 'EPL Name Error on line 5: ...')
        source_code: Optional source code that caused the error
        language: Programming language (default: EPL)

    Returns:
        AI explanation with fix suggestions
    """
    model = EPL_MODEL_NAME if model_exists() else None

    prompt = f'The following EPL error occurred:\n\n  {error_message}\n'
    if source_code:
        prompt += f'\nThe source code is:\n```epl\n{source_code}\n```\n'
    prompt += '\nExplain what went wrong in simple terms and show the corrected code.'

    system = (
        'You are EPL-Coder, an expert EPL debugging assistant. '
        'When given an error, explain clearly what went wrong, why it happened, '
        'and provide the corrected EPL code. Be concise and helpful.'
    )

    return generate(prompt, model=model, system=system)


def generate_epl_code(description, filename=None):
    """Generate EPL code from a natural language description.

    Args:
        description: What the code should do (e.g., 'sort a list of numbers')
        filename: Optional filename to save to

    Returns:
        Tuple of (generated_code, explanation)
    """
    model = EPL_MODEL_NAME if model_exists() else None

    from epl.syntax_reference import get_syntax_text

    system = (
        'You are EPL-Coder, an expert EPL code generator. '
        'Given a description, generate clean, working EPL code that matches the real parser-supported syntax. '
        'Output ONLY the EPL code wrapped in ```epl ... ``` blocks, followed by a brief explanation.\n\n'
        f'{get_syntax_text()}'
    )

    prompt = f'Generate EPL code that does the following: {description}'

    response = generate(prompt, model=model, system=system)

    # Extract code block from response
    code = _extract_code_block(response)

    if filename and code:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(code)

    return code, response


def _extract_code_block(text):
    """Extract EPL code from a markdown code block in the AI response."""
    import re

    # Try ```epl ... ``` first
    match = re.search(r'```(?:epl)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: return the whole text if no code blocks
    return text.strip()


# ─── Conversational AI ──────────────────────────────────


class Conversation:
    """Maintains a multi-turn conversation with an AI model."""

    def __init__(self, model=None, system=None):
        self.model = model or DEFAULT_MODEL
        self.system = system
        self.messages = []

    def say(self, message):
        """Send a message and get a response."""
        self.messages.append({'role': 'user', 'content': message})
        response = chat(self.messages, model=self.model, system=self.system)
        self.messages.append({'role': 'assistant', 'content': response})
        return response

    def reset(self):
        """Clear conversation history."""
        self.messages = []

    def get_history(self):
        """Get conversation history."""
        return list(self.messages)


# ─── EPL Model Name ─────────────────────────────────────
EPL_MODEL_NAME = 'epl-coder'

# ─── Base Models (small, fast, good for code) ───────────
BASE_MODELS = [
    ('qwen3:4b', '2.5 GB', 'Recommended — Qwen 3 4B (best balance)'),
    ('qwen2.5-coder:7b', '4.7 GB', 'Best code quality — Qwen 2.5 Coder 7B'),
    ('phi3:mini', '2.3 GB', 'Good quality — Microsoft Phi-3 Mini'),
    ('mistral:latest', '4.4 GB', 'Strong general — Mistral 7B'),
    ('tinyllama', '637 MB', 'Smallest — TinyLlama 1.1B'),
    ('qwen2.5:1.5b', '986 MB', 'Compact — Qwen 2.5 1.5B'),
]


def _get_modelfile_path():
    """Get the path to the EPL Modelfile."""
    import os

    return os.path.join(os.path.dirname(__file__), 'models', 'Modelfile')


def _read_modelfile():
    """Read the Modelfile content."""
    path = _get_modelfile_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def _parse_modelfile(content):
    """Parse a Modelfile into system prompt, messages, and parameters.

    Returns:
        Tuple of (system_prompt: str, messages: list, params: dict)
    """
    import re

    system_prompt = ''
    messages = []
    params = {}

    # Extract SYSTEM block (triple-quoted)
    system_match = re.search(r'SYSTEM\s+"""(.*?)"""', content, re.DOTALL)
    if system_match:
        system_prompt = system_match.group(1).strip()

    # Extract PARAMETER lines
    for match in re.finditer(r'PARAMETER\s+(\w+)\s+(.+)', content):
        key = match.group(1)
        value = match.group(2).strip().strip('"')
        # Convert to appropriate type
        try:
            if '.' in value:
                params[key] = float(value)
            else:
                params[key] = int(value)
        except ValueError:
            params[key] = value

    # Extract MESSAGE pairs
    message_pattern = re.compile(r'MESSAGE\s+(user|assistant)\s+(.*?)(?=\nMESSAGE\s|$)', re.DOTALL)
    for match in message_pattern.finditer(content):
        role = match.group(1)
        text = match.group(2).strip()
        messages.append({'role': role, 'content': text})

    return system_prompt, messages, params


def create_epl_model(base_model=None, model_name=None, verbose=True):
    """Create the custom EPL-Coder model in Ollama.

    Reads the Modelfile to extract the system prompt and conversation examples,
    then uses Ollama's API to create a derived model.

    Args:
        base_model: Base model to build from (default: qwen3:4b)
        model_name: Name for the created model (default: epl-coder)
        verbose: Print progress messages

    Returns:
        True if model was created successfully, False otherwise
    """
    name = model_name or EPL_MODEL_NAME
    base = base_model or 'qwen3:4b'

    if verbose:
        print(f"  Creating EPL model '{name}' from base '{base}'...")
        print('  This may take a few minutes on first run.\n')

    # Read and parse the Modelfile
    modelfile_content = _read_modelfile()
    if not modelfile_content:
        if verbose:
            print('  Error: Modelfile not found at epl/models/Modelfile')
        return False

    # Extract system prompt and messages from Modelfile
    system_prompt, messages, params = _parse_modelfile(modelfile_content)

    # Check if base model exists, pull if needed
    available = list_models()
    base_available = any(base in m for m in available)

    if not base_available:
        if verbose:
            print(f"  Base model '{base}' not found locally. Pulling...")
        pull_ok = pull_model(base)
        if not pull_ok:
            if verbose:
                print(f"  Error: Failed to pull '{base}'. Check your internet connection.")
            return False
        if verbose:
            print(f"  Base model '{base}' downloaded.\n")

    # Build API request — Ollama 0.14+ uses 'from', 'system', 'messages' keys
    if verbose:
        print('  Building model with EPL knowledge... ', end='', flush=True)

    api_data = {
        'name': name,
        'from': base,
        'system': system_prompt,
    }
    if params:
        api_data['params'] = params
    if messages:
        api_data['messages'] = messages

    url = f'{OLLAMA_HOST}/api/create'
    try:
        body = json.dumps(api_data).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        result = {'status': 'success'}
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode('utf-8')
            for line in raw.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if 'error' in obj:
                        result = obj
                        break
                except json.JSONDecodeError:
                    _debug_log.suppressed('ai:940:stream')
    except urllib.error.URLError as e:
        result = {'error': f'Connection failed: {e}'}
    except Exception as e:
        result = {'error': str(e)}

    if 'error' in result:
        if verbose:
            print(f'\n  Error: {result["error"]}')
        return False

    if verbose:
        print('Done!')
        print(f"\n  ✓ Model '{name}' created successfully!")
        print('  Use it with: python main.py ai "your question"')
        print('  Or in REPL:  python main.py ai')

    # Update the default model to use our trained model
    global DEFAULT_MODEL
    DEFAULT_MODEL = name
    return True


def delete_epl_model(model_name=None, verbose=True):
    """Delete the custom EPL model from Ollama."""
    name = model_name or EPL_MODEL_NAME
    data = {'name': name}
    result = _request('/api/delete', data, method='DELETE')
    if 'error' in result:
        if verbose:
            print(f'  Error: {result["error"]}')
        return False
    if verbose:
        print(f"  Model '{name}' deleted.")
    return True


def model_exists(model_name=None):
    """Check if the EPL model exists in Ollama."""
    name = model_name or EPL_MODEL_NAME
    models = list_models()
    return any(name in m for m in models)


def get_model_info(model_name=None):
    """Get information about a model."""
    name = model_name or EPL_MODEL_NAME
    data = {'name': name}
    result = _request('/api/show', data)
    if 'error' in result:
        return None
    return result


def ensure_epl_model(verbose=False):
    """Ensure the EPL model exists; create it if not.
    Returns the model name to use."""
    if model_exists():
        global DEFAULT_MODEL
        DEFAULT_MODEL = EPL_MODEL_NAME
        return EPL_MODEL_NAME
    # Model doesn't exist yet — check if Ollama is running
    if not is_available():
        return DEFAULT_MODEL  # fallback to whatever is configured
    if verbose:
        print('  EPL model not found. Creating it now...\n')
    ok = create_epl_model(verbose=verbose)
    if ok:
        return EPL_MODEL_NAME
    return DEFAULT_MODEL


def list_base_models():
    """List recommended base models for EPL."""
    return BASE_MODELS
