"""Zero-dependency ``.env`` file loading for EPL programs.

Modern runtimes (Node, Deno, Bun, python-dotenv) auto-load a ``.env`` file so
secrets such as API keys live outside source control. EPL does the same: before
a program runs, the runtime loads ``.env`` from the program's directory (and the
current working directory) into the process environment, where ``env_get("KEY")``
can read it.

Design choices (matching the de-facto dotenv standard):
- **Real environment variables always win.** A key already present in
  ``os.environ`` is never overwritten (``override=False`` by default), so a
  value injected by the shell, CI, or a container orchestrator takes precedence
  over the file. This is what makes the same ``.env`` safe across dev and prod.
- **No variable expansion.** Values are taken literally; ``${OTHER}`` is not
  expanded. This avoids surprising/unsafe substitution in secret values.
- **Opt-out** via the ``EPL_NO_DOTENV`` environment variable.
- **Never loaded in safe mode** (``--sandbox``) — untrusted code must not have
  secrets loaded into its environment (and ``env_get`` is blocked there anyway).
"""

import os

__all__ = ['parse_dotenv', 'load_dotenv', 'load_for_program']


def parse_dotenv(text):
    """Parse ``.env`` text into an ordered dict of key -> value.

    Supports ``KEY=VALUE`` and ``export KEY=VALUE`` lines, ``#`` comments, blank
    lines, and single- or double-quoted values (quotes are stripped). Whitespace
    around the key and around an unquoted value is trimmed.
    """
    result = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export ') :].lstrip()
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # Strip a single layer of matching surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result


def load_dotenv(path, override=False):
    """Load a single ``.env`` file at ``path`` into ``os.environ``.

    Returns the number of keys applied. Missing or unreadable files are a no-op
    (returns 0) — a ``.env`` is optional by definition. Existing environment
    variables are preserved unless ``override`` is True.
    """
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return 0

    applied = 0
    for key, value in parse_dotenv(text).items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied += 1
    return applied


def load_for_program(program_path=None, safe_mode=False):
    """Auto-load ``.env`` for a program about to run.

    Loads ``.env`` from the program file's directory first, then from the
    current working directory (the first occurrence of a key wins; real env vars
    always win over both). No-op in safe mode or when ``EPL_NO_DOTENV`` is set.

    Returns the total number of keys applied.
    """
    if safe_mode or os.environ.get('EPL_NO_DOTENV'):
        return 0

    seen_dirs = []
    if program_path:
        prog_dir = os.path.dirname(os.path.abspath(program_path))
        seen_dirs.append(prog_dir)
    cwd = os.getcwd()
    if cwd not in seen_dirs:
        seen_dirs.append(cwd)

    total = 0
    for directory in seen_dirs:
        total += load_dotenv(os.path.join(directory, '.env'))
    return total
