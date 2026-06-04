"""
EPL Cache Package - Python Backend
High-performance caching: LRU, TTL expiry, memoization, atomic counters.
"""

import time as _time
from collections import OrderedDict as _OrderedDict

# ═══════════════════════════════════════════════════════════
#  LRU Cache (Least Recently Used)
# ═══════════════════════════════════════════════════════════


def lru_create(max_size):
    return {
        '_type': 'lru_cache',
        'data': _OrderedDict(),
        'max_size': int(max_size),
        'hits': 0,
        'misses': 0,
    }


def cache_get(cache, cache_key):
    data = cache['data']
    if cache_key in data:
        data.move_to_end(cache_key)
        cache['hits'] += 1
        return data[cache_key]
    cache['misses'] += 1
    return None


def cache_put(cache, cache_key, cache_value):
    data = cache['data']
    if cache_key in data:
        data.move_to_end(cache_key)
        data[cache_key] = cache_value
    else:
        data[cache_key] = cache_value
        if len(data) > cache['max_size']:
            data.popitem(last=False)
    return None


def cache_has(cache, cache_key):
    return cache_key in cache['data']


def cache_remove(cache, cache_key):
    return cache['data'].pop(cache_key, None)


def cache_clear(cache):
    cache['data'].clear()
    cache['hits'] = 0
    cache['misses'] = 0
    return None


def cache_size(cache):
    return len(cache['data'])


def cache_keys(cache):
    return list(cache['data'].keys())


# ═══════════════════════════════════════════════════════════
#  TTL Cache (Time-To-Live)
# ═══════════════════════════════════════════════════════════


def ttl_create(default_ttl_seconds):
    return {
        '_type': 'ttl_cache',
        'data': {},
        'default_ttl': float(default_ttl_seconds),
        'hits': 0,
        'misses': 0,
    }


def ttl_put(cache, cache_key, cache_value, ttl_seconds=None):
    ttl = float(ttl_seconds) if ttl_seconds is not None else cache['default_ttl']
    cache['data'][cache_key] = {
        'value': cache_value,
        'expires_at': _time.time() + ttl,
    }
    return None


def ttl_get(cache, cache_key):
    entry = cache['data'].get(cache_key)
    if entry is None:
        cache['misses'] += 1
        return None
    if _time.time() > entry['expires_at']:
        del cache['data'][cache_key]
        cache['misses'] += 1
        return None
    cache['hits'] += 1
    return entry['value']


def ttl_remaining(cache, cache_key):
    entry = cache['data'].get(cache_key)
    if entry is None:
        return 0
    remaining = entry['expires_at'] - _time.time()
    if remaining <= 0:
        del cache['data'][cache_key]
        return 0
    return remaining


def ttl_extend(cache, cache_key, extra_seconds):
    entry = cache['data'].get(cache_key)
    if entry is None:
        return False
    entry['expires_at'] += float(extra_seconds)
    return True


def ttl_cleanup(cache):
    now = _time.time()
    expired_keys = [k for k, v in cache['data'].items() if now > v['expires_at']]
    for k in expired_keys:
        del cache['data'][k]
    return len(expired_keys)


# ═══════════════════════════════════════════════════════════
#  Memoization
# ═══════════════════════════════════════════════════════════


def memo_create():
    return {
        '_type': 'memo',
        'data': {},
        'hits': 0,
        'misses': 0,
    }


def memo_get_or_compute(memo, memo_key, compute_fn):
    if memo_key in memo['data']:
        memo['hits'] += 1
        return memo['data'][memo_key]
    memo['misses'] += 1
    if callable(compute_fn):
        value = compute_fn()
    else:
        value = compute_fn
    memo['data'][memo_key] = value
    return value


def memo_invalidate(memo, memo_key):
    return memo['data'].pop(memo_key, None)


def memo_stats(memo):
    total = memo['hits'] + memo['misses']
    return {
        'hits': memo['hits'],
        'misses': memo['misses'],
        'total': total,
        'hit_rate': memo['hits'] / total if total > 0 else 0.0,
        'size': len(memo['data']),
    }


# ═══════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════


def get_or_default(cache, cache_key, default_value):
    if cache.get('_type') == 'ttl_cache':
        val = ttl_get(cache, cache_key)
    else:
        val = cache_get(cache, cache_key)
    return val if val is not None else default_value


def put_if_absent(cache, cache_key, cache_value):
    if cache.get('_type') == 'ttl_cache':
        if cache_key not in cache['data'] or _time.time() > cache['data'].get(cache_key, {}).get(
            'expires_at', 0
        ):
            ttl_put(cache, cache_key, cache_value)
            return True
        return False
    else:
        if cache_key not in cache['data']:
            cache_put(cache, cache_key, cache_value)
            return True
        return False


def increment(cache, cache_key, amount=1):
    if cache.get('_type') == 'ttl_cache':
        entry = cache['data'].get(cache_key)
        if entry and _time.time() <= entry['expires_at']:
            entry['value'] = (entry['value'] or 0) + amount
            return entry['value']
        ttl_put(cache, cache_key, amount)
        return amount
    else:
        data = cache['data']
        current = data.get(cache_key, 0)
        new_val = current + amount
        data[cache_key] = new_val
        if isinstance(data, _OrderedDict):
            data.move_to_end(cache_key)
        return new_val


def decrement(cache, cache_key, amount=1):
    return increment(cache, cache_key, -amount)


def hit_rate(cache):
    hits = cache.get('hits', 0)
    misses = cache.get('misses', 0)
    total = hits + misses
    return hits / total if total > 0 else 0.0


def cache_info(cache):
    return {
        'type': cache.get('_type', 'unknown'),
        'size': len(cache.get('data', {})),
        'hits': cache.get('hits', 0),
        'misses': cache.get('misses', 0),
        'hit_rate': hit_rate(cache),
    }
