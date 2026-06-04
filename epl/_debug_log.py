"""Internal debug-logging helper (v9.2.0+).

Used by previously-silent ``except Exception: pass`` and ``return None``
sites that swallow failures the user cannot otherwise see. When the
EPL_DEBUG environment variable is truthy, each suppressed exception is
written to stderr with the call site that caught it.

This module deliberately has zero dependencies on the rest of the EPL
package — it is safe to import from anywhere, including very early
initialisation code, without creating import cycles.
"""

from __future__ import annotations

import os
import sys
import traceback as _tb


def _debug_enabled() -> bool:
    val = os.environ.get('EPL_DEBUG', '').strip().lower()
    return val not in ('', '0', 'false', 'no', 'off')


def suppressed(where: str, exc: BaseException | None = None) -> None:
    """Record a swallowed exception. No-op unless EPL_DEBUG is set.

    Args:
        where: Stable identifier for the call site (module:function or
            module:line). Shown verbatim — keep it short and grep-friendly.
        exc:   The exception instance, or None to look it up from the
            current ``sys.exc_info()``.
    """
    if not _debug_enabled():
        return
    if exc is None:
        exc = sys.exc_info()[1]
    if exc is None:
        # Called outside an except block; nothing to log.
        return
    try:
        msg = f'[EPL debug] suppressed in {where}: {type(exc).__name__}: {exc}\n'
        sys.stderr.write(msg)
        if os.environ.get('EPL_DEBUG_TRACE', '').strip().lower() in ('1', 'true', 'yes', 'on'):
            _tb.print_exc(file=sys.stderr)
    except Exception:
        # Logging itself must never raise. Stderr could be closed during
        # interpreter shutdown — silently drop in that case.
        pass
