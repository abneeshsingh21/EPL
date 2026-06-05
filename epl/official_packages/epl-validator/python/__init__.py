"""
EPL Validator Package - Python Backend
Data validation: schema validation, type checking, regex patterns, sanitization.
"""

import html as _html
import json as _json
import queue as _queue
import re as _re
import threading as _threading
import uuid as _uuid

# ═══════════════════════════════════════════════════════════
#  ReDoS guard — user-supplied pattern execution
# ═══════════════════════════════════════════════════════════

_PATTERN_TIMEOUT_SECONDS = 1.0  # max time for any user-supplied regex match


def _safe_match(pattern: str, value: str) -> bool:
    """Match a user-supplied regex pattern against value with a timeout.

    Runs the match in a daemon thread.  If it does not complete within
    _PATTERN_TIMEOUT_SECONDS, the thread is abandoned and ValueError is raised.
    This prevents catastrophic backtracking (ReDoS) from hanging the process.

    Raises:
        ValueError: if the pattern times out or is invalid.
    """
    result_q: '_queue.Queue[object]' = _queue.Queue()

    def _run():
        try:
            result_q.put(bool(_re.match(pattern, value)))
        except _re.error as exc:
            result_q.put(exc)

    t = _threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_PATTERN_TIMEOUT_SECONDS)

    if t.is_alive():
        # Thread still running — catastrophic backtracking detected.
        raise ValueError(
            f"Pattern match timed out after {_PATTERN_TIMEOUT_SECONDS}s. "
            "The pattern may cause catastrophic backtracking (ReDoS). "
            "Simplify the pattern or reduce its input."
        )

    item = result_q.get_nowait()
    if isinstance(item, Exception):
        raise ValueError(f"Invalid regex pattern: {item}") from item
    return bool(item)

# ═══════════════════════════════════════════════════════════
#  Schema Creation & Validation
# ═══════════════════════════════════════════════════════════


def create_schema(rules=None):
    return {'_type': 'schema', 'fields': [], 'rules': rules or {}}


def add_field(schema, field_name, field_type, required=True):
    schema['fields'].append(
        {
            'name': field_name,
            'type': field_type,
            'required': bool(required),
        }
    )
    return schema


def add_field_range(schema, field_name, field_type, min_val, max_val, required=True):
    schema['fields'].append(
        {
            'name': field_name,
            'type': field_type,
            'required': bool(required),
            'min': min_val,
            'max': max_val,
        }
    )
    return schema


def add_string_field(schema, field_name, min_length, max_length, required=True):
    schema['fields'].append(
        {
            'name': field_name,
            'type': 'string',
            'required': bool(required),
            'min_length': int(min_length),
            'max_length': int(max_length),
        }
    )
    return schema


def add_pattern_field(schema, field_name, regex_pattern, required=True):
    schema['fields'].append(
        {
            'name': field_name,
            'type': 'pattern',
            'required': bool(required),
            'pattern': regex_pattern,
        }
    )
    return schema


def add_enum_field(schema, field_name, allowed_values, required=True):
    schema['fields'].append(
        {
            'name': field_name,
            'type': 'enum',
            'required': bool(required),
            'allowed': allowed_values if isinstance(allowed_values, list) else [allowed_values],
        }
    )
    return schema


def validate(schema, data):
    errors = []
    if not isinstance(data, dict):
        return {'valid': False, 'errors': ['Data must be a dictionary/map']}
    for field in schema['fields']:
        name = field['name']
        value = data.get(name)
        if value is None:
            if field['required']:
                errors.append(f"Field '{name}' is required")
            continue
        ftype = field['type']
        if ftype == 'string':
            if not isinstance(value, str):
                errors.append(f"Field '{name}' must be a string")
            elif 'min_length' in field and len(value) < field['min_length']:
                errors.append(f"Field '{name}' must be at least {field['min_length']} characters")
            elif 'max_length' in field and len(value) > field['max_length']:
                errors.append(f"Field '{name}' must be at most {field['max_length']} characters")
        elif ftype == 'number' or ftype == 'integer':
            if not isinstance(value, (int, float)):
                errors.append(f"Field '{name}' must be a number")
            elif 'min' in field and value < field['min']:
                errors.append(f"Field '{name}' must be >= {field['min']}")
            elif 'max' in field and value > field['max']:
                errors.append(f"Field '{name}' must be <= {field['max']}")
        elif ftype == 'boolean':
            if not isinstance(value, bool):
                errors.append(f"Field '{name}' must be a boolean")
        elif ftype == 'pattern':
            try:
                if not _safe_match(field['pattern'], str(value)):
                    errors.append(f"Field '{name}' does not match pattern")
            except ValueError as exc:
                errors.append(f"Field '{name}' pattern error: {exc}")
        elif ftype == 'enum':
            if value not in field['allowed']:
                errors.append(f"Field '{name}' must be one of: {field['allowed']}")
    return {'valid': len(errors) == 0, 'errors': errors}


def is_valid(schema, data):
    result = validate(schema, data)
    return result['valid']


def get_errors(result):
    return result.get('errors', [])


def get_first_error(result):
    errors = result.get('errors', [])
    return errors[0] if errors else None


# ═══════════════════════════════════════════════════════════
#  Type Checking
# ═══════════════════════════════════════════════════════════


def is_string(val):
    return isinstance(val, str)


def is_number(val):
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def is_integer(val):
    return isinstance(val, int) and not isinstance(val, bool)


def is_boolean(val):
    return isinstance(val, bool)


def is_array(val):
    return isinstance(val, list)


def is_null(val):
    return val is None


# ═══════════════════════════════════════════════════════════
#  Format Validation
# ═══════════════════════════════════════════════════════════

_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_URL_RE = _re.compile(r'^https?://[^\s/$.?#].[^\s]*$', _re.IGNORECASE)
_IP_RE = _re.compile(r'^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$')
_UUID_RE = _re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.IGNORECASE
)
_ALPHANUM_RE = _re.compile(r'^[a-zA-Z0-9]+$')


def is_email(val):
    return bool(_EMAIL_RE.match(str(val)))


def is_url(val):
    return bool(_URL_RE.match(str(val)))


def is_ip(val):
    return bool(_IP_RE.match(str(val)))


def is_uuid(val):
    return bool(_UUID_RE.match(str(val)))


def is_json(val):
    try:
        _json.loads(str(val))
        return True
    except (ValueError, TypeError):
        return False


def is_alphanumeric(val):
    return bool(_ALPHANUM_RE.match(str(val)))


def matches_pattern(val, pattern):
    """Match val against a user-supplied regex pattern.

    Protected against catastrophic backtracking (ReDoS): raises ValueError
    if the match does not complete within 1 second.
    """
    return _safe_match(pattern, str(val))


# ═══════════════════════════════════════════════════════════
#  Numeric Validation
# ═══════════════════════════════════════════════════════════


def is_positive(val):
    return isinstance(val, (int, float)) and val > 0


def is_negative(val):
    return isinstance(val, (int, float)) and val < 0


def is_in_range(val, min_val, max_val):
    return isinstance(val, (int, float)) and min_val <= val <= max_val


# ═══════════════════════════════════════════════════════════
#  Sanitization
# ═══════════════════════════════════════════════════════════


def sanitize_string(val):
    s = str(val)
    s = s.replace('\x00', '')
    return s.strip()


def sanitize_html(val):
    return _html.escape(str(val))


def sanitize_sql(val):
    """Escape dangerous SQL characters in a string value.

    WARNING: This is a last-resort defence-in-depth measure only.
    Always prefer parameterised queries / prepared statements over
    string interpolation.  This function does NOT make arbitrary SQL
    safe — it only escapes the most common injection characters.

    Characters escaped:
      \\    → \\\\   (must be first to avoid double-escaping)
      '     → ''     (SQL string delimiter)
      "     → \\"    (identifier/string delimiter in some dialects)
      `     → \\`    (MySQL identifier delimiter)
      ;     → \\;    (statement terminator)
      --    → \\-\\- (line comment)
      #     → \\#    (MySQL line comment)
      %     → \\%    (LIKE wildcard)
      _     → \\_    (LIKE single-char wildcard)
      NUL   → ''     (null byte)
      \\n   → \\n    (newline)
      \\r   → \\r    (carriage return)
    """
    s = str(val)
    s = s.replace('\\', '\\\\')   # must be first
    s = s.replace("'", "''")
    s = s.replace('"', '\\"')
    s = s.replace('`', '\\`')
    s = s.replace(';', '\\;')
    s = s.replace('--', '\\-\\-')
    s = s.replace('#', '\\#')
    s = s.replace('%', '\\%')
    s = s.replace('_', '\\_')
    s = s.replace('\x00', '')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    return s


def trim(val):
    return str(val).strip()


def truncate(val, max_len):
    s = str(val)
    max_len = int(max_len)
    if len(s) <= max_len:
        return s
    return s[:max_len]


def normalize_whitespace(val):
    return _re.sub(r'\s+', ' ', str(val)).strip()
