"""
EPL AI Copilot
==============
Template/pattern-based English-to-EPL code generator.
Works completely offline — no API keys or external services required.
Usage:
    python main.py copilot                   Interactive mode
    python main.py copilot "description"     One-shot generation
    python main.py copilot --web             Web UI mode
"""

import re

from epl.syntax_reference import get_syntax_sections, get_syntax_text

# ── Public API ───────────────────────────────────────────

def generate_from_description(description: str) -> str:
    """Generate EPL code from an English description. Returns parse-checked EPL source."""
    return assist_request(description, mode='generate')['code']


def analyze_code(code: str, strict: bool = False) -> dict:
    """Analyze EPL source and return parse/type diagnostics."""
    from epl.errors import EPLError
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.type_checker import TypeChecker

    source = _normalize_code_block(code)
    if not source.strip():
        return {
            'ok': True,
            'syntax_ok': True,
            'diagnostics': [],
            'statement_count': 0,
        }

    try:
        tokens = Lexer(source).tokenize()
    except EPLError as exc:
        return {
            'ok': False,
            'syntax_ok': False,
            'diagnostics': [_diagnostic_from_error(exc, source='lexer')],
            'statement_count': 0,
        }

    parser = Parser(tokens)
    program, errors = parser.parse_with_recovery()
    diagnostics = [_diagnostic_from_error(err, source='parser') for err in errors]
    syntax_ok = not errors

    if syntax_ok:
        checker = TypeChecker(strict=strict)
        checker.check(program)
        diagnostics.extend(_normalize_type_diagnostics(checker.to_lsp_diagnostics()))

    ok = syntax_ok and not any(diag['level'] == 'error' for diag in diagnostics)
    return {
        'ok': ok,
        'syntax_ok': syntax_ok,
        'diagnostics': diagnostics,
        'statement_count': len(getattr(program, 'statements', [])),
    }


def assist_request(message: str, current_code: str = "", mode: str = "auto") -> dict:
    """Generate, explain, fix, or improve EPL code with syntax-aware diagnostics."""
    prompt = message.strip()
    code = _normalize_code_block(current_code)
    resolved_mode = _detect_assist_mode(prompt, code, mode)

    if resolved_mode == 'generate' or (not code and resolved_mode in ('fix', 'improve', 'explain')):
        candidate = _generate_candidate(prompt)
        final_code, analysis, repair_notes = _validate_generated_code(candidate, prompt)
        reply = _build_generation_reply(prompt, analysis, repair_notes)
        return {
            'mode': 'generate',
            'reply': reply,
            'code': final_code,
            'syntax_ok': analysis['syntax_ok'],
            'diagnostics': analysis['diagnostics'],
            'repair_notes': repair_notes,
            'syntax_sections': _select_syntax_sections(prompt, final_code, analysis['diagnostics']),
        }

    if resolved_mode == 'fix':
        repaired, repair_notes = _repair_common_syntax_mistakes(code)
        repaired_analysis = analyze_code(repaired)
        if repaired != code and repaired_analysis['syntax_ok']:
            reply = _build_fix_reply(repaired_analysis, repair_notes, auto_fixed=True)
            return {
                'mode': 'fix',
                'reply': reply,
                'code': repaired,
                'syntax_ok': repaired_analysis['syntax_ok'],
                'diagnostics': repaired_analysis['diagnostics'],
                'repair_notes': repair_notes,
                'syntax_sections': _select_syntax_sections(prompt, repaired, repaired_analysis['diagnostics']),
            }

        analysis = analyze_code(code)
        reply = _build_fix_reply(analysis, repair_notes, auto_fixed=False)
        return {
            'mode': 'fix',
            'reply': reply,
            'code': repaired if repaired != code else code,
            'syntax_ok': analysis['syntax_ok'],
            'diagnostics': analysis['diagnostics'],
            'repair_notes': repair_notes,
            'syntax_sections': _select_syntax_sections(prompt, code, analysis['diagnostics']),
        }

    if resolved_mode == 'improve':
        improved, repair_notes = _repair_common_syntax_mistakes(code)
        analysis = analyze_code(improved)
        reply = _build_improve_reply(analysis, repair_notes)
        return {
            'mode': 'improve',
            'reply': reply,
            'code': improved,
            'syntax_ok': analysis['syntax_ok'],
            'diagnostics': analysis['diagnostics'],
            'repair_notes': repair_notes,
            'syntax_sections': _select_syntax_sections(prompt, improved, analysis['diagnostics']),
        }

    analysis = analyze_code(code)
    reply = _build_explain_reply(code, analysis)
    return {
        'mode': 'explain',
        'reply': reply,
        'code': code,
        'syntax_ok': analysis['syntax_ok'],
        'diagnostics': analysis['diagnostics'],
        'repair_notes': [],
        'syntax_sections': _select_syntax_sections(prompt, code, analysis['diagnostics']),
    }


def _generate_candidate(description: str) -> str:
    desc = description.strip().lower()
    for matcher in _MATCHERS:
        result = matcher(desc, description.strip())
        if result:
            return result
    return _fallback(desc, description.strip())


def _normalize_code_block(code: str) -> str:
    text = code.strip()
    fence = re.search(r'```(?:epl)?\s*\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _detect_assist_mode(message: str, code: str, mode: str) -> str:
    if mode and mode != 'auto':
        return mode
    lowered = message.lower()
    if code and re.search(r'\b(fix|debug|repair|error|broken|syntax)\b', lowered):
        return 'fix'
    if code and re.search(r'\b(explain|what does|how does|describe)\b', lowered):
        return 'explain'
    if code and re.search(r'\b(improve|refactor|optimize|cleanup|clean up)\b', lowered):
        return 'improve'
    return 'generate'


def _validate_generated_code(code: str, description: str):
    candidate = _normalize_code_block(code)
    analysis = analyze_code(candidate)
    if analysis['syntax_ok']:
        return candidate, analysis, []

    repaired, repair_notes = _repair_common_syntax_mistakes(candidate)
    if repaired != candidate:
        repaired_analysis = analyze_code(repaired)
        if repaired_analysis['syntax_ok']:
            return repaired, repaired_analysis, repair_notes

    safe_fallback = _fallback(description.lower(), description.strip())
    fallback_analysis = analyze_code(safe_fallback)
    notes = repair_notes + ['Fell back to a safe starter because the first draft did not parse cleanly.']
    return safe_fallback, fallback_analysis, notes


def _repair_common_syntax_mistakes(code: str):
    repaired = _normalize_code_block(code)
    notes = []
    original = repaired

    if repaired.startswith('//'):
        repaired = '\n'.join(
            (re.sub(r'^(\s*)//\s*', r'\1Note: ', line) if re.match(r'^\s*//', line) else line)
            for line in repaired.splitlines()
        )
        notes.append('Converted // comments into EPL Note: comments.')

    if re.search(r'^\s*Else If\b', repaired, re.IGNORECASE | re.MULTILINE):
        repaired = re.sub(r'^(\s*)Else If\b', r'\1Otherwise If', repaired, flags=re.IGNORECASE | re.MULTILINE)
        notes.append('Replaced Else If with EPL Otherwise If.')

    if re.search(r'^\s*Else\b', repaired, re.IGNORECASE | re.MULTILINE):
        repaired = re.sub(r'^(\s*)Else\b', r'\1Otherwise', repaired, flags=re.IGNORECASE | re.MULTILINE)
        notes.append('Replaced Else with EPL Otherwise.')

    if ';' in repaired:
        cleaned_lines = []
        changed = False
        for line in repaired.splitlines():
            stripped = line.rstrip()
            if stripped.endswith(';'):
                cleaned_lines.append(stripped[:-1])
                changed = True
            else:
                cleaned_lines.append(line)
        if changed:
            repaired = '\n'.join(cleaned_lines)
            notes.append('Removed trailing semicolons.')

    if repaired != original:
        repaired = repaired.strip() + '\n'

    return repaired, notes


def _diagnostic_from_error(exc, source='parser'):
    payload = exc.to_dict() if hasattr(exc, 'to_dict') else {}
    return {
        'level': 'error',
        'source': source,
        'message': payload.get('message', str(exc)),
        'line': payload.get('line'),
        'code': payload.get('error_code') or payload.get('code', ''),
    }


def _normalize_type_diagnostics(items):
    severity_map = {1: 'error', 2: 'warning', 3: 'info', 4: 'hint'}
    normalized = []
    for item in items:
        start = item.get('range', {}).get('start', {})
        normalized.append({
            'level': severity_map.get(item.get('severity', 2), 'warning'),
            'source': item.get('source', 'typecheck'),
            'message': item.get('message', ''),
            'line': start.get('line', 0) + 1,
            'code': item.get('code', ''),
        })
    return normalized


def _summarize_diagnostics(diagnostics, limit=3):
    if not diagnostics:
        return 'No syntax issues found.'
    parts = []
    for diag in diagnostics[:limit]:
        line = f"line {diag['line']}" if diag.get('line') else 'unknown line'
        parts.append(f"{line}: {diag['message']}")
    if len(diagnostics) > limit:
        parts.append(f"... and {len(diagnostics) - limit} more issue(s)")
    return '; '.join(parts)


def _build_generation_reply(prompt: str, analysis: dict, repair_notes):
    subject = _infer_subject(prompt)
    status = 'The starter parses cleanly.' if analysis['syntax_ok'] else 'The starter still needs manual review.'
    details = _summarize_diagnostics(analysis['diagnostics'], limit=2)
    extra = f" Repairs applied: {' '.join(repair_notes)}" if repair_notes else ""
    return f"Generated a syntax-aware EPL {subject} starter. {status} Diagnostics: {details}.{extra}".strip()


def _build_fix_reply(analysis: dict, repair_notes, auto_fixed: bool):
    if auto_fixed:
        extra = f" Applied: {' '.join(repair_notes)}" if repair_notes else ""
        return f"I repaired common EPL syntax issues and revalidated the code. Diagnostics: {_summarize_diagnostics(analysis['diagnostics'], limit=2)}.{extra}".strip()
    guidance = _summarize_diagnostics(analysis['diagnostics'], limit=3)
    syntax_text = get_syntax_text()
    return (
        f"I could not safely auto-rewrite everything, but I found these issues: {guidance}. "
        f"Use parser-supported forms such as Note: comments, Otherwise instead of Else, "
        f"Function name takes arg, and Create WebApp called myApp for web starters.\n\n"
        f"{syntax_text}"
    )


def _build_explain_reply(code: str, analysis: dict):
    features = []
    lowered = code.lower()
    if 'create webapp' in lowered:
        features.append('a native WebApp')
    if re.search(r'^\s*(define\s+function|function)\b', code, re.IGNORECASE | re.MULTILINE):
        features.append('functions')
    if re.search(r'^\s*class\b', code, re.IGNORECASE | re.MULTILINE):
        features.append('classes')
    if re.search(r'^\s*(for|while|repeat)\b', code, re.IGNORECASE | re.MULTILINE):
        features.append('control-flow loops')
    if 'use python ' in lowered:
        features.append('the Python bridge')
    if not features:
        features.append('core EPL statements')
    return (
        f"This code uses {', '.join(features)}. "
        f"Syntax diagnostics: {_summarize_diagnostics(analysis['diagnostics'], limit=3)}"
    )


def _build_improve_reply(analysis: dict, repair_notes):
    if analysis['syntax_ok']:
        base = "The code already parses. Keep using parser-safe forms like Note:, Otherwise, Map with, and Route ... shows/responds with."
    else:
        base = f"The code needs syntax cleanup first. Diagnostics: {_summarize_diagnostics(analysis['diagnostics'], limit=3)}"
    if repair_notes:
        base += f" Applied: {' '.join(repair_notes)}"
    return base


def _infer_subject(prompt: str) -> str:
    lowered = prompt.lower()
    if re.search(r'\b(chatbot|assistant|ai bot|chat bot)\b', lowered):
        return 'chatbot'
    if re.search(r'\b(auth|login|register|signup|signin)\b', lowered):
        return 'auth'
    if re.search(r'\b(frontend|landing page|dashboard|ui|ux)\b', lowered):
        return 'frontend'
    if re.search(r'\b(api|backend|rest|server)\b', lowered):
        return 'backend'
    if re.search(r'\b(web app|website|fullstack)\b', lowered):
        return 'web'
    return 'code'


def _select_syntax_sections(message: str, code: str, diagnostics):
    text = ' '.join(
        [message or '', code or ''] + [diag.get('message', '') for diag in diagnostics or []]
    ).lower()
    section_keywords = {
        'web': ['webapp', 'route', '/api', 'send json', 'request_data', 'fetch '],
        'functions': ['function', 'return', 'call ', '(', 'lambda', '->'],
        'control_flow': ['otherwise', 'else', 'while', 'repeat', 'for each', 'for ', 'match', 'when'],
        'collections': ['map with', '[', ']', 'keys(', 'values(', 'items'],
        'imports': ['import ', 'use python', 'json', 'module'],
        'oop': ['class', 'new ', 'this', 'super', '.'],
        'output_input': ['say ', 'display ', 'ask ', 'input '],
        'gui': ['window', 'label', 'textbox', 'button', 'column', 'row'],
        'error_handling': ['try', 'catch', 'throw', 'assert', 'error', 'exception'],
        'file_io': ['write ', 'read file', 'append ', 'file '],
        'enums_ternary': ['enum', 'otherwise', 'ternary', 'if ', 'lambda'],
        'misc': ['wait', 'exit', 'length(', 'type_of(', 'to_text('],
    }
    scored = []
    for section in get_syntax_sections():
        keywords = section_keywords.get(section['id'], [])
        score = sum(1 for keyword in keywords if keyword in text)
        scored.append((score, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = [section for score, section in scored if score > 0][:3]
    if not chosen:
        ids = {'variables', 'functions', 'control_flow'}
        chosen = [section for section in get_syntax_sections() if section['id'] in ids]
    return chosen


def start_copilot_web(port: int = 8095, open_browser: bool = True):
    """Start the EPL Copilot web interface."""
    import json
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class CopilotHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/', '/index.html'):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(_COPILOT_HTML.encode('utf-8'))
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/api/generate':
                length = int(self.headers.get('Content-Length', 0))
                if length > 100_000:
                    self._json(400, {'error': 'Too large'})
                    return
                try:
                    data = json.loads(self.rfile.read(length))
                except json.JSONDecodeError:
                    self._json(400, {'error': 'Invalid JSON'})
                    return
                desc = data.get('description', '')
                if not desc.strip():
                    self._json(400, {'error': 'No description provided'})
                    return
                code = generate_from_description(desc)
                self._json(200, {'code': code})
            else:
                self.send_error(404)

        def _json(self, status, data):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))

        def log_message(self, *a):
            pass

    server = HTTPServer(('127.0.0.1', port), CopilotHandler)
    print(f"  EPL Copilot running at http://127.0.0.1:{port}")
    print("  Press Ctrl+C to stop")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{port}')
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Copilot stopped.")
        server.server_close()


def run_copilot_interactive():
    """Run the copilot in interactive CLI mode."""
    print("  EPL AI Copilot (offline, template-based)")
    print("  Describe what you want in English. Type 'quit' to exit.\n")
    while True:
        try:
            desc = input("  Describe: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break
        if desc.lower() in ('quit', 'exit', 'q'):
            break
        if not desc:
            continue
        code = generate_from_description(desc)
        print(f"\n{'─' * 50}")
        print(code)
        print(f"{'─' * 50}\n")


# ── Pattern Matchers ─────────────────────────────────────

def _match_hello(desc, orig):
    if re.search(r'hello\s*world|greet|welcome|say\s+hi', desc):
        return '''display "Hello, World!"
display "Welcome to EPL!"'''
    return None

def _match_calculator(desc, orig):
    if re.search(r'calculator|calc|arithmetic|basic\s*math', desc):
        return '''display "=== EPL Calculator ==="

function add takes a and b
    return a + b
end

function subtract takes a and b
    return a - b
end

function multiply takes a and b
    return a * b
end

function divide takes a and b
    if b == 0 then
        display "Error: Cannot divide by zero"
        return 0
    end
    return a / b
end

display "10 + 5 = " + add(10, 5)
display "10 - 5 = " + subtract(10, 5)
display "10 * 5 = " + multiply(10, 5)
display "10 / 5 = " + divide(10, 5)'''
    return None

def _match_fibonacci(desc, orig):
    if re.search(r'fibonacci|fib\b', desc):
        n = _extract_number(desc, 10)
        return f'''function fibonacci takes n
    if n <= 1 then
        return n
    end
    return fibonacci(n - 1) + fibonacci(n - 2)
end

display "Fibonacci sequence:"
for i from 0 to {n}
    display "fib(" + i + ") = " + fibonacci(i)
end'''
    return None

def _match_factorial(desc, orig):
    if re.search(r'factorial', desc):
        n = _extract_number(desc, 10)
        return f'''function factorial takes n
    if n <= 1 then
        return 1
    end
    return n * factorial(n - 1)
end

for i from 1 to {n}
    display i + "! = " + factorial(i)
end'''
    return None

def _match_fizzbuzz(desc, orig):
    if re.search(r'fizz\s*buzz', desc):
        n = _extract_number(desc, 100)
        return f'''for i from 1 to {n}
    if i % 15 == 0 then
        display "FizzBuzz"
    otherwise if i % 3 == 0 then
        display "Fizz"
    otherwise if i % 5 == 0 then
        display "Buzz"
    otherwise
        display i
    end
end'''
    return None

def _match_sort(desc, orig):
    if re.search(r'sort|bubble\s*sort|sorting', desc):
        return '''function bubbleSort takes arr
    set n to length(arr)
    for i from 0 to n - 1
        for j from 0 to n - i - 2
            if arr[j] > arr[j + 1] then
                set temp to arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
            end
        end
    end
    return arr
end

set numbers to [64, 34, 25, 12, 22, 11, 90]
display "Before: " + numbers
set sorted to bubbleSort(numbers)
display "After: " + sorted'''
    return None

def _match_search(desc, orig):
    if re.search(r'search|find|binary\s*search|linear\s*search', desc):
        return '''function linearSearch takes arr and target
    for i from 0 to length(arr) - 1
        if arr[i] == target then
            return i
        end
    end
    return -1
end

function binarySearch takes arr and target
    set low to 0
    set high to length(arr) - 1
    while low <= high
        set mid to (low + high) / 2
        if arr[mid] == target then
            return mid
        otherwise if arr[mid] < target then
            set low to mid + 1
        otherwise
            set high to mid - 1
        end
    end
    return -1
end

set data to [2, 5, 8, 12, 16, 23, 38, 45, 67, 91]
display "Data: " + data
display "Linear search for 23: index " + linearSearch(data, 23)
display "Binary search for 23: index " + binarySearch(data, 23)'''
    return None

def _match_guess_game(desc, orig):
    if re.search(r'guess|guessing\s*game|number\s*game', desc):
        return '''display "=== Number Guessing Game ==="
set secret to random(1, 100)
set attempts to 0
set found to false

while not found
    ask "Guess a number (1-100): " store in guess
    set guess to to_integer(guess)
    set attempts to attempts + 1

    if guess == secret then
        display "Correct! You got it in " + attempts + " attempts!"
        set found to true
    otherwise if guess < secret then
        display "Too low! Try again."
    otherwise
        display "Too high! Try again."
    end
end'''
    return None

def _match_list_ops(desc, orig):
    if re.search(r'list|array|collection|stack|queue', desc):
        return '''display "=== List Operations ==="

set fruits to ["apple", "banana", "cherry", "date"]
display "Fruits: " + fruits
display "First: " + fruits[0]
display "Length: " + length(fruits)

display "\\nIterating:"
for each fruit in fruits
    display "  - " + fruit
end

display "\\nAdding 'elderberry'..."
add "elderberry" to fruits
display "Updated: " + fruits

display "\\nSorted:"
set sorted to sorted(fruits)
display sorted'''
    return None

def _match_class(desc, orig):
    if re.search(r'\bclass\b|\bobject\b|\boop\b|\banimal\b|\bperson\b|\bstudent\b|\bcar\b', desc):
        name = 'Animal'
        m = re.search(r'(animal|person|student|car|dog|cat|vehicle|product|user|player)', desc)
        if m:
            name = m.group(1).capitalize()

        props = {
            'Animal': ('name', '"Unknown"', 'sound', '"..."', 'speak', 'name + " says " + sound'),
            'Person': ('name', '"John"', 'age', '0', 'greet', '"Hello, I am " + name'),
            'Student': ('name', '"Alice"', 'grade', '"A"', 'info', 'name + " - Grade: " + grade'),
            'Car': ('brand', '"Toyota"', 'speed', '0', 'describe', 'brand + " at " + speed + " mph"'),
            'Dog': ('name', '"Rex"', 'breed', '"Unknown"', 'bark', 'name + " says Woof!"'),
            'Cat': ('name', '"Whiskers"', 'color', '"gray"', 'meow', 'name + " says Meow!"'),
            'Player': ('name', '"Player1"', 'score', '0', 'status', 'name + ": " + score + " pts"'),
        }
        p = props.get(name, ('name', '"Unknown"', 'value', '0', 'info', 'name + ": " + value'))
        return f'''class {name}
    set {p[0]} to {p[1]}
    set {p[2]} to {p[3]}

    function {p[4]}
        display {p[5]}
    end
end

set obj to new {name}
obj.{p[0]} = "Example"
obj.{p[4]}()'''
    return None

def _match_loop(desc, orig):
    if re.search(r'loop|count|iterate|repeat|for\b|while\b', desc):
        n = _extract_number(desc, 10)
        return f'''display "Counting from 1 to {n}:"
for i from 1 to {n}
    display "Number: " + i
end

display "\\nUsing repeat:"
set counter to 0
repeat {n} times
    set counter to counter + 1
    display "Step " + counter
end

display "\\nUsing while:"
set x to {n}
while x > 0
    display "Countdown: " + x
    set x to x - 1
end
display "Done!"'''
    return None

def _match_string(desc, orig):
    if re.search(r'string|text|reverse\s*(a\s+)?string|palindrome|char', desc):
        return '''function reverseString takes s
    set result to ""
    set i to length(s) - 1
    while i >= 0
        set result to result + s[i]
        set i to i - 1
    end
    return result
end

function isPalindrome takes s
    return s == reverseString(s)
end

set word to "racecar"
display "Original: " + word
display "Reversed: " + reverseString(word)
display "Is palindrome: " + isPalindrome(word)

set word2 to "hello"
display "\\n" + word2 + " reversed: " + reverseString(word2)
display "Is palindrome: " + isPalindrome(word2)'''
    return None

def _match_prime(desc, orig):
    if re.search(r'prime|primes|sieve', desc):
        n = _extract_number(desc, 50)
        return f'''function isPrime takes n
    if n < 2 then
        return false
    end
    set i to 2
    while i * i <= n
        if n % i == 0 then
            return false
        end
        set i to i + 1
    end
    return true
end

display "Prime numbers up to {n}:"
for i from 2 to {n}
    if isPrime(i) then
        display i
    end
end'''
    return None

def _match_error_handling(desc, orig):
    if re.search(r'try|catch|error|exception|handle', desc):
        return '''display "=== Error Handling ==="

try
    display "Attempting division..."
    set result to 10 / 0
catch error
    display "Caught error: " + error
end

try
    display "\\nAccessing invalid index..."
    set items to [1, 2, 3]
    set val to items[99]
catch error
    display "Caught error: " + error
end

display "\\nProgram continues safely!"'''
    return None

def _match_dictionary(desc, orig):
    if re.search(r'dict|map|hash|key.*value|phone\s*book|contacts', desc):
        return '''display "=== Dictionary Operations ==="

set person to map with name = "Alice" and age = 30 and city = "NYC"
display "Person: " + person
display "Name: " + person.name
display "Age: " + person.age

person.email = "alice@example.com"
display "Updated: " + person

display "\\nAll keys:"
for each key in keys(person)
    display "  " + key
end'''
    return None

def _match_file(desc, orig):
    if re.search(r'file|read|write|save|load|io\b', desc):
        return '''display "=== File Operations ==="

set content to "Hello from EPL!\\nThis is line 2.\\nThis is line 3."
write content to file "output.txt"
display "Wrote to output.txt"

set data to read file "output.txt"
display "Read back: " + data

append "\\nAppended line!" to file "output.txt"
display "Appended to file"

set updated to read file "output.txt"
display "Updated content: " + updated'''
    return None

def _match_math_ops(desc, orig):
    if re.search(r'\bmath\b|square\s*root|\bpower\b|\babs\b|\blog\b|\bpi\b|trigonometry', desc):
        return '''display "=== Math Operations ==="

display "Square root of 144: " + sqrt(144)
display "Power: 2^10 = " + power(2, 10)
display "Absolute: |-42| = " + absolute(-42)
display "Round 3.7: " + round(3.7)
display "Min(5,3): " + min(5, 3)
display "Max(5,3): " + max(5, 3)

display "\\nRandom 1-100: " + random(1, 100)'''
    return None

def _match_pattern(desc, orig):
    if re.search(r'pattern|star|triangle|pyramid|diamond', desc):
        n = _extract_number(desc, 5)
        return f'''display "=== Star Patterns ==="

display "Right Triangle:"
for i from 1 to {n}
    set row to ""
    repeat i times
        set row to row + "* "
    end
    display row
end

display "\\nPyramid:"
for i from 1 to {n}
    set spaces to ""
    set stars to ""
    repeat {n} - i times
        set spaces to spaces + " "
    end
    repeat 2 * i - 1 times
        set stars to stars + "*"
    end
    display spaces + stars
end'''
    return None

def _match_todo(desc, orig):
    if re.search(r'todo|task|to.do|checklist', desc):
        return '''display "=== Todo List ==="

set todos to []
set running to true

while running
    display "\\n1. Add task"
    display "2. View tasks"
    display "3. Complete task"
    display "4. Quit"
    ask "Choose (1-4): " store in choice

    if choice == "1" then
        ask "Enter task: " store in task
        add task to todos
        display "Added: " + task
    otherwise if choice == "2" then
        if length(todos) == 0 then
            display "No tasks!"
        otherwise
            for i from 0 to length(todos) - 1
                display (i + 1) + ". " + todos[i]
            end
        end
    otherwise if choice == "3" then
        ask "Task number to complete: " store in num
        set num to to_number(num) - 1
        display "Completed: " + todos[num]
        call todos.remove(todos[num])
    otherwise if choice == "4" then
        set running to false
        display "Goodbye!"
    end
end'''
    return None

def _match_frontend(desc, orig):
    if re.search(r'frontend|landing\s*page|dashboard|creative\s*ui|creative\s*ux|hero\s*section', desc):
        return '''Create WebApp called studioApp

Route "/" shows
    Create hero_title = "Neon Studio"
    Create hero_copy = "Build bold interfaces with real EPL syntax."
    Page "$hero_title"
        Heading "$hero_title"
        SubHeading "Creative frontend starter"
        Text "$hero_copy"
        Link "View roadmap" to "/roadmap"
    End
End

Route "/roadmap" shows
    Page "Roadmap"
        Heading "Roadmap"
        Text "Design. Build. Launch."
        Link "Back home" to "/"
    End
End

Route "/api/theme" responds with
    Send json Map with accent = "#58a6ff" and mode = "creative"
End

Start studioApp on port 8080'''
    return None

def _match_auth(desc, orig):
    if re.search(r'auth|login|register|signup|sign\s*in|sign\s*up', desc):
        return '''Import "epl-db"

Create db equal to open(":memory:")
Call create_table(db, "users", Map with id = "INTEGER PRIMARY KEY AUTOINCREMENT" and username = "TEXT UNIQUE NOT NULL" and password_hash = "TEXT NOT NULL")

Create WebApp called authApp

Route "/" shows
    Page "Auth Starter"
        Heading "Auth starter"
        Text "Post username and password to the JSON routes below."
        Link "Health API" to "/api/health"
    End
End

Route "/api/health" responds with
    Send json Map with status = "ok" and service = "auth"
End

Route "/api/register" responds with
    Create username equal to request_data.get("username")
    Create password equal to request_data.get("password")
    Create response equal to Map with ok = False and error = "Username and password are required"
    If username != nothing And password != nothing Then
        If username != "" And password != "" Then
            Try
                Create password_hash equal to auth_hash_password(password)
                Call execute_params(db, "INSERT INTO users (username, password_hash) VALUES (?, ?)", [username, password_hash])
                Create response equal to Map with ok = True and user = username
            Catch error
                Create response equal to Map with ok = False and error = "Username already exists"
            End
        End
    End
    Send json response
End

Route "/api/login" responds with
    Create username equal to request_data.get("username")
    Create password equal to request_data.get("password")
    Create account equal to query_one_params(db, "SELECT username, password_hash FROM users WHERE username = ?", [username])
    Create response equal to Map with ok = False and error = "Invalid credentials"
    If account != nothing And auth_verify_password(password, account.password_hash) Then
        Create response equal to Map with ok = True and user = account.username and token = auth_generate_token(32)
    End
    Send json response
End

Start authApp on port 8080'''
    return None

def _match_chatbot(desc, orig):
    if re.search(r'chatbot|chat\s*bot|ai\s*assistant|assistant\s*api|chat\s*api', desc):
        return '''Use python "epl.ai" as ai

Create WebApp called chatApp

Route "/" shows
    Page "Chatbot Starter"
        Heading "EPL chatbot starter"
        Text "Send JSON to /api/chat with a message field."
        Link "Health API" to "/api/health"
    End
End

Route "/api/health" responds with
    Send json Map with status = "ok" and service = "chatbot"
End

Route "/api/chat" responds with
    Create message equal to request_data.get("message")
    Create reply equal to Map with ok = False and mode = "starter" and reply = "Message is required"
    If message != nothing And message != "" Then
        Try
            Create messages equal to [Map with role = "system" and content = "You are a helpful EPL assistant.", Map with role = "user" and content = message]
            Create answer equal to ai.chat(messages)
            Create reply equal to Map with ok = True and mode = "ai" and reply = answer
        Catch error
            Create reply equal to Map with ok = False and mode = "fallback" and reply = "AI backend unavailable" and detail = to_text(error)
        End
    End
    Send json reply
End

Start chatApp on port 8080'''
    return None

def _match_api_web(desc, orig):
    if re.search(r'api|web\s*app|server|route|http|rest', desc):
        return '''Create WebApp called myApp

Route "/" shows
    Page "Welcome"
        Heading "Welcome to EPL!"
        Text "This is a web app built with EPL."
        Link "About" to "/about"
    End
End

Route "/about" shows
    Page "About"
        Heading "About"
        Text "Built with EPL"
        Link "Home" to "/"
    End
End

Route "/api/hello" responds with
    Send json Map with message = "Hello from EPL API!" and status = "ok"
End

Start myApp on port 8080'''
    return None

def _match_timer(desc, orig):
    if re.search(r'timer|stopwatch|countdown|clock', desc):
        n = _extract_number(desc, 10)
        return f'''display "=== Countdown Timer ==="
set secs to {n}

while secs > 0
    display secs + " seconds remaining..."
    wait 1 seconds
    set secs to secs - 1
end

display "Time is up!"'''
    return None


# ── Helpers ──────────────────────────────────────────────

def _extract_number(desc, default):
    """Extract a number from description, or return default."""
    m = re.search(r'\b(\d+)\b', desc)
    return int(m.group(1)) if m else default


def _fallback(desc, orig):
    """Generate a best-effort template when no specific pattern matches."""
    # Extract potential variable names from description
    words = re.findall(r'\b[a-z]+\b', desc)
    nouns = [w for w in words if w not in {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
        'that', 'this', 'with', 'from', 'for', 'and', 'or', 'but',
        'in', 'on', 'at', 'to', 'of', 'it', 'do', 'does', 'did',
        'make', 'create', 'write', 'build', 'program', 'code',
        'generate', 'me', 'my', 'i', 'can', 'you', 'should', 'would',
        'could', 'will', 'shall', 'may', 'might', 'have', 'has', 'had',
    }]
    topic = nouns[0] if nouns else 'program'

    return f'''Note: Generated from: "{orig}"
Note: EPL AI Copilot - customize this template as needed

display "=== {topic.capitalize()} Program ==="

Note: Add your variables
set {topic} to "default"
display "{topic.capitalize()}: " + {topic}

Note: Add your logic here
function process{topic.capitalize()} takes value
    display "Processing: " + value
    return value
end

set result to process{topic.capitalize()}({topic})
display "Result: " + result
display "Done!"'''


# All pattern matchers in priority order
_MATCHERS = [
    _match_hello,
    _match_calculator,
    _match_fibonacci,
    _match_factorial,
    _match_fizzbuzz,
    _match_sort,
    _match_search,
    _match_guess_game,
    _match_prime,
    _match_string,
    _match_pattern,
    _match_todo,
    _match_frontend,
    _match_auth,
    _match_chatbot,
    _match_class,
    _match_timer,
    _match_loop,
    _match_list_ops,
    _match_dictionary,
    _match_file,
    _match_api_web,
    _match_math_ops,
    _match_error_handling,
]


# ── Web UI Template ──────────────────────────────────────

_COPILOT_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPL AI Copilot</title>
<style>
:root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --purple: #bc8cff;
    --font-mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: var(--font-sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
}

header {
    padding: 30px 20px 10px;
    text-align: center;
}
header h1 { font-size: 2em; color: var(--accent); margin-bottom: 6px; }
header p { color: var(--text-dim); font-size: 0.95em; }

.container {
    width: 100%;
    max-width: 900px;
    padding: 20px;
}

/* Input area */
.input-area {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}
.input-area label {
    display: block;
    font-size: 0.85em;
    color: var(--text-dim);
    margin-bottom: 8px;
}
.input-row {
    display: flex;
    gap: 10px;
}
.input-row input {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    color: var(--text);
    font-size: 1em;
    outline: none;
}
.input-row input:focus { border-color: var(--accent); }
.input-row input::placeholder { color: var(--text-dim); }
.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    background: var(--accent);
    color: #fff;
    font-size: 0.95em;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
}
.btn:hover { background: #79c0ff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Suggestions */
.suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
}
.suggestion {
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: 16px;
    font-size: 0.78em;
    color: var(--text-dim);
    cursor: pointer;
    transition: all 0.15s;
}
.suggestion:hover { border-color: var(--accent); color: var(--accent); }

/* Output */
.output-area {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    display: none;
}
.output-header {
    padding: 10px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
}
.output-header span { font-size: 0.85em; color: var(--green); }
.copy-btn {
    padding: 4px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    color: var(--text-dim);
    font-size: 0.8em;
    cursor: pointer;
}
.copy-btn:hover { color: var(--accent); border-color: var(--accent); }
#codeOutput {
    padding: 16px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-x: auto;
    max-height: 500px;
    overflow-y: auto;
}

/* History */
.history { margin-top: 20px; }
.history h3 {
    font-size: 0.8em;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}
.history-item {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 6px;
    font-size: 0.85em;
    cursor: pointer;
    transition: border-color 0.15s;
}
.history-item:hover { border-color: var(--accent); }
.history-item .desc { color: var(--text); }
.history-item .time { color: var(--text-dim); font-size: 0.8em; }
</style>
</head>
<body>

<header>
    <h1>EPL AI Copilot</h1>
    <p>Describe what you want in English — get EPL code instantly</p>
</header>

<div class="container">
    <div class="input-area">
        <label>What do you want to build?</label>
        <div class="input-row">
            <input type="text" id="descInput" placeholder='e.g. "fibonacci sequence up to 20" or "todo list app"'
                   autofocus>
            <button class="btn" id="generateBtn" onclick="generate()">Generate</button>
        </div>
        <div class="suggestions">
            <span class="suggestion" onclick="suggest('hello world')">hello world</span>
            <span class="suggestion" onclick="suggest('calculator')">calculator</span>
            <span class="suggestion" onclick="suggest('fibonacci 15')">fibonacci</span>
            <span class="suggestion" onclick="suggest('fizzbuzz')">fizzbuzz</span>
            <span class="suggestion" onclick="suggest('sort a list')">sort</span>
            <span class="suggestion" onclick="suggest('guessing game')">guessing game</span>
            <span class="suggestion" onclick="suggest('class Animal')">class</span>
            <span class="suggestion" onclick="suggest('prime numbers up to 50')">primes</span>
            <span class="suggestion" onclick="suggest('star pattern')">patterns</span>
            <span class="suggestion" onclick="suggest('todo list')">todo app</span>
            <span class="suggestion" onclick="suggest('countdown timer 10')">timer</span>
            <span class="suggestion" onclick="suggest('dictionary operations')">dictionary</span>
            <span class="suggestion" onclick="suggest('creative frontend landing page')">frontend</span>
            <span class="suggestion" onclick="suggest('auth api with login and register')">auth</span>
            <span class="suggestion" onclick="suggest('chatbot api assistant')">chatbot</span>
        </div>
    </div>

    <div class="output-area" id="outputArea">
        <div class="output-header">
            <span>Generated EPL Code</span>
            <button class="copy-btn" onclick="copyCode()">Copy</button>
        </div>
        <div id="codeOutput"></div>
    </div>

    <div class="history" id="historySection" style="display:none">
        <h3>Recent Generations</h3>
        <div id="historyList"></div>
    </div>
</div>

<script>
const input = document.getElementById('descInput');
const outputArea = document.getElementById('outputArea');
const codeOutput = document.getElementById('codeOutput');
const historySection = document.getElementById('historySection');
const historyList = document.getElementById('historyList');
let history = [];

input.addEventListener('keydown', e => {
    if (e.key === 'Enter') generate();
});

function suggest(text) {
    input.value = text;
    generate();
}

async function generate() {
    const desc = input.value.trim();
    if (!desc) return;

    const btn = document.getElementById('generateBtn');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: desc })
        });
        const data = await res.json();

        if (data.code) {
            codeOutput.textContent = data.code;
            outputArea.style.display = 'block';

            // Add to history
            history.unshift({ desc, time: new Date().toLocaleTimeString() });
            if (history.length > 10) history.pop();
            renderHistory();
        }
    } catch (e) {
        codeOutput.textContent = '// Error: ' + e.message;
        outputArea.style.display = 'block';
    }

    btn.disabled = false;
    btn.textContent = 'Generate';
}

function copyCode() {
    navigator.clipboard.writeText(codeOutput.textContent).then(() => {
        const btn = event.target;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 1500);
    });
}

function renderHistory() {
    if (history.length === 0) { historySection.style.display = 'none'; return; }
    historySection.style.display = 'block';
    historyList.innerHTML = '';
    history.forEach(h => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `<span class="desc">${escapeHtml(h.desc)}</span> <span class="time">${h.time}</span>`;
        div.onclick = () => { input.value = h.desc; generate(); };
        historyList.appendChild(div);
    });
}

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>
'''
