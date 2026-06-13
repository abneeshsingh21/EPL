"""
EPL HTTP Package - Python Backend
HTTP client operations powered by the requests library.
"""

import json as _json
import time as _time
import urllib.parse as _urlparse

try:
    import requests as _requests
except ImportError:
    raise ImportError(
        "epl-http requires the 'requests' library. Install with: pip install requests"
    )


# ═══════════════════════════════════════════════════════════
#  Basic HTTP Methods
# ═══════════════════════════════════════════════════════════


def _make_response(resp):
    return {
        'status': resp.status_code,
        'body': resp.text,
        'headers': dict(resp.headers),
        'ok': 200 <= resp.status_code < 300,
        '_json': None,
    }


def get(url):
    resp = _requests.get(url, timeout=30)
    return _make_response(resp)


def post(url, data):
    resp = _requests.post(url, json=data, timeout=30)
    return _make_response(resp)


def put(url, data):
    resp = _requests.put(url, json=data, timeout=30)
    return _make_response(resp)


def patch(url, data):
    resp = _requests.patch(url, json=data, timeout=30)
    return _make_response(resp)


def delete(url):
    resp = _requests.delete(url, timeout=30)
    return _make_response(resp)


# ═══════════════════════════════════════════════════════════
#  Advanced Requests
# ═══════════════════════════════════════════════════════════


def get_with_headers(url, headers):
    resp = _requests.get(url, headers=headers, timeout=30)
    return _make_response(resp)


def post_with_headers(url, data, headers):
    resp = _requests.post(url, json=data, headers=headers, timeout=30)
    return _make_response(resp)


def request(method, url, data, headers, timeout):
    kwargs = {'timeout': timeout or 30}
    if headers:
        kwargs['headers'] = headers
    if data:
        kwargs['json'] = data
    resp = _requests.request(method.upper(), url, **kwargs)
    return _make_response(resp)


def get_with_bearer(url, token):
    headers = {'Authorization': f'Bearer {token}'}
    resp = _requests.get(url, headers=headers, timeout=30)
    return _make_response(resp)


def get_with_basic_auth(url, username, password):
    resp = _requests.get(url, auth=(username, password), timeout=30)
    return _make_response(resp)


# ═══════════════════════════════════════════════════════════
#  Response Helpers
# ═══════════════════════════════════════════════════════════


def status_code(response):
    return response.get('status', 0)


def json(response):
    body = response.get('body', '')
    try:
        return _json.loads(body)
    except (ValueError, TypeError):
        return None


def get_text(response):
    return response.get('body', '')


def headers(response):
    return response.get('headers', {})


def is_ok(response):
    return response.get('ok', False)


# ═══════════════════════════════════════════════════════════
#  JSON Utilities
# ═══════════════════════════════════════════════════════════


def to_json(data):
    return _json.dumps(data)


def from_json(input_text):
    return _json.loads(input_text)


# ═══════════════════════════════════════════════════════════
#  File Operations
# ═══════════════════════════════════════════════════════════


def download(url, save_path):
    resp = _requests.get(url, stream=True, timeout=60)
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return {
        'status': resp.status_code,
        'path': save_path,
        'size': resp.headers.get('content-length', 0),
    }


def upload(url, file_path, field_name):
    with open(file_path, 'rb') as f:
        files = {field_name: f}
        resp = _requests.post(url, files=files, timeout=60)
    return _make_response(resp)


# ═══════════════════════════════════════════════════════════
#  Webhooks & Polling
# ═══════════════════════════════════════════════════════════


def send_webhook(url, event_name, payload):
    data = {'event': event_name, 'payload': payload, 'timestamp': _time.time()}
    resp = _requests.post(url, json=data, timeout=30)
    return _make_response(resp)


def poll(url, interval_seconds, max_attempts):
    for i in range(int(max_attempts)):
        resp = _requests.get(url, timeout=30)
        result = _make_response(resp)
        if result['ok']:
            return result
        if i < max_attempts - 1:
            _time.sleep(float(interval_seconds))
    return result


# ═══════════════════════════════════════════════════════════
#  URL Utilities
# ═══════════════════════════════════════════════════════════


def build_url(base, path, params):
    url = base.rstrip('/') + '/' + path.lstrip('/')
    if params:
        query = _urlparse.urlencode(params)
        url = url + '?' + query
    return url


def url_encode(input_text):
    return _urlparse.quote(str(input_text))


def url_decode(input_text):
    return _urlparse.unquote(str(input_text))
