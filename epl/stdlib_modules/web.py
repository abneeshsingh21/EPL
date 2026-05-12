"""
epl.stdlib_modules.web — Web server domain public API.

Provides a clean, importable interface to EPL's web functions
without copying implementations out of stdlib.py (safe facade pattern).

Usage in EPL:
    Import "web" from stdlib

Usage in Python tests:
    from epl.stdlib_modules.web import get_functions
"""

from __future__ import annotations

# Functions this module owns (from DOMAIN_MAP)
FUNCTIONS = frozenset(
    {
        'web_create',
        'web_route',
        'web_get',
        'web_post',
        'web_put',
        'web_delete',
        'web_start',
        'web_json',
        'web_html',
        'web_redirect',
        'web_static',
        'web_template',
        'web_request_data',
        'web_request_args',
        'web_request_method',
        'web_request_path',
        'web_request_header',
        'web_set_cors',
        'web_middleware',
        'web_error_handler',
        'web_stop',
        'web_api_create',
        'web_api_resource',
        'web_session_get',
        'web_session_set',
        'web_session_clear',
        'web_request_param',
        'web_cookie_get',
        'web_cookie_set',
        'web_test_client',
        'web_test_get',
        'web_test_post',
        'web_upload_config',
        'web_request_files',
        'web_send_file',
        'web_response',
        'web_url_for',
        # Auth
        'auth_hash_password',
        'auth_verify_password',
        'auth_jwt_create',
        'auth_jwt_verify',
        'auth_jwt_decode',
        'auth_generate_token',
        'auth_api_key_create',
        'auth_api_key_verify',
        'auth_bearer_token',
        'auth_basic_decode',
        # HTTP client
        'http_get',
        'http_post',
        'http_put',
        'http_delete',
        'http_request',
        'url_encode',
        'url_decode',
        'url_parse',
    }
)

# Human-readable documentation per function
DOCS: dict[str, str] = {
    'web_create': 'Create a new web application instance.',
    'web_route': 'Register a route handler (any method).',
    'web_get': 'Register a GET route handler.',
    'web_post': 'Register a POST route handler.',
    'web_put': 'Register a PUT route handler.',
    'web_delete': 'Register a DELETE route handler.',
    'web_start': 'Start the web server on a port.',
    'web_json': 'Return a JSON response from a handler.',
    'web_html': 'Return an HTML response from a handler.',
    'web_redirect': 'Redirect to another URL.',
    'web_set_cors': 'Enable CORS for an app or specific origins.',
    'web_middleware': 'Add middleware function to the app.',
    'web_session_get': 'Get a session variable by key.',
    'web_session_set': 'Set a session variable.',
    'web_session_clear': 'Clear all session variables.',
    'web_cookie_get': 'Get a cookie value by name.',
    'web_cookie_set': 'Set a cookie.',
    'web_request_data': 'Get the parsed request body (JSON or form).',
    'web_request_args': 'Get URL query string parameters.',
    'web_request_method': 'Get the HTTP method of the current request.',
    'web_request_path': 'Get the URL path of the current request.',
    'web_request_header': 'Get a request header by name.',
    'web_request_param': 'Get a route path parameter.',
    'web_request_files': 'Get uploaded files from the request.',
    'web_send_file': 'Stream a file as the response.',
    'web_response': 'Create a custom HTTP response.',
    'web_url_for': 'Generate a URL for a named route.',
    'web_error_handler': 'Register an error handler for HTTP status codes.',
    'web_stop': 'Stop the web server.',
    'web_test_client': 'Create a test client for the app.',
    'web_test_get': 'Make a GET request in a test context.',
    'web_test_post': 'Make a POST request in a test context.',
    'auth_hash_password': 'Hash a password securely with bcrypt/PBKDF2.',
    'auth_verify_password': 'Verify a plaintext password against a hash.',
    'auth_jwt_create': 'Create a signed JWT token.',
    'auth_jwt_verify': 'Verify and decode a JWT token.',
    'http_get': 'Make an HTTP GET request.',
    'http_post': 'Make an HTTP POST request.',
    'http_put': 'Make an HTTP PUT request.',
    'http_delete': 'Make an HTTP DELETE request.',
    'url_encode': 'URL-encode a string.',
    'url_decode': 'URL-decode a string.',
    'url_parse': 'Parse a URL into its components.',
}


def get_functions() -> frozenset[str]:
    """Return all function names owned by this module."""
    return FUNCTIONS


def describe(fn_name: str) -> str:
    """Return documentation for a function name."""
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
