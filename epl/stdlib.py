"""
EPL Standard Library (v1.3)
Production-grade built-in functions for HTTP, Database, DateTime, Regex,
FileSystem, OS operations, Crypto, and more.

All functions register into the interpreter's BUILTINS and are available
from any EPL program without imports.
"""

import contextlib as _contextlib
import json as _json
import os as _os
import re as _re
import time as _time
import hashlib as _hashlib
import base64 as _base64
import urllib.request as _urllib_request
import urllib.error as _urllib_error
import urllib.parse as _urllib_parse
import sqlite3 as _sqlite3
import subprocess as _subprocess
import threading as _threading
import math as _math
import datetime as _datetime
import uuid as _uuid
import sys as _sys
import shutil as _shutil
import socket as _socket
import ssl as _ssl
import tempfile as _tempfile
import csv as _csv
import io as _io
import struct as _struct
import platform as _platform

from epl.errors import RuntimeError as EPLRuntimeError

_install_lock = _threading.Lock()
_module_cache = {}


def _require_module(module_name, pip_name=None, feature_name=None):
    """Lazy-import an EPL or Python module with clear error messages on failure.
    Caches successful imports. Returns the module object."""
    if module_name in _module_cache:
        return _module_cache[module_name]
    try:
        import importlib
        mod = importlib.import_module(module_name)
        _module_cache[module_name] = mod
        return mod
    except ImportError:
        if pip_name:
            if _auto_install(pip_name):
                try:
                    import importlib
                    mod = importlib.import_module(module_name)
                    _module_cache[module_name] = mod
                    return mod
                except ImportError:
                    pass
        feature = feature_name or module_name
        hint = f' Install with: pip install {pip_name}' if pip_name else ''
        raise EPLRuntimeError(
            f'{feature} is not available.{hint}', 0)


def _auto_install(pip_name, display_name=None):
    """Auto-install a Python package using pip.
    Requires EPL_AUTO_INSTALL=1 environment variable for security.
    Returns True on success."""
    import re as _re_mod
    if not _re_mod.match(r'^[A-Za-z0-9_][A-Za-z0-9._-]*$', pip_name):
        print(f'[EPL] Refusing to install invalid package name: {pip_name}',
              file=_sys.stderr)
        return False
    if not _os.environ.get('EPL_AUTO_INSTALL', '') == '1':
        display_name = display_name or pip_name
        print(f'[EPL] {display_name} is not installed. '
              f'Install manually: pip install {pip_name}\n'
              f'Or set EPL_AUTO_INSTALL=1 to allow automatic installation.',
              file=_sys.stderr)
        return False
    display_name = display_name or pip_name
    with _install_lock:
        print(f'[EPL] {display_name} not found. Installing automatically...',
              file=_sys.stderr)
        try:
            result = _subprocess.run(
                [_sys.executable, '-m', 'pip', 'install', pip_name],
                stdout=_subprocess.DEVNULL,
                stderr=_subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                print(f'[EPL] Install failed: {result.stderr[:500]}',
                      file=_sys.stderr)
                return False
            print(f'[EPL] {display_name} installed successfully.',
                  file=_sys.stderr)
            return True
        except Exception:
            return False


def _escape_kotlin_string(s):
    """Escape a string for safe use inside Kotlin string literals."""
    return (str(s).replace('\\', '\\\\').replace('"', '\\"')
            .replace('$', '\\$').replace('\n', '\\n')
            .replace('\r', '\\r').replace('\t', '\\t'))


def _escape_xml(s):
    """Escape a string for safe embedding in XML attributes/text."""
    import xml.sax.saxutils
    return xml.sax.saxutils.escape(str(s), {'"': '&quot;', "'": '&apos;'})

# ═══════════════════════════════════════════════════════════
#  Registry — all stdlib function names
# ═══════════════════════════════════════════════════════════

STDLIB_FUNCTIONS = {
    # HTTP
    'http_get', 'http_post', 'http_put', 'http_delete', 'http_request',
    'url_encode', 'url_decode', 'url_parse',
    # JSON
    'json_parse', 'json_stringify', 'json_pretty',
    # Database
    'db_open', 'db_close', 'db_execute', 'db_query', 'db_query_one',
    'db_insert', 'db_tables', 'db_create_table',
    # DateTime
    'now', 'today', 'date_format', 'date_parse', 'date_diff',
    'date_add', 'year', 'month', 'day', 'hour', 'minute', 'second',
    'day_of_week', 'days_in_month', 'is_leap_year', 'sleep',
    # Regex
    'regex_match', 'regex_find', 'regex_find_all', 'regex_replace',
    'regex_split', 'regex_test',
    # FileSystem
    'file_exists', 'file_delete', 'file_rename', 'file_copy',
    'file_size', 'file_read', 'file_write', 'file_append',
    'file_read_lines', 'file_write_lines',
    'dir_list', 'dir_create', 'dir_delete', 'dir_exists',
    'path_join', 'path_basename', 'path_dirname', 'path_extension',
    'path_absolute', 'path_split', 'temp_file', 'temp_dir',
    # OS
    'env_get', 'env_set', 'env_has', 'env_all',
    'exec', 'exec_output', 'platform', 'cpu_count',
    'memory_usage', 'cwd', 'chdir', 'pid',
    # Crypto & Encoding
    'hash_md5', 'hash_sha256', 'hash_sha512',
    'base64_encode', 'base64_decode',
    'uuid', 'uuid4',
    # Advanced Math
    'pi', 'euler', 'inf', 'nan',
    'atan', 'atan2', 'asin', 'acos',
    'degrees', 'radians', 'gcd', 'lcm', 'factorial',
    'is_finite', 'is_nan', 'clamp', 'lerp', 'sign',
    # Strings (extended)
    'format', 'regex_escape', 'string_bytes', 'bytes_string',
    'hex_encode', 'hex_decode',
    # HMAC
    'hmac_sha256', 'hmac_sha512',
    # Collections (extended)
    'zip_lists', 'enumerate_list', 'dict_from_lists',
    'set_create', 'set_add', 'set_remove', 'set_contains',
    'set_union', 'set_intersection', 'set_difference',
    # CSV
    'csv_read', 'csv_write', 'csv_parse',
    # Threading
    'thread_run', 'thread_sleep', 'atomic_counter',
    # Network
    'socket_connect', 'socket_send', 'socket_receive', 'socket_close',
    'dns_lookup', 'is_port_open',
    # System
    'print_error', 'read_input', 'exit_code',
    'args', 'timer_start', 'timer_stop',
    # Concurrency (epl.concurrency)
    'mutex_create', 'mutex_lock', 'mutex_unlock',
    'rwlock_create', 'rwlock_read_lock', 'rwlock_read_unlock',
    'rwlock_write_lock', 'rwlock_write_unlock',
    'channel_create', 'channel_send', 'channel_receive',
    'channel_try_send', 'channel_try_receive', 'channel_close',
    'semaphore_create', 'semaphore_acquire', 'semaphore_release',
    'atomic_create', 'atomic_get', 'atomic_set',
    'atomic_increment', 'atomic_decrement', 'atomic_cas',
    'thread_pool_create', 'thread_pool_submit', 'thread_pool_map',
    'thread_pool_shutdown', 'thread_pool_wait',
    'wait_group_create', 'wait_group_add', 'wait_group_done', 'wait_group_wait',
    'parallel_map', 'parallel_for_each', 'sleep_ms',
    # ORM / Database (epl.database)
    'orm_open', 'orm_close', 'orm_define_model', 'orm_add_field',
    'orm_migrate', 'orm_create', 'orm_find', 'orm_find_by_id',
    'orm_update', 'orm_delete', 'orm_delete_where',
    'orm_query', 'orm_raw_query', 'orm_raw_execute',
    'orm_transaction_begin', 'orm_transaction_commit', 'orm_transaction_rollback',
    'orm_table_exists',
    # Advanced Networking (epl.database — HTTPClient/Socket)
    'http_client_create', 'http_client_get', 'http_client_post',
    'http_client_put', 'http_client_delete',
    'tcp_connect', 'tcp_send', 'tcp_receive', 'tcp_close',

    # ── Real Database (epl.database_real) ──
    'real_db_connect', 'real_db_get', 'real_db_close', 'real_db_close_all',
    'real_db_execute', 'real_db_execute_many', 'real_db_query', 'real_db_query_one',
    'real_db_insert', 'real_db_update', 'real_db_delete', 'real_db_find_by_id',
    'real_db_create_table', 'real_db_count', 'real_db_table_exists',
    'real_db_begin', 'real_db_commit', 'real_db_rollback',
    'real_db_migrate', 'real_db_table',
    'real_db_model_define', 'real_db_model_create', 'real_db_model_find',
    'real_db_model_all', 'real_db_model_where', 'real_db_model_first',
    'real_db_model_update', 'real_db_model_delete', 'real_db_model_count',

    # ── Real Networking (epl.networking) ──
    'net_dns_lookup', 'net_dns_lookup_all', 'net_reverse_dns',
    'net_is_port_open', 'net_local_ip', 'net_hostname',
    'net_http_get', 'net_http_post', 'net_http_put', 'net_http_delete',
    'net_http_client', 'net_http_client_get', 'net_http_client_post',
    'net_http_client_put', 'net_http_client_delete',
    'net_tcp_connect', 'net_tcp_server', 'net_tcp_send', 'net_tcp_receive',
    'net_tcp_receive_line', 'net_tcp_close',
    'net_udp_socket', 'net_udp_bind', 'net_udp_send_to',
    'net_udp_receive_from', 'net_udp_close',

    # ── Real Concurrency (epl.concurrency_real) ──
    'real_thread_run', 'real_thread_join', 'real_thread_is_alive',
    'real_thread_pool_create', 'real_thread_pool_submit',
    'real_thread_pool_map', 'real_thread_pool_shutdown',
    'real_mutex_create', 'real_mutex_lock', 'real_mutex_unlock',
    'real_rwlock_create', 'real_rwlock_read_lock', 'real_rwlock_read_unlock',
    'real_rwlock_write_lock', 'real_rwlock_write_unlock',
    'real_semaphore_create', 'real_semaphore_acquire', 'real_semaphore_release',
    'real_barrier_create', 'real_barrier_wait', 'real_barrier_reset',
    'real_event_create', 'real_event_set', 'real_event_clear',
    'real_event_wait', 'real_event_is_set',
    'real_channel_create', 'real_channel_send', 'real_channel_receive',
    'real_channel_try_send', 'real_channel_try_receive', 'real_channel_close',
    'real_atomic_int', 'real_atomic_int_get', 'real_atomic_int_set',
    'real_atomic_int_inc', 'real_atomic_int_dec', 'real_atomic_int_cas',
    'real_atomic_bool', 'real_atomic_bool_get', 'real_atomic_bool_set',
    'real_atomic_bool_toggle',
    'real_waitgroup_create', 'real_waitgroup_add', 'real_waitgroup_done',
    'real_waitgroup_wait',
    'real_parallel_map', 'real_parallel_for_each', 'real_parallel_filter',
    'real_race', 'real_all_settled',
    'real_sleep', 'real_sleep_ms', 'real_cpu_count',
    'real_current_thread', 'real_active_threads',
    'real_process_run', 'real_timer', 'real_interval', 'real_interval_stop',

    # ── Bytecode VM (epl.vm) ──
    'vm_run', 'vm_compile', 'vm_disassemble',

    # ── WebServer (Flask-powered) ──
    'web_create', 'web_route', 'web_get', 'web_post', 'web_put', 'web_delete',
    'web_start', 'web_json', 'web_html', 'web_redirect', 'web_static',
    'web_template', 'web_request_data', 'web_request_args', 'web_request_method',
    'web_request_path', 'web_request_header', 'web_set_cors',
    'web_middleware', 'web_error_handler', 'web_stop',
    'web_api_create', 'web_api_resource',
    'web_session_get', 'web_session_set', 'web_session_clear',
    'web_request_param',

    # ── Desktop GUI (Tkinter-powered) ──
    'gui_window', 'gui_label', 'gui_button', 'gui_input', 'gui_text',
    'gui_checkbox', 'gui_dropdown', 'gui_slider', 'gui_image',
    'gui_frame', 'gui_grid', 'gui_pack', 'gui_place',
    'gui_on_click', 'gui_get_value', 'gui_set_value',
    'gui_messagebox', 'gui_file_dialog', 'gui_run',
    'gui_menu', 'gui_menu_item', 'gui_submenu', 'gui_canvas', 'gui_draw_rect',
    'gui_draw_circle', 'gui_draw_line', 'gui_draw_text',
    'gui_style', 'gui_close', 'gui_update', 'gui_after',
    'gui_list', 'gui_list_on_select', 'gui_table', 'gui_progress',
    'gui_tab', 'gui_tab_add',

    # ── Mobile Builder (BeeWare/Toga-powered) ──
    'mobile_create', 'mobile_label', 'mobile_button', 'mobile_input',
    'mobile_image', 'mobile_box', 'mobile_scroll', 'mobile_switch',
    'mobile_slider', 'mobile_select', 'mobile_webview', 'mobile_run',
    'mobile_build', 'mobile_style', 'mobile_navigate', 'mobile_screen',
    'mobile_alert', 'mobile_status_bar', 'mobile_get_value', 'mobile_set_value',
    'mobile_destroy', 'android_project',

    # ── Game Development (Pygame-powered) ──
    'game_create', 'game_sprite', 'game_text', 'game_rect', 'game_circle',
    'game_line', 'game_image', 'game_sound', 'game_play_sound',
    'game_music', 'game_play_music', 'game_stop_music',
    'game_key_pressed', 'game_mouse_pos', 'game_mouse_clicked',
    'game_collide', 'game_move', 'game_set_pos', 'game_get_pos',
    'game_remove', 'game_on_update', 'game_on_key', 'game_on_click',
    'game_run', 'game_fps', 'game_set_score', 'game_get_score',
    'game_scene', 'game_timer', 'game_animate', 'game_camera',
    'game_set_bg', 'game_get_size', 'game_quit',
    'game_show', 'game_hide', 'game_update_text',
    'game_set_sprite_scene', 'game_destroy',

    # ── ML/AI (scikit-learn/PyTorch/TensorFlow wrappers) ──
    'ml_load_data', 'ml_split', 'ml_linear_regression', 'ml_logistic_regression',
    'ml_decision_tree', 'ml_random_forest', 'ml_svm', 'ml_knn', 'ml_kmeans',
    'ml_train', 'ml_predict', 'ml_accuracy', 'ml_save_model', 'ml_load_model',
    'ml_neural_network', 'ml_normalize', 'ml_confusion_matrix',
    'ml_mse', 'ml_mae', 'ml_r2',
    'ml_cross_validate', 'ml_classification_report', 'ml_feature_importance',
    'ml_delete_model', 'ml_delete_data',

    # ── Deep Learning (PyTorch / TensorFlow) ──
    'dl_tensor', 'dl_sequential', 'dl_compile', 'dl_train', 'dl_predict',
    'dl_save', 'dl_load', 'dl_summary', 'dl_device', 'dl_delete',

    # ── 3D Graphics (ModernGL / PyOpenGL) ──
    '3d_create', '3d_cube', '3d_sphere', '3d_light', '3d_camera',
    '3d_rotate', '3d_move', '3d_color', '3d_render', '3d_run', '3d_delete',

    # ── Data Science (Pandas/NumPy/Matplotlib wrappers) ──
    'ds_dataframe', 'ds_read_csv', 'ds_write_csv', 'ds_read_json',
    'ds_head', 'ds_tail', 'ds_shape', 'ds_columns', 'ds_select', 'ds_filter',
    'ds_sort', 'ds_group', 'ds_mean', 'ds_sum', 'ds_count', 'ds_describe',
    'ds_merge', 'ds_concat', 'ds_dropna', 'ds_fillna', 'ds_rename',
    'ds_add_column', 'ds_drop_column', 'ds_unique', 'ds_plot', 'ds_histogram',
    'ds_scatter', 'ds_bar_chart', 'ds_line_chart', 'ds_pie_chart',
    'ds_save_plot', 'ds_show_plot', 'ds_correlation', 'ds_pivot',
    'ds_apply', 'ds_to_list', 'ds_to_map', 'ds_value_counts', 'ds_sample',
    'ds_write_json', 'ds_median', 'ds_std', 'ds_min', 'ds_max',
    'ds_dtypes', 'ds_info', 'ds_delete',

    # ══════════════════════════════════════════════════════
    #  Phase 2: Production Standard Library Additions
    # ══════════════════════════════════════════════════════

    # ── JSON (extended) ──
    'json_valid', 'json_merge', 'json_query',

    # ── Crypto (extended — encryption, CSPRNG, password hashing) ──
    'hash_sha1', 'hash_sha384', 'hash_file',
    'secure_random_bytes', 'secure_random_int',
    'aes_encrypt', 'aes_decrypt',
    'pbkdf2_hash', 'pbkdf2_verify',

    # ── SQL (extended — transactions, convenience) ──
    'db_update', 'db_delete', 'db_count', 'db_table_info',
    'db_begin', 'db_commit', 'db_rollback', 'db_backup',

    # ── OS (extended — process, signals, user info) ──
    'env_delete', 'hostname', 'arch', 'user_home', 'user_name',
    'uptime', 'exec_async', 'kill_process', 'is_admin',

    # ── FileSystem (extended — binary, metadata, walk, glob) ──
    'file_modified_time', 'file_created_time', 'file_is_dir', 'file_is_file',
    'file_read_binary', 'file_write_binary', 'file_move',
    'dir_walk', 'file_glob',
    'path_normalize', 'path_relative',

    # ── Regex (extended — compile, flags) ──
    'regex_compile', 'regex_replace_fn', 'regex_groups',

    # ── DateTime (extended — timezone, epoch) ──
    'utc_now', 'timezone', 'to_timestamp', 'from_timestamp',
    'week_of_year', 'is_weekend', 'is_weekday', 'date_range',

    # ── Collections (extended — data structures) ──
    'linked_list_new', 'linked_list_append', 'linked_list_prepend',
    'linked_list_pop', 'linked_list_pop_front', 'linked_list_get',
    'linked_list_size', 'linked_list_to_list',
    'priority_queue_new', 'priority_queue_push', 'priority_queue_pop',
    'priority_queue_peek', 'priority_queue_size',
    'deque_new', 'deque_push_back', 'deque_push_front',
    'deque_pop_back', 'deque_pop_front', 'deque_size', 'deque_to_list',
    'ordered_map_new', 'ordered_map_set', 'ordered_map_get',
    'ordered_map_delete', 'ordered_map_keys', 'ordered_map_values',
    'ordered_map_size', 'ordered_map_to_list',
    'set_size', 'set_to_list', 'set_clear',
    'group_by', 'partition', 'frequency_map',

    # ── Math (extended — log variants, hyperbolic, stats) ──
    'log2', 'log10', 'exp', 'hypot',
    'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh',
    'ceil_div', 'fmod', 'copysign',
    'permutations', 'combinations',
    'variance', 'std_dev',

    # ── Encoding (extended — URL-safe Base64, HTML entities) ──
    'base64_url_encode', 'base64_url_decode',
    'html_encode', 'html_decode',
    'base32_encode', 'base32_decode',

    # ── Testing (extended — hooks, BDD, utilities) ──
    'test_describe', 'test_it', 'test_before_each', 'test_after_each',
    'test_skip', 'test_expect_near', 'test_expect_match',
    'test_benchmark', 'test_assert_throws',

    # ── Net (extended — HTTP server, WebSocket) ──
    'net_http_server', 'net_http_server_route', 'net_http_server_start',
    'net_http_server_stop',
    'net_ws_connect', 'net_ws_send', 'net_ws_receive', 'net_ws_close',

    # ══════════════════════════════════════════════════════
    #  Phase 3: Web & Networking Production Additions
    # ══════════════════════════════════════════════════════

    # ── Auth & JWT ──
    'auth_hash_password', 'auth_verify_password',
    'auth_jwt_create', 'auth_jwt_verify', 'auth_jwt_decode',
    'auth_generate_token', 'auth_api_key_create', 'auth_api_key_verify',
    'auth_bearer_token', 'auth_basic_decode',

    # ── WebSocket Server ──
    'ws_server_create', 'ws_server_start', 'ws_server_stop',
    'ws_on_connect', 'ws_on_message', 'ws_on_disconnect',
    'ws_broadcast', 'ws_send_to',
    'ws_room_join', 'ws_room_leave', 'ws_room_broadcast',
    'ws_clients',

    # ── Template Engine (standalone) ──
    'template_create', 'template_render', 'template_render_string',
    'template_add_filter', 'template_from_file', 'template_exists',

    # ── HTML Builder ──
    'html_element', 'html_table', 'html_form', 'html_list',
    'html_link', 'html_image', 'html_page',
    'html_escape', 'html_unescape', 'html_minify',

    # ── API Helpers ──
    'api_paginate', 'api_validate', 'api_error', 'api_success',
    'api_response', 'api_parse_query', 'api_version', 'api_link_header',

    # ── ORM Extensions ──
    'orm_has_many', 'orm_belongs_to', 'orm_with_related',
    'orm_paginate', 'orm_order_by', 'orm_count_where',
    'orm_seed', 'orm_add_index', 'orm_first', 'orm_last',

    # ── Web Enhancements ──
    'web_cookie_get', 'web_cookie_set',
    'web_test_client', 'web_test_get', 'web_test_post',
    'web_upload_config', 'web_request_files',
    'web_send_file', 'web_response', 'web_url_for',
}


# ═══════════════════════════════════════════════════════════
#  Internal state — DB connections, sockets, timers
# ═══════════════════════════════════════════════════════════

_db_connections = {}   # name -> sqlite3.Connection
_db_locks = {}         # conn_id -> threading.RLock
_open_sockets = {}     # id -> socket
_timers = {}           # name -> start_time
_atomic_counters = {}  # name -> [int]
_next_id = [0]
_state_lock = _threading.Lock()  # Protects all module-level state dicts

# ── Real module state ──
_real_db_instances = {}       # name -> database_real.Database
_real_db_models = {}          # "db:model" -> database_real.Model
_real_db_txns = {}            # txn_id -> connection (in transaction)
_net_tcp_connections = {}     # id -> networking.TCPConnection
_net_tcp_servers = {}         # id -> networking.TCPServer
_net_udp_sockets = {}         # id -> networking.UDPSocket
_net_http_clients = {}        # id -> networking.HTTPClient
_real_threads = {}            # id -> concurrency_real.EPLThread
_real_thread_pools = {}       # id -> concurrency_real.ThreadPool
_real_mutexes = {}            # id -> concurrency_real.Mutex
_real_rwlocks = {}            # id -> concurrency_real.RWLock
_real_semaphores = {}         # id -> concurrency_real.Semaphore
_real_barriers = {}           # id -> concurrency_real.Barrier
_real_events = {}             # id -> concurrency_real.Event
_real_channels = {}           # id -> concurrency_real.Channel
_real_atomic_ints = {}        # id -> concurrency_real.AtomicInt
_real_atomic_bools = {}       # id -> concurrency_real.AtomicBool
_real_waitgroups = {}         # id -> concurrency_real.WaitGroup
_real_intervals = {}          # id -> concurrency_real.Interval

# ── Phase 2 state ──
_compiled_regexes = {}        # id -> compiled re.Pattern
_linked_lists = {}            # id -> list of nodes (doubly-linked as list)
_priority_queues = {}         # id -> list of (priority, value) tuples
_deques = {}                  # id -> collections.deque
_ordered_maps = {}            # id -> OrderedDict
_test_hooks = {'before_each': None, 'after_each': None, 'describes': [], 'current_group': None}
_http_servers = {}            # id -> HTTPServer instance
_ws_connections = {}          # id -> websocket connection
_async_processes = {}         # id -> subprocess.Popen

# ── Phase 3 state ──
_ws_servers = {}              # id -> {port, server, clients, rooms, handlers, thread}
_templates = {}               # name -> template string
_template_filters = {}        # name -> callable
_html_components = {}         # name -> template string
_web_test_clients = {}        # id -> Flask test client
_web_upload_configs = {}      # app_id -> {folder, max_size}
_orm_relations = {}           # "db:model" -> {relation_name: {type, target, fk}}

def _new_id():
    with _state_lock:
        _next_id[0] += 1
        return _next_id[0]


# ═══════════════════════════════════════════════════════════
#  EPL value conversion helpers
# ═══════════════════════════════════════════════════════════

def _to_epl_dict(d):
    """Convert a Python dict to EPLDict."""
    from epl.interpreter import EPLDict
    result = {}
    for k, v in d.items():
        result[str(k)] = _to_epl(v)
    return EPLDict(result)

def _to_epl(val):
    """Convert a Python value to an EPL value."""
    from epl.interpreter import EPLDict
    if val is None:
        return None
    if isinstance(val, dict):
        return _to_epl_dict(val)
    if isinstance(val, (list, tuple)):
        return [_to_epl(v) for v in val]
    if isinstance(val, set):
        return [_to_epl(v) for v in sorted(val)]
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    if isinstance(val, _datetime.datetime):
        return val.isoformat()
    if isinstance(val, _datetime.date):
        return val.isoformat()
    return val

def _from_epl(val):
    """Convert an EPL value to a Python value (for DB etc.)."""
    from epl.interpreter import EPLDict
    if isinstance(val, EPLDict):
        return {k: _from_epl(v) for k, v in val.data.items()}
    if isinstance(val, list):
        return [_from_epl(v) for v in val]
    return val


# ═══════════════════════════════════════════════════════════
#  HTTP Client
# ═══════════════════════════════════════════════════════════

def _http_request(method, url, body=None, headers=None, timeout=30):
    """Core HTTP request function."""
    if headers is None:
        headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'EPL/1.3'

    data = None
    if body is not None:
        if isinstance(body, dict):
            from epl.interpreter import EPLDict
            if isinstance(body, EPLDict):
                body = {k: _from_epl(v) for k, v in body.data.items()}
            data = _json.dumps(body).encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
        elif isinstance(body, str):
            data = body.encode('utf-8')
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'text/plain'

    req = _urllib_request.Request(url, data=data, headers=headers, method=method)
    
    # Allow HTTPS
    ctx = _ssl.create_default_context()
    
    try:
        with _urllib_request.urlopen(req, timeout=timeout, context=ctx) as resp:
            resp_body = resp.read().decode('utf-8', errors='replace')
            resp_headers = dict(resp.headers)
            status = resp.status

            # Try to auto-parse JSON
            parsed_body = resp_body
            ct = resp_headers.get('Content-Type', '')
            if 'json' in ct.lower():
                try:
                    parsed_body = _json.loads(resp_body)
                    parsed_body = _to_epl(parsed_body)
                except _json.JSONDecodeError:
                    pass

            return _to_epl_dict({
                'status': status,
                'body': parsed_body,
                'text': resp_body,
                'headers': resp_headers,
                'ok': 200 <= status < 300,
            })
    except _urllib_error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')
        return _to_epl_dict({
            'status': e.code,
            'body': body_text,
            'text': body_text,
            'headers': dict(e.headers),
            'ok': False,
            'error': str(e),
        })
    except Exception as e:
        return _to_epl_dict({
            'status': 0,
            'body': None,
            'text': '',
            'headers': {},
            'ok': False,
            'error': str(e),
        })


# ═══════════════════════════════════════════════════════════
#  SQLite Database
# ═══════════════════════════════════════════════════════════

def _db_open(path):
    """Open/create a SQLite database. Returns a connection ID."""
    conn = _sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn_id = str(_new_id())
    _db_connections[conn_id] = conn
    _db_locks[conn_id] = _threading.RLock()
    return conn_id

def _db_close(conn_id):
    """Close a database connection."""
    _db_locks.pop(str(conn_id), None)
    conn = _db_connections.pop(str(conn_id), None)
    if conn:
        conn.close()
    return True


def _db_connection_lock(conn_id):
    lock = _db_locks.get(str(conn_id))
    if lock is None:
        return _contextlib.nullcontext()
    return lock

def _db_execute(conn_id, sql, params=None):
    """Execute a SQL statement. Returns rows affected."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    p = _from_epl(params) if params else []
    if isinstance(p, dict):
        p = p  # named params
    elif not isinstance(p, (list, tuple)):
        p = [p]
    with _db_connection_lock(conn_id):
        cursor = conn.execute(sql, p)
        conn.commit()
        return cursor.rowcount

def _db_query(conn_id, sql, params=None):
    """Execute a query and return all rows as a list of maps."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    p = _from_epl(params) if params else []
    if isinstance(p, dict):
        p = p
    elif not isinstance(p, (list, tuple)):
        p = [p]
    with _db_connection_lock(conn_id):
        cursor = conn.execute(sql, p)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [_to_epl_dict(dict(zip(columns, row))) for row in rows]

def _db_query_one(conn_id, sql, params=None):
    """Execute a query and return the first row as a map, or nothing."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    p = _from_epl(params) if params else []
    if isinstance(p, dict):
        p = p
    elif not isinstance(p, (list, tuple)):
        p = [p]
    with _db_connection_lock(conn_id):
        cursor = conn.execute(sql, p)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row is None:
            return None
        return _to_epl_dict(dict(zip(columns, row)))

def _db_insert(conn_id, table, record):
    """Insert a record (map) into a table. Returns the rowid."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    from epl.interpreter import EPLDict
    if isinstance(record, EPLDict):
        data = {k: _from_epl(v) for k, v in record.data.items()}
    else:
        data = _from_epl(record)
    _IDENT_RE = _re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    if not _IDENT_RE.match(table):
        raise RuntimeError(f'Invalid table name: {table}')
    for k in data.keys():
        if not _IDENT_RE.match(k):
            raise RuntimeError(f'Invalid column name: {k}')
    cols = ', '.join(f'"{k}"' for k in data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f'"{table}" ({cols}) VALUES ({placeholders})'
    sql = f'INSERT INTO {sql}'
    with _db_connection_lock(conn_id):
        cursor = conn.execute(sql, list(data.values()))
        conn.commit()
        return cursor.lastrowid

def _db_tables(conn_id):
    """List all table names in the database."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    with _db_connection_lock(conn_id):
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

def _db_create_table(conn_id, table, columns):
    """Create a table. columns can be a map of name -> type, or a raw SQL column definition string."""
    conn = _db_connections.get(str(conn_id))
    if not conn:
        raise RuntimeError(f'No database connection with ID: {conn_id}')
    _IDENT_RE = _re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    _SAFE_TYPES = frozenset({'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC',
                             'VARCHAR', 'BOOLEAN', 'DATE', 'DATETIME',
                             'PRIMARY KEY', 'NOT NULL', 'UNIQUE', 'AUTOINCREMENT',
                             'DEFAULT', 'CHECK', 'REFERENCES'})
    if not _IDENT_RE.match(table):
        raise RuntimeError(f'Invalid table name: {table}')
    if isinstance(columns, str):
        raise RuntimeError('Raw SQL column definitions are not allowed. Use a map of name -> type.')
    else:
        from epl.interpreter import EPLDict
        if isinstance(columns, EPLDict):
            cols = columns.data
        else:
            cols = _from_epl(columns)
        for col_name in cols.keys():
            if not _IDENT_RE.match(col_name):
                raise RuntimeError(f'Invalid column name: {col_name}')
        for col_name, typ in cols.items():
            # Validate each word in the column type against safe types
            words = str(typ).upper().split()
            for w in words:
                # Allow type names, numbers (for VARCHAR(255)), and parenthesized values
                cleaned = w.strip('()')
                if cleaned and not cleaned.isdigit() and cleaned not in _SAFE_TYPES:
                    raise RuntimeError(f'Invalid column type component: {w}')
        col_defs = ', '.join(f'"{name}" {typ}' for name, typ in cols.items())
    with _db_connection_lock(conn_id):
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')
        conn.commit()
        return True


# ═══════════════════════════════════════════════════════════
#  DateTime
# ═══════════════════════════════════════════════════════════

def _now():
    """Current datetime as ISO string."""
    return _datetime.datetime.now().isoformat()

def _today():
    """Current date as ISO string."""
    return _datetime.date.today().isoformat()

def _date_format(date_str, fmt):
    """Format a date string with a strftime format."""
    dt = _parse_dt(date_str)
    return dt.strftime(fmt)

def _date_parse(date_str, fmt=None):
    """Parse a date string. Returns ISO format."""
    if fmt:
        dt = _datetime.datetime.strptime(date_str, fmt)
    else:
        dt = _parse_dt(date_str)
    return dt.isoformat()

def _parse_dt(s):
    """Best-effort datetime parsing."""
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y',
                '%m/%d/%Y', '%d-%m-%Y', '%B %d, %Y'):
        try:
            return _datetime.datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    raise ValueError(f'Cannot parse date: {s}')

def _date_diff(date1, date2, unit='days'):
    """Difference between two dates. unit: days, hours, minutes, seconds."""
    d1 = _parse_dt(date1)
    d2 = _parse_dt(date2)
    delta = d1 - d2
    if unit == 'days':
        return delta.days
    if unit == 'hours':
        return delta.total_seconds() / 3600
    if unit == 'minutes':
        return delta.total_seconds() / 60
    if unit == 'seconds':
        return delta.total_seconds()
    return delta.days

def _date_add(date_str, amount, unit='days'):
    """Add time to a date. Returns ISO string."""
    dt = _parse_dt(date_str)
    amount = int(amount)
    if unit == 'days':
        dt += _datetime.timedelta(days=amount)
    elif unit == 'hours':
        dt += _datetime.timedelta(hours=amount)
    elif unit == 'minutes':
        dt += _datetime.timedelta(minutes=amount)
    elif unit == 'seconds':
        dt += _datetime.timedelta(seconds=amount)
    elif unit == 'weeks':
        dt += _datetime.timedelta(weeks=amount)
    elif unit == 'months':
        month = dt.month + amount
        year = dt.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(dt.day, _days_in_month(year, month))
        dt = dt.replace(year=year, month=month, day=day)
    elif unit == 'years':
        dt = dt.replace(year=dt.year + amount)
    return dt.isoformat()

def _year(date_str):
    return _parse_dt(date_str).year

def _month(date_str):
    return _parse_dt(date_str).month

def _day(date_str):
    return _parse_dt(date_str).day

def _hour(date_str):
    return _parse_dt(date_str).hour

def _minute(date_str):
    return _parse_dt(date_str).minute

def _second(date_str):
    return _parse_dt(date_str).second

def _day_of_week(date_str):
    """0 = Monday, 6 = Sunday."""
    return _parse_dt(date_str).weekday()

def _days_in_month(year_or_date, month=None):
    """Days in a given month."""
    import calendar
    if month is None:
        dt = _parse_dt(str(year_or_date))
        return calendar.monthrange(dt.year, dt.month)[1]
    return calendar.monthrange(int(year_or_date), int(month))[1]

def _is_leap_year(year_or_date):
    import calendar
    if isinstance(year_or_date, str):
        y = _parse_dt(year_or_date).year
    else:
        y = int(year_or_date)
    return calendar.isleap(y)


# ═══════════════════════════════════════════════════════════
#  Regular Expressions
# ═══════════════════════════════════════════════════════════

def _regex_match(pattern, text):
    """Full match. Returns the matched string or nothing."""
    m = _re.match(pattern, text)
    return m.group(0) if m else None

def _regex_find(pattern, text):
    """Find first match. Returns a map with match, start, end, groups."""
    m = _re.search(pattern, text)
    if not m:
        return None
    return _to_epl_dict({
        'match': m.group(0),
        'start': m.start(),
        'end': m.end(),
        'groups': list(m.groups()),
    })

def _regex_find_all(pattern, text):
    """Find all matches. Returns a list of strings."""
    return _re.findall(pattern, text)

def _regex_replace(pattern, replacement, text):
    """Replace all matches."""
    return _re.sub(pattern, replacement, text)

def _regex_split(pattern, text):
    """Split text by pattern."""
    return _re.split(pattern, text)

def _regex_test(pattern, text):
    """Test if text matches pattern. Returns boolean."""
    return bool(_re.search(pattern, text))


# ═══════════════════════════════════════════════════════════
#  File System (Enhanced)
# ═══════════════════════════════════════════════════════════

def _file_exists(path):
    return _os.path.isfile(str(path))

def _file_delete(path):
    _os.remove(str(path))
    return True

def _file_rename(old_path, new_path):
    _os.rename(str(old_path), str(new_path))
    return True

def _file_copy(src, dst):
    _shutil.copy2(str(src), str(dst))
    return True

def _file_size(path):
    return _os.path.getsize(str(path))

def _file_read(path):
    with open(str(path), 'r', encoding='utf-8') as f:
        return f.read()

def _file_write(path, content):
    with open(str(path), 'w', encoding='utf-8') as f:
        f.write(str(content))
    return True

def _file_append(path, content):
    with open(str(path), 'a', encoding='utf-8') as f:
        f.write(str(content))
    return True

def _file_read_lines(path):
    with open(str(path), 'r', encoding='utf-8') as f:
        return [line.rstrip('\n') for line in f]

def _file_write_lines(path, lines):
    with open(str(path), 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(str(line) + '\n')
    return True

def _dir_list(path='.'):
    entries = _os.listdir(str(path))
    return sorted(entries)

def _dir_create(path):
    _os.makedirs(str(path), exist_ok=True)
    return True

def _dir_delete(path):
    _shutil.rmtree(str(path))
    return True

def _dir_exists(path):
    return _os.path.isdir(str(path))

def _path_join(*parts):
    return _os.path.join(*[str(p) for p in parts])

def _path_basename(path):
    return _os.path.basename(str(path))

def _path_dirname(path):
    return _os.path.dirname(str(path))

def _path_extension(path):
    return _os.path.splitext(str(path))[1]

def _path_absolute(path):
    return _os.path.abspath(str(path))

def _path_split(path):
    head, tail = _os.path.split(str(path))
    return [head, tail]

def _temp_file(suffix='', prefix='epl_'):
    fd, path = _tempfile.mkstemp(suffix=suffix, prefix=prefix)
    _os.close(fd)
    return path

def _temp_dir(prefix='epl_'):
    return _tempfile.mkdtemp(prefix=prefix)


# ═══════════════════════════════════════════════════════════
#  OS Operations
# ═══════════════════════════════════════════════════════════

def _env_get(name, default=None):
    return _os.environ.get(str(name), default)

def _env_set(name, value):
    _os.environ[str(name)] = str(value)
    return True

def _env_has(name):
    return str(name) in _os.environ

def _env_all():
    return _to_epl_dict(dict(_os.environ))

def _exec(command):
    """Execute a command. Returns exit code."""
    import shlex as _shlex
    try:
        cmd_parts = _shlex.split(str(command))
    except ValueError as e:
        raise EPLRuntimeError(f'Invalid command syntax: {e}', 0)
    try:
        result = _subprocess.run(cmd_parts, capture_output=True, text=True)
    except FileNotFoundError:
        raise EPLRuntimeError(f'Command not found: {cmd_parts[0]}', 0)
    return result.returncode

def _exec_output(command):
    """Execute a command and return its output as a map."""
    import shlex as _shlex
    try:
        cmd_parts = _shlex.split(str(command))
    except ValueError as e:
        raise EPLRuntimeError(f'Invalid command syntax: {e}', 0)
    try:
        result = _subprocess.run(cmd_parts, capture_output=True, text=True)
    except FileNotFoundError:
        raise EPLRuntimeError(f'Command not found: {cmd_parts[0]}', 0)
    return _to_epl_dict({
        'stdout': result.stdout,
        'stderr': result.stderr,
        'exit_code': result.returncode,
        'ok': result.returncode == 0,
    })

def _get_platform():
    return _to_epl_dict({
        'os': _platform.system(),
        'version': _platform.version(),
        'arch': _platform.machine(),
        'python': _platform.python_version(),
        'node': _platform.node(),
    })

def _cpu_count():
    return _os.cpu_count() or 1

def _memory_usage():
    """Get current process memory usage in MB."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        # Windows
        try:
            import psutil
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            return -1

def _cwd():
    return _os.getcwd()

def _chdir(path):
    _os.chdir(str(path))
    return True

def _pid():
    return _os.getpid()


# ═══════════════════════════════════════════════════════════
#  Crypto & Encoding
# ═══════════════════════════════════════════════════════════

def _hash_md5(text):
    return _hashlib.md5(str(text).encode('utf-8')).hexdigest()

def _hash_sha256(text):
    return _hashlib.sha256(str(text).encode('utf-8')).hexdigest()

def _hash_sha512(text):
    return _hashlib.sha512(str(text).encode('utf-8')).hexdigest()

def _base64_encode(text):
    return _base64.b64encode(str(text).encode('utf-8')).decode('ascii')

def _base64_decode(text):
    return _base64.b64decode(str(text)).decode('utf-8')

def _make_uuid():
    return str(_uuid.uuid4())


# ═══════════════════════════════════════════════════════════
#  Advanced Math
# ═══════════════════════════════════════════════════════════

def _atan(x):
    return _math.atan(x)

def _atan2(y, x):
    return _math.atan2(y, x)

def _asin(x):
    return _math.asin(x)

def _acos(x):
    return _math.acos(x)

def _degrees(radians):
    return _math.degrees(radians)

def _radians(degrees):
    return _math.radians(degrees)

def _gcd(a, b):
    return _math.gcd(int(a), int(b))

def _lcm(a, b):
    return abs(int(a) * int(b)) // _math.gcd(int(a), int(b))

def _factorial(n):
    return _math.factorial(int(n))

def _is_finite(x):
    return _math.isfinite(x)

def _is_nan(x):
    return _math.isnan(x)

def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))

def _lerp(a, b, t):
    return a + (b - a) * t

def _sign(x):
    if x > 0: return 1
    if x < 0: return -1
    return 0


# ═══════════════════════════════════════════════════════════
#  String / Encoding extensions
# ═══════════════════════════════════════════════════════════

def _format_string(template, *args):
    """Python-style format: format("Hello {0}, you are {1}", name, age)"""
    return str(template).format(*args)

def _regex_escape(text):
    return _re.escape(str(text))

def _string_bytes(text, encoding='utf-8'):
    """Get the byte representation of a string as a list of integers."""
    return list(str(text).encode(encoding))

def _bytes_string(byte_list, encoding='utf-8'):
    """Convert a list of byte values back to a string."""
    return bytes(byte_list).decode(encoding)

def _hex_encode(text):
    return str(text).encode('utf-8').hex()

def _hex_decode(hex_str):
    return bytes.fromhex(str(hex_str)).decode('utf-8')


# ═══════════════════════════════════════════════════════════
#  HMAC Functions
# ═══════════════════════════════════════════════════════════

def _hmac_sha256(key, message):
    """HMAC-SHA256 authentication code."""
    import hmac as _hmac_mod
    return _hmac_mod.new(
        str(key).encode('utf-8'),
        str(message).encode('utf-8'),
        _hashlib.sha256
    ).hexdigest()

def _hmac_sha512(key, message):
    """HMAC-SHA512 authentication code."""
    import hmac as _hmac_mod
    return _hmac_mod.new(
        str(key).encode('utf-8'),
        str(message).encode('utf-8'),
        _hashlib.sha512
    ).hexdigest()


# ═══════════════════════════════════════════════════════════
#  Collections (extended)
# ═══════════════════════════════════════════════════════════

def _zip_lists(*lists):
    """Zip multiple lists together."""
    return [list(t) for t in zip(*lists)]

def _enumerate_list(lst, start=0):
    """Enumerate a list, returns list of [index, value] pairs."""
    return [[i, v] for i, v in enumerate(lst, start=int(start))]

def _dict_from_lists(keys_list, values_list):
    """Create a map from two lists (keys and values)."""
    return _to_epl_dict(dict(zip(keys_list, values_list)))

# Sets — represented as sorted lists with set operations
def _set_create(*items):
    return sorted(set(items))

def _set_add(s, item):
    result = set(s)
    result.add(item)
    return sorted(result)

def _set_remove(s, item):
    result = set(s)
    result.discard(item)
    return sorted(result)

def _set_contains(s, item):
    return item in s

def _set_union(s1, s2):
    return sorted(set(s1) | set(s2))

def _set_intersection(s1, s2):
    return sorted(set(s1) & set(s2))

def _set_difference(s1, s2):
    return sorted(set(s1) - set(s2))


# ═══════════════════════════════════════════════════════════
#  CSV
# ═══════════════════════════════════════════════════════════

def _csv_read(path, has_header=True):
    """Read a CSV file. Returns list of maps (if header) or list of lists."""
    with open(str(path), 'r', newline='', encoding='utf-8') as f:
        if has_header:
            reader = _csv.DictReader(f)
            return [_to_epl_dict(dict(row)) for row in reader]
        else:
            reader = _csv.reader(f)
            return [list(row) for row in reader]

def _csv_write(path, data, headers=None):
    """Write data to CSV. data is list of maps or list of lists."""
    from epl.interpreter import EPLDict
    with open(str(path), 'w', newline='', encoding='utf-8') as f:
        if data and isinstance(data[0], EPLDict):
            hdrs = headers or list(data[0].data.keys())
            writer = _csv.DictWriter(f, fieldnames=hdrs)
            writer.writeheader()
            for row in data:
                writer.writerow({k: _from_epl(v) for k, v in row.data.items()})
        else:
            writer = _csv.writer(f)
            if headers:
                writer.writerow(headers)
            for row in data:
                writer.writerow(row)
    return True

def _csv_parse(text, has_header=True):
    """Parse CSV from a string."""
    f = _io.StringIO(str(text))
    if has_header:
        reader = _csv.DictReader(f)
        return [_to_epl_dict(dict(row)) for row in reader]
    else:
        reader = _csv.reader(f)
        return [list(row) for row in reader]


# ═══════════════════════════════════════════════════════════
#  Threading
# ═══════════════════════════════════════════════════════════

def _thread_run(func, *args):
    """Run a function in a background thread. Returns thread ID."""
    tid = _new_id()
    def _wrapper():
        try:
            func(*args)
        except Exception as e:
            import sys
            print(f"[EPL thread {tid}] Unhandled exception: {e}", file=sys.stderr)
    t = _threading.Thread(target=_wrapper, daemon=True)
    t.start()
    return tid

def _thread_sleep(seconds):
    _time.sleep(float(seconds))
    return True

def _atomic_counter(name='default', increment=None):
    """Thread-safe counter. Call with just name to read, with increment to change."""
    with _state_lock:
        if name not in _atomic_counters:
            _atomic_counters[name] = [0]
        if increment is not None:
            _atomic_counters[name][0] += int(increment)
        return _atomic_counters[name][0]


# ═══════════════════════════════════════════════════════════
#  Network (low-level)
# ═══════════════════════════════════════════════════════════

def _socket_connect(host, port, timeout=10):
    """Connect a TCP socket. Returns socket ID."""
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(float(timeout))
    s.connect((str(host), int(port)))
    sid = str(_new_id())
    _open_sockets[sid] = s
    return sid

def _socket_send(sock_id, data):
    """Send data through a socket."""
    s = _open_sockets.get(str(sock_id))
    if not s:
        raise RuntimeError(f'No socket with ID: {sock_id}')
    s.sendall(str(data).encode('utf-8'))
    return True

def _socket_receive(sock_id, size=4096):
    """Receive data from a socket."""
    s = _open_sockets.get(str(sock_id))
    if not s:
        raise RuntimeError(f'No socket with ID: {sock_id}')
    return s.recv(int(size)).decode('utf-8', errors='replace')

def _socket_close(sock_id):
    """Close a socket."""
    s = _open_sockets.pop(str(sock_id), None)
    if s:
        s.close()
    return True

def _dns_lookup(hostname):
    """DNS lookup. Returns list of IP addresses."""
    try:
        results = _socket.getaddrinfo(str(hostname), None)
        ips = list(set(r[4][0] for r in results))
        return sorted(ips)
    except _socket.gaierror as e:
        return []

def _is_port_open(host, port, timeout=3):
    """Check if a TCP port is open."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(float(timeout))
        s.connect((str(host), int(port)))
        s.close()
        return True
    except (OSError, _socket.error):
        return False


# ═══════════════════════════════════════════════════════════
#  System utilities
# ═══════════════════════════════════════════════════════════

def _print_error(msg):
    print(str(msg), file=_sys.stderr)
    return True

def _read_input(prompt=''):
    return input(str(prompt))

def _exit_code(code):
    _sys.exit(int(code))

def _get_args():
    return _sys.argv[:]

def _timer_start(name='default'):
    _timers[str(name)] = _time.perf_counter()
    return True

def _timer_stop(name='default'):
    start = _timers.pop(str(name), None)
    if start is None:
        return -1.0
    return round(_time.perf_counter() - start, 6)


# ═══════════════════════════════════════════════════════════
#  URL utilities
# ═══════════════════════════════════════════════════════════

def _url_encode(text):
    return _urllib_parse.quote_plus(str(text))

def _url_decode(text):
    return _urllib_parse.unquote_plus(str(text))

def _url_parse(url):
    parsed = _urllib_parse.urlparse(str(url))
    return _to_epl_dict({
        'scheme': parsed.scheme,
        'host': parsed.hostname or '',
        'port': parsed.port or 0,
        'path': parsed.path,
        'query': parsed.query,
        'fragment': parsed.fragment,
    })


# ═══════════════════════════════════════════════════════════
#  Dispatcher — called from interpreter
# ═══════════════════════════════════════════════════════════

def call_stdlib(name, args, line):
    """Dispatch a stdlib function call.

    Args:
        name: function name
        args: list of evaluated arguments
        line: source line number (for error messages)

    Returns:
        The result value

    Raises:
        EPLRuntimeError on failure
    """
    try:
        # ── HTTP ──
        if name == 'http_get':
            if len(args) < 1: raise EPLRuntimeError('http_get(url[, headers]) requires a URL.', line)
            headers = _from_epl(args[1]) if len(args) > 1 else None
            return _http_request('GET', str(args[0]), headers=headers)

        if name == 'http_post':
            if len(args) < 1: raise EPLRuntimeError('http_post(url[, body, headers]) requires a URL.', line)
            body = args[1] if len(args) > 1 else None
            headers = _from_epl(args[2]) if len(args) > 2 else None
            return _http_request('POST', str(args[0]), body=body, headers=headers)

        if name == 'http_put':
            if len(args) < 1: raise EPLRuntimeError('http_put(url[, body, headers]) requires a URL.', line)
            body = args[1] if len(args) > 1 else None
            headers = _from_epl(args[2]) if len(args) > 2 else None
            return _http_request('PUT', str(args[0]), body=body, headers=headers)

        if name == 'http_delete':
            if len(args) < 1: raise EPLRuntimeError('http_delete(url[, headers]) requires a URL.', line)
            headers = _from_epl(args[1]) if len(args) > 1 else None
            return _http_request('DELETE', str(args[0]), headers=headers)

        if name == 'http_request':
            if len(args) < 2: raise EPLRuntimeError('http_request(method, url[, body, headers]) requires method and URL.', line)
            body = args[2] if len(args) > 2 else None
            headers = _from_epl(args[3]) if len(args) > 3 else None
            return _http_request(str(args[0]).upper(), str(args[1]), body=body, headers=headers)

        if name == 'url_encode': return _url_encode(args[0])
        if name == 'url_decode': return _url_decode(args[0])
        if name == 'url_parse': return _url_parse(args[0])

        # ── JSON ──
        if name == 'json_parse':
            if len(args) < 1: raise EPLRuntimeError('json_parse(text) requires a JSON string.', line)
            try:
                return _to_epl(_json.loads(str(args[0])))
            except _json.JSONDecodeError as e:
                raise EPLRuntimeError(f'json_parse error: {e}', line)
        if name == 'json_stringify':
            if len(args) < 1: raise EPLRuntimeError('json_stringify(value) requires a value.', line)
            try:
                return _json.dumps(_from_epl(args[0]))
            except (TypeError, ValueError) as e:
                raise EPLRuntimeError(f'json_stringify error: {e}', line)
        if name == 'json_pretty':
            if len(args) < 1: raise EPLRuntimeError('json_pretty(value) requires a value.', line)
            try:
                return _json.dumps(_from_epl(args[0]), indent=2)
            except (TypeError, ValueError) as e:
                raise EPLRuntimeError(f'json_pretty error: {e}', line)

        # ── Database ──
        if name == 'db_open':
            if len(args) < 1: raise EPLRuntimeError('db_open(path) requires a path.', line)
            return _db_open(args[0])

        if name == 'db_close':
            if len(args) < 1: raise EPLRuntimeError('db_close(conn) requires a connection ID.', line)
            return _db_close(args[0])

        if name == 'db_execute':
            if len(args) < 2: raise EPLRuntimeError('db_execute(conn, sql[, params]) requires conn and SQL.', line)
            params = args[2] if len(args) > 2 else None
            return _db_execute(args[0], str(args[1]), params)

        if name == 'db_query':
            if len(args) < 2: raise EPLRuntimeError('db_query(conn, sql[, params]) requires conn and SQL.', line)
            params = args[2] if len(args) > 2 else None
            return _db_query(args[0], str(args[1]), params)

        if name == 'db_query_one':
            if len(args) < 2: raise EPLRuntimeError('db_query_one(conn, sql[, params]) requires conn and SQL.', line)
            params = args[2] if len(args) > 2 else None
            return _db_query_one(args[0], str(args[1]), params)

        if name == 'db_insert':
            if len(args) < 3: raise EPLRuntimeError('db_insert(conn, table, record) requires conn, table, and record map.', line)
            return _db_insert(args[0], str(args[1]), args[2])

        if name == 'db_tables':
            if len(args) < 1: raise EPLRuntimeError('db_tables(conn) requires a connection ID.', line)
            return _db_tables(args[0])

        if name == 'db_create_table':
            if len(args) < 3: raise EPLRuntimeError('db_create_table(conn, name, columns) requires conn, table name, and columns map.', line)
            return _db_create_table(args[0], str(args[1]), args[2])

        # ── DateTime ──
        if name == 'now': return _now()
        if name == 'today': return _today()

        if name == 'date_format':
            if len(args) < 2: raise EPLRuntimeError('date_format(date, format) requires 2 args.', line)
            return _date_format(str(args[0]), str(args[1]))

        if name == 'date_parse':
            if len(args) < 1: raise EPLRuntimeError('date_parse(text[, format]) requires a text arg.', line)
            fmt = str(args[1]) if len(args) > 1 else None
            return _date_parse(str(args[0]), fmt)

        if name == 'date_diff':
            if len(args) < 2: raise EPLRuntimeError('date_diff(date1, date2[, unit]) requires 2 dates.', line)
            unit = str(args[2]) if len(args) > 2 else 'days'
            return _date_diff(str(args[0]), str(args[1]), unit)

        if name == 'date_add':
            if len(args) < 2: raise EPLRuntimeError('date_add(date, amount[, unit]) requires date and amount.', line)
            unit = str(args[2]) if len(args) > 2 else 'days'
            return _date_add(str(args[0]), args[1], unit)

        if name == 'year': return _year(str(args[0])) if args else _datetime.datetime.now().year
        if name == 'month': return _month(str(args[0])) if args else _datetime.datetime.now().month
        if name == 'day': return _day(str(args[0])) if args else _datetime.datetime.now().day
        if name == 'hour': return _hour(str(args[0])) if args else _datetime.datetime.now().hour
        if name == 'minute': return _minute(str(args[0])) if args else _datetime.datetime.now().minute
        if name == 'second': return _second(str(args[0])) if args else _datetime.datetime.now().second
        if name == 'day_of_week': return _day_of_week(str(args[0])) if args else _datetime.datetime.now().weekday()
        if name == 'days_in_month':
            if len(args) == 2: return _days_in_month(args[0], args[1])
            if len(args) == 1: return _days_in_month(args[0])
            raise EPLRuntimeError('days_in_month(year, month) or days_in_month(date)', line)
        if name == 'is_leap_year':
            if len(args) == 1: return _is_leap_year(args[0])
            raise EPLRuntimeError('is_leap_year(year) requires 1 arg.', line)
        if name == 'sleep':
            if len(args) == 1:
                _time.sleep(float(args[0]))
                return True
            raise EPLRuntimeError('sleep(seconds) requires 1 arg.', line)

        # ── Regex ──
        if name == 'regex_match':
            if len(args) < 2: raise EPLRuntimeError('regex_match(pattern, text) requires 2 args.', line)
            return _regex_match(str(args[0]), str(args[1]))
        if name == 'regex_find':
            if len(args) < 2: raise EPLRuntimeError('regex_find(pattern, text) requires 2 args.', line)
            return _regex_find(str(args[0]), str(args[1]))
        if name == 'regex_find_all':
            if len(args) < 2: raise EPLRuntimeError('regex_find_all(pattern, text) requires 2 args.', line)
            return _regex_find_all(str(args[0]), str(args[1]))
        if name == 'regex_replace':
            if len(args) < 3: raise EPLRuntimeError('regex_replace(pattern, replacement, text) requires 3 args.', line)
            return _regex_replace(str(args[0]), str(args[1]), str(args[2]))
        if name == 'regex_split':
            if len(args) < 2: raise EPLRuntimeError('regex_split(pattern, text) requires 2 args.', line)
            return _regex_split(str(args[0]), str(args[1]))
        if name == 'regex_test':
            if len(args) < 2: raise EPLRuntimeError('regex_test(pattern, text) requires 2 args.', line)
            return _regex_test(str(args[0]), str(args[1]))

        # ── File System ──
        if name == 'file_exists': return _file_exists(args[0]) if args else False
        if name == 'file_delete':
            if not args: raise EPLRuntimeError('file_delete(path) requires a path.', line)
            return _file_delete(args[0])
        if name == 'file_rename':
            if len(args) < 2: raise EPLRuntimeError('file_rename(old, new) requires 2 args.', line)
            return _file_rename(args[0], args[1])
        if name == 'file_copy':
            if len(args) < 2: raise EPLRuntimeError('file_copy(src, dst) requires 2 args.', line)
            return _file_copy(args[0], args[1])
        if name == 'file_size':
            if not args: raise EPLRuntimeError('file_size(path) requires a path.', line)
            return _file_size(args[0])
        if name == 'file_read':
            if not args: raise EPLRuntimeError('file_read(path) requires a path.', line)
            return _file_read(args[0])
        if name == 'file_write':
            if len(args) < 2: raise EPLRuntimeError('file_write(path, content) requires 2 args.', line)
            return _file_write(args[0], args[1])
        if name == 'file_append':
            if len(args) < 2: raise EPLRuntimeError('file_append(path, content) requires 2 args.', line)
            return _file_append(args[0], args[1])
        if name == 'file_read_lines':
            if not args: raise EPLRuntimeError('file_read_lines(path) requires a path.', line)
            return _file_read_lines(args[0])
        if name == 'file_write_lines':
            if len(args) < 2: raise EPLRuntimeError('file_write_lines(path, lines) requires 2 args.', line)
            return _file_write_lines(args[0], args[1])
        if name == 'dir_list': return _dir_list(args[0] if args else '.')
        if name == 'dir_create':
            if not args: raise EPLRuntimeError('dir_create(path) requires a path.', line)
            return _dir_create(args[0])
        if name == 'dir_delete':
            if not args: raise EPLRuntimeError('dir_delete(path) requires a path.', line)
            return _dir_delete(args[0])
        if name == 'dir_exists': return _dir_exists(args[0]) if args else False
        if name == 'path_join': return _path_join(*args)
        if name == 'path_basename': return _path_basename(args[0]) if args else ''
        if name == 'path_dirname': return _path_dirname(args[0]) if args else ''
        if name == 'path_extension': return _path_extension(args[0]) if args else ''
        if name == 'path_absolute': return _path_absolute(args[0]) if args else _os.getcwd()
        if name == 'path_split': return _path_split(args[0]) if args else ['', '']
        if name == 'temp_file':
            suffix = str(args[0]) if args else ''
            return _temp_file(suffix)
        if name == 'temp_dir':
            prefix = str(args[0]) if args else 'epl_'
            return _temp_dir(prefix)

        # ── OS ──
        if name == 'env_get':
            if not args: raise EPLRuntimeError('env_get(name[, default]) requires a name.', line)
            default = args[1] if len(args) > 1 else None
            return _env_get(args[0], default)
        if name == 'env_set':
            if len(args) < 2: raise EPLRuntimeError('env_set(name, value) requires 2 args.', line)
            return _env_set(args[0], args[1])
        if name == 'env_has':
            if not args: raise EPLRuntimeError('env_has(name) requires a name.', line)
            return _env_has(args[0])
        if name == 'env_all': return _env_all()
        if name == 'exec':
            if not args: raise EPLRuntimeError('exec(command) requires a command.', line)
            return _exec(args[0])
        if name == 'exec_output':
            if not args: raise EPLRuntimeError('exec_output(command) requires a command.', line)
            return _exec_output(args[0])
        if name == 'platform': return _get_platform()
        if name == 'cpu_count': return _cpu_count()
        if name == 'memory_usage': return _memory_usage()
        if name == 'cwd': return _cwd()
        if name == 'chdir':
            if not args: raise EPLRuntimeError('chdir(path) requires a path.', line)
            return _chdir(args[0])
        if name == 'pid': return _pid()

        # ── Crypto & Encoding ──
        if name == 'hash_md5':
            if not args: raise EPLRuntimeError('hash_md5(text) requires text.', line)
            return _hash_md5(args[0])
        if name == 'hash_sha256':
            if not args: raise EPLRuntimeError('hash_sha256(text) requires text.', line)
            return _hash_sha256(args[0])
        if name == 'hash_sha512':
            if not args: raise EPLRuntimeError('hash_sha512(text) requires text.', line)
            return _hash_sha512(args[0])
        if name == 'base64_encode':
            if not args: raise EPLRuntimeError('base64_encode(text) requires text.', line)
            return _base64_encode(args[0])
        if name == 'base64_decode':
            if not args: raise EPLRuntimeError('base64_decode(text) requires text.', line)
            return _base64_decode(args[0])
        if name in ('uuid', 'uuid4'): return _make_uuid()

        # ── Advanced Math ──
        if name == 'pi': return _math.pi
        if name == 'euler': return _math.e
        if name == 'inf': return _math.inf
        if name == 'nan': return _math.nan
        if name == 'atan': return _atan(args[0])
        if name == 'atan2':
            if len(args) < 2: raise EPLRuntimeError('atan2(y, x) requires 2 args.', line)
            return _atan2(args[0], args[1])
        if name == 'asin': return _asin(args[0])
        if name == 'acos': return _acos(args[0])
        if name == 'degrees': return _degrees(args[0])
        if name == 'radians': return _radians(args[0])
        if name == 'gcd':
            if len(args) < 2: raise EPLRuntimeError('gcd(a, b) requires 2 args.', line)
            return _gcd(args[0], args[1])
        if name == 'lcm':
            if len(args) < 2: raise EPLRuntimeError('lcm(a, b) requires 2 args.', line)
            return _lcm(args[0], args[1])
        if name == 'factorial': return _factorial(args[0]) if args else 1
        if name == 'is_finite': return _is_finite(args[0]) if args else True
        if name == 'is_nan': return _is_nan(args[0]) if args else False
        if name == 'clamp':
            if len(args) < 3: raise EPLRuntimeError('clamp(value, min, max) requires 3 args.', line)
            return _clamp(args[0], args[1], args[2])
        if name == 'lerp':
            if len(args) < 3: raise EPLRuntimeError('lerp(a, b, t) requires 3 args.', line)
            return _lerp(args[0], args[1], args[2])
        if name == 'sign': return _sign(args[0]) if args else 0

        # ── String/Encoding ──
        if name == 'format':
            if not args: raise EPLRuntimeError('format(template, ...) requires at least a template.', line)
            return _format_string(args[0], *args[1:])
        if name == 'regex_escape': return _regex_escape(args[0]) if args else ''
        if name == 'string_bytes':
            if not args: raise EPLRuntimeError('string_bytes(text) requires text.', line)
            enc = str(args[1]) if len(args) > 1 else 'utf-8'
            return _string_bytes(args[0], enc)
        if name == 'bytes_string':
            if not args: raise EPLRuntimeError('bytes_string(list) requires a byte list.', line)
            enc = str(args[1]) if len(args) > 1 else 'utf-8'
            return _bytes_string(args[0], enc)
        if name == 'hex_encode': return _hex_encode(args[0]) if args else ''
        if name == 'hex_decode': return _hex_decode(args[0]) if args else ''

        # ── HMAC ──
        if name == 'hmac_sha256':
            if len(args) < 2: raise EPLRuntimeError('hmac_sha256(key, message) requires 2 arguments.', line)
            return _hmac_sha256(args[0], args[1])
        if name == 'hmac_sha512':
            if len(args) < 2: raise EPLRuntimeError('hmac_sha512(key, message) requires 2 arguments.', line)
            return _hmac_sha512(args[0], args[1])

        # ── Collections ──
        if name == 'zip_lists': return _zip_lists(*args)
        if name == 'enumerate_list':
            if not args: raise EPLRuntimeError('enumerate_list(list[, start]) requires a list.', line)
            start = int(args[1]) if len(args) > 1 else 0
            return _enumerate_list(args[0], start)
        if name == 'dict_from_lists':
            if len(args) < 2: raise EPLRuntimeError('dict_from_lists(keys, values) requires 2 lists.', line)
            return _dict_from_lists(args[0], args[1])
        if name == 'set_create': return _set_create(*args)
        if name == 'set_add':
            if len(args) < 2: raise EPLRuntimeError('set_add(set, item) requires 2 args.', line)
            return _set_add(args[0], args[1])
        if name == 'set_remove':
            if len(args) < 2: raise EPLRuntimeError('set_remove(set, item) requires 2 args.', line)
            return _set_remove(args[0], args[1])
        if name == 'set_contains':
            if len(args) < 2: raise EPLRuntimeError('set_contains(set, item) requires 2 args.', line)
            return _set_contains(args[0], args[1])
        if name == 'set_union':
            if len(args) < 2: raise EPLRuntimeError('set_union(s1, s2) requires 2 args.', line)
            return _set_union(args[0], args[1])
        if name == 'set_intersection':
            if len(args) < 2: raise EPLRuntimeError('set_intersection(s1, s2) requires 2 args.', line)
            return _set_intersection(args[0], args[1])
        if name == 'set_difference':
            if len(args) < 2: raise EPLRuntimeError('set_difference(s1, s2) requires 2 args.', line)
            return _set_difference(args[0], args[1])

        # ── CSV ──
        if name == 'csv_read':
            if not args: raise EPLRuntimeError('csv_read(path[, has_header]) requires a path.', line)
            has_header = args[1] if len(args) > 1 else True
            return _csv_read(args[0], has_header)
        if name == 'csv_write':
            if len(args) < 2: raise EPLRuntimeError('csv_write(path, data[, headers]) requires path and data.', line)
            headers = args[2] if len(args) > 2 else None
            return _csv_write(args[0], args[1], headers)
        if name == 'csv_parse':
            if not args: raise EPLRuntimeError('csv_parse(text[, has_header]) requires text.', line)
            has_header = args[1] if len(args) > 1 else True
            return _csv_parse(args[0], has_header)

        # ── Threading ──
        if name == 'thread_run':
            if not args: raise EPLRuntimeError('thread_run(function, ...args) requires a function.', line)
            return _thread_run(args[0], *args[1:])
        if name == 'thread_sleep':
            if not args: raise EPLRuntimeError('thread_sleep(seconds) requires seconds.', line)
            return _thread_sleep(args[0])
        if name == 'atomic_counter':
            nm = str(args[0]) if args else 'default'
            inc = args[1] if len(args) > 1 else None
            return _atomic_counter(nm, inc)

        # ── Network ──
        if name == 'socket_connect':
            if len(args) < 2: raise EPLRuntimeError('socket_connect(host, port[, timeout]) requires host and port.', line)
            timeout = float(args[2]) if len(args) > 2 else 10
            return _socket_connect(args[0], args[1], timeout)
        if name == 'socket_send':
            if len(args) < 2: raise EPLRuntimeError('socket_send(id, data) requires id and data.', line)
            return _socket_send(args[0], args[1])
        if name == 'socket_receive':
            if not args: raise EPLRuntimeError('socket_receive(id[, size]) requires a socket ID.', line)
            size = int(args[1]) if len(args) > 1 else 4096
            return _socket_receive(args[0], size)
        if name == 'socket_close':
            if not args: raise EPLRuntimeError('socket_close(id) requires a socket ID.', line)
            return _socket_close(args[0])
        if name == 'dns_lookup':
            if not args: raise EPLRuntimeError('dns_lookup(hostname) requires a hostname.', line)
            return _dns_lookup(args[0])
        if name == 'is_port_open':
            if len(args) < 2: raise EPLRuntimeError('is_port_open(host, port) requires host and port.', line)
            timeout = float(args[2]) if len(args) > 2 else 3
            return _is_port_open(args[0], args[1], timeout)

        # ── System ──
        if name == 'print_error':
            if not args: raise EPLRuntimeError('print_error(msg) requires a message.', line)
            return _print_error(args[0])
        if name == 'read_input':
            prompt = str(args[0]) if args else ''
            return _read_input(prompt)
        if name == 'exit_code':
            if not args: raise EPLRuntimeError('exit_code(code) requires a code.', line)
            return _exit_code(args[0])
        if name == 'args': return _get_args()
        if name == 'timer_start':
            nm = str(args[0]) if args else 'default'
            return _timer_start(nm)
        if name == 'timer_stop':
            nm = str(args[0]) if args else 'default'
            return _timer_stop(nm)

        # ── Concurrency (epl.concurrency) ──
        if name == 'mutex_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            return _conc.create_mutex()
        if name == 'mutex_lock':
            if not args: raise EPLRuntimeError('mutex_lock(mutex[, timeout]) requires a mutex.', line)
            timeout = float(args[1]) if len(args) > 1 else -1
            return args[0].acquire(timeout)
        if name == 'mutex_unlock':
            if not args: raise EPLRuntimeError('mutex_unlock(mutex) requires a mutex.', line)
            args[0].release()
            return None
        if name == 'rwlock_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            return _conc.create_rwlock()
        if name == 'rwlock_read_lock':
            if not args: raise EPLRuntimeError('rwlock_read_lock(rwlock) requires an RWLock.', line)
            args[0].acquire_read()
            return None
        if name == 'rwlock_read_unlock':
            if not args: raise EPLRuntimeError('rwlock_read_unlock(rwlock) requires an RWLock.', line)
            args[0].release_read()
            return None
        if name == 'rwlock_write_lock':
            if not args: raise EPLRuntimeError('rwlock_write_lock(rwlock) requires an RWLock.', line)
            args[0].acquire_write()
            return None
        if name == 'rwlock_write_unlock':
            if not args: raise EPLRuntimeError('rwlock_write_unlock(rwlock) requires an RWLock.', line)
            args[0].release_write()
            return None
        if name == 'channel_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            capacity = int(args[0]) if args else 0
            return _conc.create_channel(capacity)
        if name == 'channel_send':
            if len(args) < 2: raise EPLRuntimeError('channel_send(ch, value[, timeout]) requires channel and value.', line)
            timeout = float(args[2]) if len(args) > 2 else None
            args[0].send(args[1], timeout)
            return None
        if name == 'channel_receive':
            if not args: raise EPLRuntimeError('channel_receive(ch[, timeout]) requires a channel.', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return args[0].receive(timeout)
        if name == 'channel_try_send':
            if len(args) < 2: raise EPLRuntimeError('channel_try_send(ch, value) requires channel and value.', line)
            return args[0].try_send(args[1])
        if name == 'channel_try_receive':
            if not args: raise EPLRuntimeError('channel_try_receive(ch) requires a channel.', line)
            return args[0].try_receive()
        if name == 'channel_close':
            if not args: raise EPLRuntimeError('channel_close(ch) requires a channel.', line)
            args[0].close()
            return None
        if name == 'semaphore_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            count = int(args[0]) if args else 1
            return _conc.create_semaphore(count)
        if name == 'semaphore_acquire':
            if not args: raise EPLRuntimeError('semaphore_acquire(sem[, timeout]) requires a semaphore.', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return args[0].acquire(timeout)
        if name == 'semaphore_release':
            if not args: raise EPLRuntimeError('semaphore_release(sem) requires a semaphore.', line)
            args[0].release()
            return None
        if name == 'atomic_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            initial = int(args[0]) if args else 0
            return _conc.create_atomic(initial)
        if name == 'atomic_get':
            if not args: raise EPLRuntimeError('atomic_get(counter) requires an atomic counter.', line)
            return args[0].get()
        if name == 'atomic_set':
            if len(args) < 2: raise EPLRuntimeError('atomic_set(counter, value) requires counter and value.', line)
            args[0].set(int(args[1]))
            return None
        if name == 'atomic_increment':
            if not args: raise EPLRuntimeError('atomic_increment(counter[, amount]) requires a counter.', line)
            amount = int(args[1]) if len(args) > 1 else 1
            return args[0].increment(amount)
        if name == 'atomic_decrement':
            if not args: raise EPLRuntimeError('atomic_decrement(counter[, amount]) requires a counter.', line)
            amount = int(args[1]) if len(args) > 1 else 1
            return args[0].decrement(amount)
        if name == 'atomic_cas':
            if len(args) < 3: raise EPLRuntimeError('atomic_cas(counter, expected, new) requires 3 args.', line)
            return args[0].compare_and_swap(int(args[1]), int(args[2]))
        if name == 'thread_pool_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            workers = int(args[0]) if args else 4
            return _conc.create_thread_pool(workers)
        if name == 'thread_pool_submit':
            if len(args) < 2: raise EPLRuntimeError('thread_pool_submit(pool, func) requires pool and function.', line)
            return args[0].submit(args[1])
        if name == 'thread_pool_map':
            if len(args) < 3: raise EPLRuntimeError('thread_pool_map(pool, func, items) requires pool, function, and items.', line)
            return args[0].map(args[1], args[2])
        if name == 'thread_pool_shutdown':
            if not args: raise EPLRuntimeError('thread_pool_shutdown(pool) requires a pool.', line)
            wait = bool(args[1]) if len(args) > 1 else True
            args[0].shutdown(wait)
            return None
        if name == 'thread_pool_wait':
            if not args: raise EPLRuntimeError('thread_pool_wait(pool[, timeout]) requires a pool.', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return args[0].wait_all(timeout)
        if name == 'wait_group_create':
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            return _conc.create_wait_group()
        if name == 'wait_group_add':
            if not args: raise EPLRuntimeError('wait_group_add(wg[, count]) requires a wait group.', line)
            count = int(args[1]) if len(args) > 1 else 1
            args[0].add(count)
            return None
        if name == 'wait_group_done':
            if not args: raise EPLRuntimeError('wait_group_done(wg) requires a wait group.', line)
            args[0].done()
            return None
        if name == 'wait_group_wait':
            if not args: raise EPLRuntimeError('wait_group_wait(wg[, timeout]) requires a wait group.', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return args[0].wait(timeout)
        if name == 'parallel_map':
            if len(args) < 2: raise EPLRuntimeError('parallel_map(func, items[, workers]) requires function and items.', line)
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            workers = int(args[2]) if len(args) > 2 else 4
            return _conc.parallel_map(args[0], args[1], workers)
        if name == 'parallel_for_each':
            if len(args) < 2: raise EPLRuntimeError('parallel_for_each(func, items[, workers]) requires function and items.', line)
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            workers = int(args[2]) if len(args) > 2 else 4
            _conc.parallel_for_each(args[0], args[1], workers)
            return None
        if name == 'sleep_ms':
            if not args: raise EPLRuntimeError('sleep_ms(ms) requires milliseconds.', line)
            _conc = _require_module('epl.concurrency', feature_name='Concurrency')
            _conc.sleep_ms(int(args[0]))
            return None

        # ── ORM / Database (epl.database) ──
        if name == 'orm_open':
            if not args: raise EPLRuntimeError('orm_open(dialect[, database, pool_size]) requires a dialect.', line)
            _db_mod = _require_module('epl.database', feature_name='ORM Database')
            dialect = str(args[0])
            database = str(args[1]) if len(args) > 1 else ':memory:'
            pool_size = int(args[2]) if len(args) > 2 else 5
            db = _db_mod.Database(dialect, database, pool_size)
            sid = f'orm_{_new_id()}'
            _db_connections[sid] = db
            return sid
        if name == 'orm_close':
            if not args: raise EPLRuntimeError('orm_close(db_id) requires a database ID.', line)
            sid = str(args[0])
            if sid in _db_connections:
                _db_connections[sid].close()
                del _db_connections[sid]
            return None
        if name == 'orm_define_model':
            if len(args) < 2: raise EPLRuntimeError('orm_define_model(db_id, model_name) requires db_id and name.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model = _db_connections[sid].define_model(str(args[1]))
            return model
        if name == 'orm_add_field':
            if len(args) < 3: raise EPLRuntimeError('orm_add_field(model, name, type[, options]) requires model, name, type.', line)
            _db_mod = _require_module('epl.database', feature_name='ORM Database')
            model = args[0]
            fname = str(args[1])
            ftype = str(args[2])
            opts = _from_epl(args[3]) if len(args) > 3 else {}
            model.add_field(fname, ftype,
                nullable=opts.get('nullable', True),
                unique=opts.get('unique', False),
                default=opts.get('default', None),
            )
            return model
        if name == 'orm_migrate':
            if not args: raise EPLRuntimeError('orm_migrate(db_id) requires a database ID.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            _db_connections[sid].migrate()
            return None
        if name == 'orm_create':
            if len(args) < 3: raise EPLRuntimeError('orm_create(db_id, model, data) requires db_id, model name, data dict.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            data = _from_epl(args[2]) if hasattr(args[2], 'entries') else args[2]
            return _db_connections[sid].create(str(args[1]), data)
        if name == 'orm_find':
            if len(args) < 2: raise EPLRuntimeError('orm_find(db_id, model[, conditions]) requires db_id and model.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            conds = _from_epl(args[2]) if len(args) > 2 and args[2] is not None else None
            results = _db_connections[sid].find(str(args[1]), conds)
            return [_to_epl_dict(r) for r in results]
        if name == 'orm_find_by_id':
            if len(args) < 3: raise EPLRuntimeError('orm_find_by_id(db_id, model, id) requires db_id, model, and id.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            result = _db_connections[sid].find_by_id(str(args[1]), int(args[2]))
            return _to_epl_dict(result) if result else None
        if name == 'orm_update':
            if len(args) < 4: raise EPLRuntimeError('orm_update(db_id, model, id, data) requires 4 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            data = _from_epl(args[3]) if hasattr(args[3], 'entries') else args[3]
            return _db_connections[sid].update(str(args[1]), int(args[2]), data)
        if name == 'orm_delete':
            if len(args) < 3: raise EPLRuntimeError('orm_delete(db_id, model, id) requires db_id, model, and id.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            return _db_connections[sid].delete(str(args[1]), int(args[2]))
        if name == 'orm_delete_where':
            if len(args) < 3: raise EPLRuntimeError('orm_delete_where(db_id, model, conditions) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            conds = _from_epl(args[2]) if hasattr(args[2], 'entries') else args[2]
            return _db_connections[sid].delete_where(str(args[1]), conds)
        if name == 'orm_query':
            if len(args) < 2: raise EPLRuntimeError('orm_query(db_id, model) requires db_id and model name.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            return _db_connections[sid].query(str(args[1]))
        if name == 'orm_raw_query':
            if len(args) < 2: raise EPLRuntimeError('orm_raw_query(db_id, sql[, params]) requires db_id and SQL.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            params = list(args[2]) if len(args) > 2 else None
            results = _db_connections[sid].raw_query(str(args[1]), params)
            return [_to_epl_dict(r) for r in results]
        if name == 'orm_raw_execute':
            if len(args) < 2: raise EPLRuntimeError('orm_raw_execute(db_id, sql[, params]) requires db_id and SQL.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            params = list(args[2]) if len(args) > 2 else None
            return _db_connections[sid].raw_execute(str(args[1]), params)
        if name == 'orm_transaction_begin':
            if not args: raise EPLRuntimeError('orm_transaction_begin(db_id) requires a database ID.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            txn = _db_connections[sid].transaction()
            txn.__enter__()
            txn_id = f'txn_{_new_id()}'
            _db_connections[txn_id] = txn
            return txn_id
        if name == 'orm_transaction_commit':
            if not args: raise EPLRuntimeError('orm_transaction_commit(txn_id) requires a transaction ID.', line)
            txn_id = str(args[0])
            if txn_id in _db_connections:
                txn = _db_connections[txn_id]
                # __exit__(None, None, None) calls commit() internally, don't double-commit
                txn.__exit__(None, None, None)
                del _db_connections[txn_id]
            return None
        if name == 'orm_transaction_rollback':
            if not args: raise EPLRuntimeError('orm_transaction_rollback(txn_id) requires a transaction ID.', line)
            txn_id = str(args[0])
            if txn_id in _db_connections:
                txn = _db_connections[txn_id]
                txn.conn.rollback()
                txn.__exit__(Exception, Exception("rollback"), None)
                del _db_connections[txn_id]
            return None
        if name == 'orm_table_exists':
            if len(args) < 2: raise EPLRuntimeError('orm_table_exists(db_id, table) requires db_id and table name.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            return _db_connections[sid].table_exists(str(args[1]))

        # ── ORM Extensions (Phase 3) ──
        if name == 'orm_has_many':
            if len(args) < 4: raise EPLRuntimeError('orm_has_many(db_id, model, target, foreign_key) requires 4 args.', line)
            sid, model, target, fk = str(args[0]), str(args[1]), str(args[2]), str(args[3])
            rel_key = f'{sid}:{model}'
            if rel_key not in _orm_relations: _orm_relations[rel_key] = {}
            _orm_relations[rel_key][target] = {'type': 'has_many', 'target': target, 'foreign_key': fk}
            return True
        if name == 'orm_belongs_to':
            if len(args) < 4: raise EPLRuntimeError('orm_belongs_to(db_id, model, target, foreign_key) requires 4 args.', line)
            sid, model, target, fk = str(args[0]), str(args[1]), str(args[2]), str(args[3])
            rel_key = f'{sid}:{model}'
            if rel_key not in _orm_relations: _orm_relations[rel_key] = {}
            _orm_relations[rel_key][target] = {'type': 'belongs_to', 'target': target, 'foreign_key': fk}
            return True
        if name == 'orm_with_related':
            if len(args) < 4: raise EPLRuntimeError('orm_with_related(db_id, model, id, relation) requires 4 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model, record_id, relation = str(args[1]), int(args[2]), str(args[3])
            main = _db_connections[sid].find_by_id(model, record_id)
            if not main: return None
            result = dict(main)
            rel_key = f'{sid}:{model}'
            rel_info = _orm_relations.get(rel_key, {}).get(relation)
            if rel_info:
                if rel_info['type'] == 'has_many':
                    related = _db_connections[sid].find(rel_info['target'], {rel_info['foreign_key']: record_id})
                    result[relation] = [dict(r) for r in related]
                elif rel_info['type'] == 'belongs_to':
                    fk_val = main.get(rel_info['foreign_key'])
                    if fk_val:
                        related = _db_connections[sid].find_by_id(rel_info['target'], int(fk_val))
                        result[relation] = dict(related) if related else None
            return _to_epl_dict(result)
        if name == 'orm_paginate':
            if len(args) < 2: raise EPLRuntimeError('orm_paginate(db_id, model[, page, per_page, conditions]) requires db_id and model.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model = str(args[1])
            page = max(1, int(args[2])) if len(args) > 2 else 1
            per_page = max(1, min(int(args[3]), 1000)) if len(args) > 3 else 20
            conds = _from_epl(args[4]) if len(args) > 4 and args[4] is not None else None
            all_records = _db_connections[sid].find(model, conds)
            total = len(all_records)
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            start = (page - 1) * per_page
            items = all_records[start:start + per_page]
            return _to_epl({
                'items': [dict(r) for r in items], 'page': page, 'per_page': per_page,
                'total': total, 'total_pages': total_pages,
                'has_next': page < total_pages, 'has_prev': page > 1,
            })
        if name == 'orm_order_by':
            if len(args) < 3: raise EPLRuntimeError('orm_order_by(db_id, model, field[, direction]) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model_name = str(args[1])
            field = str(args[2])
            direction = str(args[3]).upper() if len(args) > 3 else 'ASC'
            if direction not in ('ASC', 'DESC'): direction = 'ASC'
            tbl = _db_connections[sid].get_model(model_name).table_name
            if not _re.match(r'^[a-zA-Z_]\w*$', tbl): raise EPLRuntimeError(f'Invalid table name: {tbl}', line)
            if not _re.match(r'^[a-zA-Z_]\w*$', field): raise EPLRuntimeError(f'Invalid field name: {field}', line)
            results = _db_connections[sid].raw_query(f'SELECT * FROM "{tbl}" ORDER BY "{field}" {direction}')
            return [_to_epl_dict(r) for r in results]
        if name == 'orm_count_where':
            if len(args) < 3: raise EPLRuntimeError('orm_count_where(db_id, model, conditions) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            from epl.interpreter import EPLDict as _ED
            conds = _from_epl(args[2]) if isinstance(args[2], _ED) else args[2]
            records = _db_connections[sid].find(str(args[1]), conds)
            return len(records)
        if name == 'orm_seed':
            if len(args) < 3: raise EPLRuntimeError('orm_seed(db_id, model, data_list) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model = str(args[1])
            data_list = args[2] if isinstance(args[2], list) else [args[2]]
            count = 0
            for item in data_list:
                from epl.interpreter import EPLDict as _ED2
                data = _from_epl(item) if isinstance(item, _ED2) else item
                _db_connections[sid].create(model, data)
                count += 1
            return count
        if name == 'orm_add_index':
            if len(args) < 3: raise EPLRuntimeError('orm_add_index(db_id, model, fields) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            model_name = str(args[1])
            fields = args[2] if isinstance(args[2], list) else [str(args[2])]
            tbl = _db_connections[sid].get_model(model_name).table_name
            if not _re.match(r'^[a-zA-Z_]\w*$', tbl): raise EPLRuntimeError(f'Invalid table name: {tbl}', line)
            for f in fields:
                if not _re.match(r'^[a-zA-Z_]\w*$', str(f)): raise EPLRuntimeError(f'Invalid field name: {f}', line)
            field_str = ', '.join(f'"{f}"' for f in fields)
            idx_name = f'idx_{tbl}_{"_".join(str(f) for f in fields)}'
            _db_connections[sid].raw_execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tbl}" ({field_str})')
            return True
        if name == 'orm_first':
            if len(args) < 2: raise EPLRuntimeError('orm_first(db_id, model[, conditions]) requires db_id and model.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            from epl.interpreter import EPLDict as _ED3
            conds = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], _ED3) else (args[2] if len(args) > 2 and args[2] is not None else None)
            results = _db_connections[sid].find(str(args[1]), conds)
            return _to_epl_dict(results[0]) if results else None
        if name == 'orm_last':
            if len(args) < 2: raise EPLRuntimeError('orm_last(db_id, model[, conditions]) requires db_id and model.', line)
            sid = str(args[0])
            if sid not in _db_connections: raise EPLRuntimeError(f'Unknown ORM connection: {sid}', line)
            from epl.interpreter import EPLDict as _ED4
            conds = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], _ED4) else (args[2] if len(args) > 2 and args[2] is not None else None)
            results = _db_connections[sid].find(str(args[1]), conds)
            return _to_epl_dict(results[-1]) if results else None

        # ── Advanced Networking (epl.database) ──
        if name == 'http_client_create':
            _db_mod = _require_module('epl.database', feature_name='ORM Database')
            base_url = str(args[0]) if args else ''
            return _db_mod.HTTPClient(base_url)
        if name == 'http_client_get':
            if not args: raise EPLRuntimeError('http_client_get(client, path[, headers]) requires client and path.', line)
            headers = _from_epl(args[2]) if len(args) > 2 else None
            return _to_epl_dict(args[0].get(str(args[1]), headers))
        if name == 'http_client_post':
            if len(args) < 2: raise EPLRuntimeError('http_client_post(client, path[, body, headers]) requires client and path.', line)
            body = str(args[2]) if len(args) > 2 else ''
            headers = _from_epl(args[3]) if len(args) > 3 else None
            return _to_epl_dict(args[0].post(str(args[1]), body, headers))
        if name == 'http_client_put':
            if len(args) < 2: raise EPLRuntimeError('http_client_put(client, path[, body, headers]) requires client and path.', line)
            body = str(args[2]) if len(args) > 2 else ''
            headers = _from_epl(args[3]) if len(args) > 3 else None
            return _to_epl_dict(args[0].put(str(args[1]), body, headers))
        if name == 'http_client_delete':
            if len(args) < 2: raise EPLRuntimeError('http_client_delete(client, path[, headers]) requires client and path.', line)
            headers = _from_epl(args[2]) if len(args) > 2 else None
            return _to_epl_dict(args[0].delete(str(args[1]), headers))
        if name == 'tcp_connect':
            _db_mod = _require_module('epl.database', feature_name='ORM Database')
            if len(args) < 2: raise EPLRuntimeError('tcp_connect(host, port) requires host and port.', line)
            sock = _db_mod.EPLSocket('tcp')
            sock.connect(str(args[0]), int(args[1]))
            sid = f'tcp_{_new_id()}'
            _open_sockets[sid] = sock
            return sid
        if name == 'tcp_send':
            if len(args) < 2: raise EPLRuntimeError('tcp_send(id, data) requires socket id and data.', line)
            sid = str(args[0])
            if sid not in _open_sockets: raise EPLRuntimeError(f'Unknown socket: {sid}', line)
            return _open_sockets[sid].send(str(args[1]))
        if name == 'tcp_receive':
            if not args: raise EPLRuntimeError('tcp_receive(id[, size]) requires a socket ID.', line)
            sid = str(args[0])
            if sid not in _open_sockets: raise EPLRuntimeError(f'Unknown socket: {sid}', line)
            size = int(args[1]) if len(args) > 1 else 4096
            return _open_sockets[sid].receive(size)
        if name == 'tcp_close':
            if not args: raise EPLRuntimeError('tcp_close(id) requires a socket ID.', line)
            sid = str(args[0])
            if sid in _open_sockets:
                _open_sockets[sid].close()
                del _open_sockets[sid]
            return None

        # ══════════════════════════════════════════════════
        #  Real Database (epl.database_real)
        # ══════════════════════════════════════════════════
        if name == 'real_db_connect':
            _db_real = _require_module('epl.database_real', feature_name='Real Database')
            path = str(args[0]) if args else ':memory:'
            db_name = str(args[1]) if len(args) > 1 else 'default'
            db = _db_real.db_connect(path, db_name)
            _real_db_instances[db_name] = db
            return db_name
        if name == 'real_db_get':
            db_name = str(args[0]) if args else 'default'
            if db_name not in _real_db_instances:
                raise EPLRuntimeError(f'No database connection: {db_name}', line)
            return db_name
        if name == 'real_db_close':
            _db_real = _require_module('epl.database_real', feature_name='Real Database')
            db_name = str(args[0]) if args else 'default'
            _db_real.db_close(db_name)
            _real_db_instances.pop(db_name, None)
            return None
        if name == 'real_db_close_all':
            _db_real = _require_module('epl.database_real', feature_name='Real Database')
            _db_real.db_close_all()
            _real_db_instances.clear()
            return None
        if name == 'real_db_execute':
            if len(args) < 2: raise EPLRuntimeError('real_db_execute(db, sql[, params]) requires db and SQL.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            params = tuple(args[2]) if len(args) > 2 else ()
            _real_db_instances[db_name].execute(str(args[1]), params)
            return None
        if name == 'real_db_execute_many':
            if len(args) < 3: raise EPLRuntimeError('real_db_execute_many(db, sql, params_list) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            _real_db_instances[db_name].execute_many(str(args[1]), [list(p) for p in args[2]])
            return None
        if name == 'real_db_query':
            if len(args) < 2: raise EPLRuntimeError('real_db_query(db, sql[, params]) requires db and SQL.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            params = tuple(args[2]) if len(args) > 2 else ()
            results = _real_db_instances[db_name].query(str(args[1]), params)
            return [_to_epl_dict(r) for r in results]
        if name == 'real_db_query_one':
            if len(args) < 2: raise EPLRuntimeError('real_db_query_one(db, sql[, params]) requires db and SQL.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            params = tuple(args[2]) if len(args) > 2 else ()
            result = _real_db_instances[db_name].query_one(str(args[1]), params)
            return _to_epl_dict(result) if result else None
        if name == 'real_db_insert':
            if len(args) < 3: raise EPLRuntimeError('real_db_insert(db, table, record) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            record = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            return _real_db_instances[db_name].insert(str(args[1]), record)
        if name == 'real_db_update':
            if len(args) < 4: raise EPLRuntimeError('real_db_update(db, table, record, where) requires 4 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            record = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            where_arg = _from_epl(args[3]) if hasattr(args[3], 'data') else args[3]
            # If where is a dict, convert to SQL string + params
            if isinstance(where_arg, dict):
                where_parts = [f"{k} = ?" for k in where_arg.keys()]
                where_sql = ' AND '.join(where_parts)
                where_params = tuple(where_arg.values())
            else:
                where_sql = str(where_arg)
                where_params = tuple(args[4]) if len(args) > 4 else ()
            return _real_db_instances[db_name].update(str(args[1]), record, where_sql, where_params)
        if name == 'real_db_delete':
            if len(args) < 3: raise EPLRuntimeError('real_db_delete(db, table, where) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            where_arg = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            if isinstance(where_arg, dict):
                where_parts = [f"{k} = ?" for k in where_arg.keys()]
                where_sql = ' AND '.join(where_parts)
                where_params = tuple(where_arg.values())
            else:
                where_sql = str(where_arg)
                where_params = tuple(args[3]) if len(args) > 3 else ()
            return _real_db_instances[db_name].delete(str(args[1]), where_sql, where_params)
        if name == 'real_db_find_by_id':
            if len(args) < 3: raise EPLRuntimeError('real_db_find_by_id(db, table, id) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            result = _real_db_instances[db_name].find_by_id(str(args[1]), args[2])
            return _to_epl_dict(result) if result else None
        if name == 'real_db_create_table':
            if len(args) < 3: raise EPLRuntimeError('real_db_create_table(db, table, columns) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            cols = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            _real_db_instances[db_name].create_table(str(args[1]), cols)
            return None
        if name == 'real_db_count':
            if len(args) < 2: raise EPLRuntimeError('real_db_count(db, table[, where]) requires db and table.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            where = _from_epl(args[2]) if len(args) > 2 and hasattr(args[2], 'data') else (args[2] if len(args) > 2 else None)
            if where is None:
                return _real_db_instances[db_name].count(str(args[1]))
            elif isinstance(where, dict):
                where_parts = [f"{k} = ?" for k in where.keys()]
                where_sql = ' AND '.join(where_parts)
                where_params = tuple(where.values())
                return _real_db_instances[db_name].count(str(args[1]), where_sql, where_params)
            else:
                return _real_db_instances[db_name].count(str(args[1]), str(where))
        if name == 'real_db_table_exists':
            if len(args) < 2: raise EPLRuntimeError('real_db_table_exists(db, table) requires db and table.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            return _real_db_instances[db_name].table_exists(str(args[1]))
        if name == 'real_db_begin':
            if not args: raise EPLRuntimeError('real_db_begin(db) requires a db name.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            _real_db_instances[db_name]._in_manual_transaction = True
            _real_db_instances[db_name]._conn.execute('BEGIN')
            return None
        if name == 'real_db_commit':
            if not args: raise EPLRuntimeError('real_db_commit(db) requires a db name.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            _real_db_instances[db_name]._conn.commit()
            _real_db_instances[db_name]._in_manual_transaction = False
            return None
        if name == 'real_db_rollback':
            if not args: raise EPLRuntimeError('real_db_rollback(db) requires a db name.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            _real_db_instances[db_name]._conn.rollback()
            _real_db_instances[db_name]._in_manual_transaction = False
            return None
        if name == 'real_db_migrate':
            if len(args) < 3: raise EPLRuntimeError('real_db_migrate(db, version, sql) requires 3 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            _real_db_instances[db_name].migrate(int(args[1]), str(args[2]))
            return None
        if name == 'real_db_table':
            if len(args) < 2: raise EPLRuntimeError('real_db_table(db, table_name) requires 2 args.', line)
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            # Returns a query builder as EPLDict with methods
            qb = _real_db_instances[db_name].table(str(args[1]))
            qb_id = f'qb_{_new_id()}'
            _db_connections[qb_id] = qb  # reuse connections dict for query builders
            return qb_id
        if name == 'real_db_model_define':
            if len(args) < 3: raise EPLRuntimeError('real_db_model_define(db, model_name, fields) requires 3 args.', line)
            _db_real = _require_module('epl.database_real', feature_name='Real Database')
            db_name = str(args[0])
            if db_name not in _real_db_instances: raise EPLRuntimeError(f'No database connection: {db_name}', line)
            fields = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            model_name = str(args[1])
            model = _db_real.Model(_real_db_instances[db_name], model_name, fields)
            _real_db_models[f'{db_name}:{model_name}'] = model
            return model_name
        if name == 'real_db_model_create':
            if len(args) < 3: raise EPLRuntimeError('real_db_model_create(db, model, data) requires 3 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            data = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            result = _real_db_models[key].create(data)
            return _to_epl_dict(result) if isinstance(result, dict) else result
        if name == 'real_db_model_find':
            if len(args) < 3: raise EPLRuntimeError('real_db_model_find(db, model, id) requires 3 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            result = _real_db_models[key].find(args[2])
            return _to_epl_dict(result) if result else None
        if name == 'real_db_model_all':
            if len(args) < 2: raise EPLRuntimeError('real_db_model_all(db, model) requires 2 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            return [_to_epl_dict(r) for r in _real_db_models[key].all()]
        if name == 'real_db_model_where':
            if len(args) < 3: raise EPLRuntimeError('real_db_model_where(db, model, conditions) requires 3 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            conds = _from_epl(args[2]) if hasattr(args[2], 'data') else args[2]
            return [_to_epl_dict(r) for r in _real_db_models[key].where(conds)]
        if name == 'real_db_model_first':
            if len(args) < 2: raise EPLRuntimeError('real_db_model_first(db, model) requires 2 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            result = _real_db_models[key].first()
            return _to_epl_dict(result) if result else None
        if name == 'real_db_model_update':
            if len(args) < 4: raise EPLRuntimeError('real_db_model_update(db, model, id, data) requires 4 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            data = _from_epl(args[3]) if hasattr(args[3], 'data') else args[3]
            return _real_db_models[key].update_record(args[2], data)
        if name == 'real_db_model_delete':
            if len(args) < 3: raise EPLRuntimeError('real_db_model_delete(db, model, id) requires 3 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            return _real_db_models[key].delete_record(args[2])
        if name == 'real_db_model_count':
            if len(args) < 2: raise EPLRuntimeError('real_db_model_count(db, model) requires 2 args.', line)
            key = f'{str(args[0])}:{str(args[1])}'
            if key not in _real_db_models: raise EPLRuntimeError(f'Model not defined: {args[1]}', line)
            return _real_db_models[key].count()

        # ══════════════════════════════════════════════════
        #  Real Networking (epl.networking)
        # ══════════════════════════════════════════════════
        if name == 'net_dns_lookup':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_dns_lookup(hostname) requires a hostname.', line)
            return _net.dns_lookup(str(args[0]))
        if name == 'net_dns_lookup_all':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_dns_lookup_all(hostname) requires a hostname.', line)
            return _net.dns_lookup_all(str(args[0]))
        if name == 'net_reverse_dns':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_reverse_dns(ip) requires an IP address.', line)
            return _net.reverse_dns(str(args[0]))
        if name == 'net_is_port_open':
            _net = _require_module('epl.networking', feature_name='Networking')
            if len(args) < 2: raise EPLRuntimeError('net_is_port_open(host, port[, timeout]) requires host and port.', line)
            timeout = float(args[2]) if len(args) > 2 else 2.0
            return _net.is_port_open(str(args[0]), int(args[1]), timeout)
        if name == 'net_local_ip':
            _net = _require_module('epl.networking', feature_name='Networking')
            return _net.get_local_ip()
        if name == 'net_hostname':
            _net = _require_module('epl.networking', feature_name='Networking')
            return _net.get_hostname()
        if name == 'net_http_get':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_http_get(url[, headers, timeout]) requires a URL.', line)
            headers = _from_epl(args[1]) if len(args) > 1 and args[1] is not None else None
            timeout = float(args[2]) if len(args) > 2 else 30.0
            resp = _net.http_get(str(args[0]), headers, timeout)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_post':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_http_post(url[, data, headers, timeout]) requires a URL.', line)
            data = args[1] if len(args) > 1 else None
            headers = _from_epl(args[2]) if len(args) > 2 and args[2] is not None else None
            timeout = float(args[3]) if len(args) > 3 else 30.0
            resp = _net.http_post(str(args[0]), data, headers, timeout)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_put':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_http_put(url[, data, headers, timeout]) requires a URL.', line)
            data = args[1] if len(args) > 1 else None
            headers = _from_epl(args[2]) if len(args) > 2 and args[2] is not None else None
            timeout = float(args[3]) if len(args) > 3 else 30.0
            resp = _net.http_put(str(args[0]), data, headers, timeout)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_delete':
            _net = _require_module('epl.networking', feature_name='Networking')
            if not args: raise EPLRuntimeError('net_http_delete(url[, headers, timeout]) requires a URL.', line)
            headers = _from_epl(args[1]) if len(args) > 1 and args[1] is not None else None
            timeout = float(args[2]) if len(args) > 2 else 30.0
            resp = _net.http_delete(str(args[0]), headers, timeout)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_client':
            _net = _require_module('epl.networking', feature_name='Networking')
            base_url = str(args[0]) if args else ''
            timeout = float(args[1]) if len(args) > 1 else 30.0
            client = _net.HTTPClient(base_url, timeout)
            cid = f'httpc_{_new_id()}'
            _net_http_clients[cid] = client
            return cid
        if name == 'net_http_client_get':
            if not args: raise EPLRuntimeError('net_http_client_get(client_id, path[, headers]) requires client and path.', line)
            cid = str(args[0])
            if cid not in _net_http_clients: raise EPLRuntimeError(f'Unknown HTTP client: {cid}', line)
            headers = _from_epl(args[2]) if len(args) > 2 else None
            resp = _net_http_clients[cid].get(str(args[1]), headers)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_client_post':
            if len(args) < 2: raise EPLRuntimeError('net_http_client_post(client, path[, body, headers]) requires client and path.', line)
            cid = str(args[0])
            if cid not in _net_http_clients: raise EPLRuntimeError(f'Unknown HTTP client: {cid}', line)
            body = args[2] if len(args) > 2 else None
            headers = _from_epl(args[3]) if len(args) > 3 else None
            resp = _net_http_clients[cid].post(str(args[1]), body, headers)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_client_put':
            if len(args) < 2: raise EPLRuntimeError('net_http_client_put(client, path[, body, headers]) requires client and path.', line)
            cid = str(args[0])
            if cid not in _net_http_clients: raise EPLRuntimeError(f'Unknown HTTP client: {cid}', line)
            body = args[2] if len(args) > 2 else None
            headers = _from_epl(args[3]) if len(args) > 3 else None
            resp = _net_http_clients[cid].put(str(args[1]), body, headers)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_http_client_delete':
            if len(args) < 2: raise EPLRuntimeError('net_http_client_delete(client, path[, headers]) requires client and path.', line)
            cid = str(args[0])
            if cid not in _net_http_clients: raise EPLRuntimeError(f'Unknown HTTP client: {cid}', line)
            headers = _from_epl(args[2]) if len(args) > 2 else None
            resp = _net_http_clients[cid].delete(str(args[1]), headers)
            return _to_epl_dict({'status': resp.status, 'body': resp.text, 'headers': dict(resp.headers), 'ok': resp.ok})
        if name == 'net_tcp_connect':
            _net = _require_module('epl.networking', feature_name='Networking')
            if len(args) < 2: raise EPLRuntimeError('net_tcp_connect(host, port[, timeout, ssl]) requires host and port.', line)
            timeout = float(args[2]) if len(args) > 2 else 30.0
            use_ssl = bool(args[3]) if len(args) > 3 else False
            conn = _net.tcp_connect(str(args[0]), int(args[1]), timeout, use_ssl)
            cid = f'ntcp_{_new_id()}'
            _net_tcp_connections[cid] = conn
            return cid
        if name == 'net_tcp_server':
            _net = _require_module('epl.networking', feature_name='Networking')
            host = str(args[0]) if args else '0.0.0.0'
            port = int(args[1]) if len(args) > 1 else 8080
            server = _net.TCPServer(host, port)
            sid = f'tsrv_{_new_id()}'
            _net_tcp_servers[sid] = server
            return sid
        if name == 'net_tcp_send':
            if len(args) < 2: raise EPLRuntimeError('net_tcp_send(conn_id, data) requires connection and data.', line)
            cid = str(args[0])
            if cid not in _net_tcp_connections: raise EPLRuntimeError(f'Unknown TCP connection: {cid}', line)
            return _net_tcp_connections[cid].send(str(args[1]))
        if name == 'net_tcp_receive':
            if not args: raise EPLRuntimeError('net_tcp_receive(conn_id[, size]) requires a connection ID.', line)
            cid = str(args[0])
            if cid not in _net_tcp_connections: raise EPLRuntimeError(f'Unknown TCP connection: {cid}', line)
            size = int(args[1]) if len(args) > 1 else 4096
            return _net_tcp_connections[cid].receive(size)
        if name == 'net_tcp_receive_line':
            if not args: raise EPLRuntimeError('net_tcp_receive_line(conn_id) requires a connection ID.', line)
            cid = str(args[0])
            if cid not in _net_tcp_connections: raise EPLRuntimeError(f'Unknown TCP connection: {cid}', line)
            return _net_tcp_connections[cid].receive_line()
        if name == 'net_tcp_close':
            if not args: raise EPLRuntimeError('net_tcp_close(conn_id) requires a connection ID.', line)
            cid = str(args[0])
            if cid in _net_tcp_connections:
                _net_tcp_connections[cid].close()
                del _net_tcp_connections[cid]
            return None
        if name == 'net_udp_socket':
            _net = _require_module('epl.networking', feature_name='Networking')
            sock = _net.udp_socket()
            sid = f'nudp_{_new_id()}'
            _net_udp_sockets[sid] = sock
            return sid
        if name == 'net_udp_bind':
            if len(args) < 3: raise EPLRuntimeError('net_udp_bind(sock_id, host, port) requires 3 args.', line)
            sid = str(args[0])
            if sid not in _net_udp_sockets: raise EPLRuntimeError(f'Unknown UDP socket: {sid}', line)
            _net_udp_sockets[sid].bind(str(args[1]), int(args[2]))
            return None
        if name == 'net_udp_send_to':
            if len(args) < 4: raise EPLRuntimeError('net_udp_send_to(sock_id, data, host, port) requires 4 args.', line)
            sid = str(args[0])
            if sid not in _net_udp_sockets: raise EPLRuntimeError(f'Unknown UDP socket: {sid}', line)
            return _net_udp_sockets[sid].send_to(str(args[1]), str(args[2]), int(args[3]))
        if name == 'net_udp_receive_from':
            if not args: raise EPLRuntimeError('net_udp_receive_from(sock_id[, size]) requires a socket ID.', line)
            sid = str(args[0])
            if sid not in _net_udp_sockets: raise EPLRuntimeError(f'Unknown UDP socket: {sid}', line)
            size = int(args[1]) if len(args) > 1 else 4096
            data, addr = _net_udp_sockets[sid].receive_from(size)
            return _to_epl_dict({'data': data, 'host': addr[0], 'port': addr[1]})
        if name == 'net_udp_close':
            if not args: raise EPLRuntimeError('net_udp_close(sock_id) requires a socket ID.', line)
            sid = str(args[0])
            if sid in _net_udp_sockets:
                _net_udp_sockets[sid].close()
                del _net_udp_sockets[sid]
            return None

        # ══════════════════════════════════════════════════
        #  Real Concurrency (epl.concurrency_real)
        # ══════════════════════════════════════════════════
        if name == 'real_thread_run':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if not args: raise EPLRuntimeError('real_thread_run(fn[, args...]) requires a callable.', line)
            fn = args[0]
            fn_args = tuple(args[1:])
            # Wrap EPL function/lambda for Python threading
            if callable(fn):
                t = _conc_real.run_in_thread(fn, *fn_args)
            else:
                raise EPLRuntimeError('real_thread_run() first argument must be callable.', line)
            tid = f'thr_{_new_id()}'
            _real_threads[tid] = t
            return tid
        if name == 'real_thread_join':
            if not args: raise EPLRuntimeError('real_thread_join(thread_id[, timeout]) requires a thread ID.', line)
            tid = str(args[0])
            if tid not in _real_threads: raise EPLRuntimeError(f'Unknown thread: {tid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            _real_threads[tid].join(timeout)
            t = _real_threads[tid]
            if t.error:
                raise EPLRuntimeError(f'Thread {tid} raised: {t.error}', line)
            return t.result
        if name == 'real_thread_is_alive':
            if not args: raise EPLRuntimeError('real_thread_is_alive(thread_id) requires a thread ID.', line)
            tid = str(args[0])
            if tid not in _real_threads: return False
            return _real_threads[tid].is_alive
        if name == 'real_thread_pool_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            workers = int(args[0]) if args else None
            pool = _conc_real.ThreadPool(workers)
            pid = f'tpool_{_new_id()}'
            _real_thread_pools[pid] = pool
            return pid
        if name == 'real_thread_pool_submit':
            if len(args) < 2: raise EPLRuntimeError('real_thread_pool_submit(pool_id, fn[, args...]) requires pool and fn.', line)
            pid = str(args[0])
            if pid not in _real_thread_pools: raise EPLRuntimeError(f'Unknown thread pool: {pid}', line)
            fn = args[1]
            fn_args = tuple(args[2:])
            future = _real_thread_pools[pid].submit(fn, *fn_args)
            fid = f'fut_{_new_id()}'
            _db_connections[fid] = future  # reuse for storage
            return fid
        if name == 'real_thread_pool_map':
            if len(args) < 3: raise EPLRuntimeError('real_thread_pool_map(pool_id, fn, items) requires pool, fn, items.', line)
            pid = str(args[0])
            if pid not in _real_thread_pools: raise EPLRuntimeError(f'Unknown thread pool: {pid}', line)
            return list(_real_thread_pools[pid].map(args[1], list(args[2])))
        if name == 'real_thread_pool_shutdown':
            if not args: raise EPLRuntimeError('real_thread_pool_shutdown(pool_id) requires a pool ID.', line)
            pid = str(args[0])
            if pid in _real_thread_pools:
                _real_thread_pools[pid].shutdown()
                del _real_thread_pools[pid]
            return None
        if name == 'real_mutex_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            m = _conc_real.Mutex()
            mid = f'mtx_{_new_id()}'
            _real_mutexes[mid] = m
            return mid
        if name == 'real_mutex_lock':
            if not args: raise EPLRuntimeError('real_mutex_lock(mutex_id[, timeout]) requires a mutex ID.', line)
            mid = str(args[0])
            if mid not in _real_mutexes: raise EPLRuntimeError(f'Unknown mutex: {mid}', line)
            timeout = float(args[1]) if len(args) > 1 else -1
            return _real_mutexes[mid].acquire(timeout)
        if name == 'real_mutex_unlock':
            if not args: raise EPLRuntimeError('real_mutex_unlock(mutex_id) requires a mutex ID.', line)
            mid = str(args[0])
            if mid not in _real_mutexes: raise EPLRuntimeError(f'Unknown mutex: {mid}', line)
            _real_mutexes[mid].release()
            return None
        if name == 'real_rwlock_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            rw = _conc_real.RWLock()
            rid = f'rwl_{_new_id()}'
            _real_rwlocks[rid] = rw
            return rid
        if name == 'real_rwlock_read_lock':
            if not args: raise EPLRuntimeError('real_rwlock_read_lock(rwlock_id) requires a RWLock ID.', line)
            rid = str(args[0])
            if rid not in _real_rwlocks: raise EPLRuntimeError(f'Unknown RWLock: {rid}', line)
            _real_rwlocks[rid].acquire_read()
            return None
        if name == 'real_rwlock_read_unlock':
            if not args: raise EPLRuntimeError('real_rwlock_read_unlock(rwlock_id) requires a RWLock ID.', line)
            rid = str(args[0])
            if rid not in _real_rwlocks: raise EPLRuntimeError(f'Unknown RWLock: {rid}', line)
            _real_rwlocks[rid].release_read()
            return None
        if name == 'real_rwlock_write_lock':
            if not args: raise EPLRuntimeError('real_rwlock_write_lock(rwlock_id) requires a RWLock ID.', line)
            rid = str(args[0])
            if rid not in _real_rwlocks: raise EPLRuntimeError(f'Unknown RWLock: {rid}', line)
            _real_rwlocks[rid].acquire_write()
            return None
        if name == 'real_rwlock_write_unlock':
            if not args: raise EPLRuntimeError('real_rwlock_write_unlock(rwlock_id) requires a RWLock ID.', line)
            rid = str(args[0])
            if rid not in _real_rwlocks: raise EPLRuntimeError(f'Unknown RWLock: {rid}', line)
            _real_rwlocks[rid].release_write()
            return None
        if name == 'real_semaphore_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            count = int(args[0]) if args else 1
            s = _conc_real.Semaphore(count)
            sid = f'sem_{_new_id()}'
            _real_semaphores[sid] = s
            return sid
        if name == 'real_semaphore_acquire':
            if not args: raise EPLRuntimeError('real_semaphore_acquire(sem_id[, timeout]) requires a semaphore ID.', line)
            sid = str(args[0])
            if sid not in _real_semaphores: raise EPLRuntimeError(f'Unknown semaphore: {sid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return _real_semaphores[sid].acquire(timeout)
        if name == 'real_semaphore_release':
            if not args: raise EPLRuntimeError('real_semaphore_release(sem_id) requires a semaphore ID.', line)
            sid = str(args[0])
            if sid not in _real_semaphores: raise EPLRuntimeError(f'Unknown semaphore: {sid}', line)
            _real_semaphores[sid].release()
            return None
        if name == 'real_barrier_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if not args: raise EPLRuntimeError('real_barrier_create(parties) requires party count.', line)
            b = _conc_real.Barrier(int(args[0]))
            bid = f'bar_{_new_id()}'
            _real_barriers[bid] = b
            return bid
        if name == 'real_barrier_wait':
            if not args: raise EPLRuntimeError('real_barrier_wait(barrier_id[, timeout]) requires a barrier ID.', line)
            bid = str(args[0])
            if bid not in _real_barriers: raise EPLRuntimeError(f'Unknown barrier: {bid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return _real_barriers[bid].wait(timeout)
        if name == 'real_barrier_reset':
            if not args: raise EPLRuntimeError('real_barrier_reset(barrier_id) requires a barrier ID.', line)
            bid = str(args[0])
            if bid not in _real_barriers: raise EPLRuntimeError(f'Unknown barrier: {bid}', line)
            _real_barriers[bid].reset()
            return None
        if name == 'real_event_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            e = _conc_real.Event()
            eid = f'evt_{_new_id()}'
            _real_events[eid] = e
            return eid
        if name == 'real_event_set':
            if not args: raise EPLRuntimeError('real_event_set(event_id) requires an event ID.', line)
            eid = str(args[0])
            if eid not in _real_events: raise EPLRuntimeError(f'Unknown event: {eid}', line)
            _real_events[eid].set()
            return None
        if name == 'real_event_clear':
            if not args: raise EPLRuntimeError('real_event_clear(event_id) requires an event ID.', line)
            eid = str(args[0])
            if eid not in _real_events: raise EPLRuntimeError(f'Unknown event: {eid}', line)
            _real_events[eid].clear()
            return None
        if name == 'real_event_wait':
            if not args: raise EPLRuntimeError('real_event_wait(event_id[, timeout]) requires an event ID.', line)
            eid = str(args[0])
            if eid not in _real_events: raise EPLRuntimeError(f'Unknown event: {eid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return _real_events[eid].wait(timeout)
        if name == 'real_event_is_set':
            if not args: raise EPLRuntimeError('real_event_is_set(event_id) requires an event ID.', line)
            eid = str(args[0])
            if eid not in _real_events: raise EPLRuntimeError(f'Unknown event: {eid}', line)
            return _real_events[eid].is_set
        if name == 'real_channel_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            capacity = int(args[0]) if args else 0
            ch = _conc_real.Channel(capacity)
            cid = f'ch_{_new_id()}'
            _real_channels[cid] = ch
            return cid
        if name == 'real_channel_send':
            if len(args) < 2: raise EPLRuntimeError('real_channel_send(channel_id, value) requires channel and value.', line)
            cid = str(args[0])
            if cid not in _real_channels: raise EPLRuntimeError(f'Unknown channel: {cid}', line)
            _real_channels[cid].send(args[1])
            return None
        if name == 'real_channel_receive':
            if not args: raise EPLRuntimeError('real_channel_receive(channel_id[, timeout]) requires a channel ID.', line)
            cid = str(args[0])
            if cid not in _real_channels: raise EPLRuntimeError(f'Unknown channel: {cid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return _real_channels[cid].receive(timeout)
        if name == 'real_channel_try_send':
            if len(args) < 2: raise EPLRuntimeError('real_channel_try_send(channel_id, value) requires channel and value.', line)
            cid = str(args[0])
            if cid not in _real_channels: raise EPLRuntimeError(f'Unknown channel: {cid}', line)
            return _real_channels[cid].try_send(args[1])
        if name == 'real_channel_try_receive':
            if not args: raise EPLRuntimeError('real_channel_try_receive(channel_id) requires a channel ID.', line)
            cid = str(args[0])
            if cid not in _real_channels: raise EPLRuntimeError(f'Unknown channel: {cid}', line)
            return _real_channels[cid].try_receive()
        if name == 'real_channel_close':
            if not args: raise EPLRuntimeError('real_channel_close(channel_id) requires a channel ID.', line)
            cid = str(args[0])
            if cid in _real_channels:
                _real_channels[cid].close()
                del _real_channels[cid]
            return None
        if name == 'real_atomic_int':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            val = int(args[0]) if args else 0
            a = _conc_real.AtomicInt(val)
            aid = f'aint_{_new_id()}'
            _real_atomic_ints[aid] = a
            return aid
        if name == 'real_atomic_int_get':
            if not args: raise EPLRuntimeError('real_atomic_int_get(id) requires an atomic int ID.', line)
            aid = str(args[0])
            if aid not in _real_atomic_ints: raise EPLRuntimeError(f'Unknown atomic int: {aid}', line)
            return _real_atomic_ints[aid].get()
        if name == 'real_atomic_int_set':
            if len(args) < 2: raise EPLRuntimeError('real_atomic_int_set(id, value) requires ID and value.', line)
            aid = str(args[0])
            if aid not in _real_atomic_ints: raise EPLRuntimeError(f'Unknown atomic int: {aid}', line)
            _real_atomic_ints[aid].set(int(args[1]))
            return None
        if name == 'real_atomic_int_inc':
            if not args: raise EPLRuntimeError('real_atomic_int_inc(id[, delta]) requires an atomic int ID.', line)
            aid = str(args[0])
            if aid not in _real_atomic_ints: raise EPLRuntimeError(f'Unknown atomic int: {aid}', line)
            delta = int(args[1]) if len(args) > 1 else 1
            return _real_atomic_ints[aid].increment(delta)
        if name == 'real_atomic_int_dec':
            if not args: raise EPLRuntimeError('real_atomic_int_dec(id[, delta]) requires an atomic int ID.', line)
            aid = str(args[0])
            if aid not in _real_atomic_ints: raise EPLRuntimeError(f'Unknown atomic int: {aid}', line)
            delta = int(args[1]) if len(args) > 1 else 1
            return _real_atomic_ints[aid].decrement(delta)
        if name == 'real_atomic_int_cas':
            if len(args) < 3: raise EPLRuntimeError('real_atomic_int_cas(id, expected, new) requires 3 args.', line)
            aid = str(args[0])
            if aid not in _real_atomic_ints: raise EPLRuntimeError(f'Unknown atomic int: {aid}', line)
            return _real_atomic_ints[aid].compare_and_swap(int(args[1]), int(args[2]))
        if name == 'real_atomic_bool':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            val = bool(args[0]) if args else False
            a = _conc_real.AtomicBool(val)
            aid = f'abool_{_new_id()}'
            _real_atomic_bools[aid] = a
            return aid
        if name == 'real_atomic_bool_get':
            if not args: raise EPLRuntimeError('real_atomic_bool_get(id) requires an atomic bool ID.', line)
            aid = str(args[0])
            if aid not in _real_atomic_bools: raise EPLRuntimeError(f'Unknown atomic bool: {aid}', line)
            return _real_atomic_bools[aid].get()
        if name == 'real_atomic_bool_set':
            if len(args) < 2: raise EPLRuntimeError('real_atomic_bool_set(id, value) requires ID and value.', line)
            aid = str(args[0])
            if aid not in _real_atomic_bools: raise EPLRuntimeError(f'Unknown atomic bool: {aid}', line)
            _real_atomic_bools[aid].set(bool(args[1]))
            return None
        if name == 'real_atomic_bool_toggle':
            if not args: raise EPLRuntimeError('real_atomic_bool_toggle(id) requires an atomic bool ID.', line)
            aid = str(args[0])
            if aid not in _real_atomic_bools: raise EPLRuntimeError(f'Unknown atomic bool: {aid}', line)
            return _real_atomic_bools[aid].toggle()
        if name == 'real_waitgroup_create':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            wg = _conc_real.WaitGroup()
            wid = f'wg_{_new_id()}'
            _real_waitgroups[wid] = wg
            return wid
        if name == 'real_waitgroup_add':
            if not args: raise EPLRuntimeError('real_waitgroup_add(wg_id[, count]) requires a waitgroup ID.', line)
            wid = str(args[0])
            if wid not in _real_waitgroups: raise EPLRuntimeError(f'Unknown waitgroup: {wid}', line)
            count = int(args[1]) if len(args) > 1 else 1
            _real_waitgroups[wid].add(count)
            return None
        if name == 'real_waitgroup_done':
            if not args: raise EPLRuntimeError('real_waitgroup_done(wg_id) requires a waitgroup ID.', line)
            wid = str(args[0])
            if wid not in _real_waitgroups: raise EPLRuntimeError(f'Unknown waitgroup: {wid}', line)
            _real_waitgroups[wid].done()
            return None
        if name == 'real_waitgroup_wait':
            if not args: raise EPLRuntimeError('real_waitgroup_wait(wg_id[, timeout]) requires a waitgroup ID.', line)
            wid = str(args[0])
            if wid not in _real_waitgroups: raise EPLRuntimeError(f'Unknown waitgroup: {wid}', line)
            timeout = float(args[1]) if len(args) > 1 else None
            return _real_waitgroups[wid].wait(timeout)
        if name == 'real_parallel_map':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if len(args) < 2: raise EPLRuntimeError('real_parallel_map(fn, items[, workers]) requires fn and items.', line)
            workers = int(args[2]) if len(args) > 2 else None
            return _conc_real.parallel_map(args[0], list(args[1]), workers)
        if name == 'real_parallel_for_each':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if len(args) < 2: raise EPLRuntimeError('real_parallel_for_each(fn, items[, workers]) requires fn and items.', line)
            workers = int(args[2]) if len(args) > 2 else None
            _conc_real.parallel_for_each(args[0], list(args[1]), workers)
            return None
        if name == 'real_parallel_filter':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if len(args) < 2: raise EPLRuntimeError('real_parallel_filter(fn, items[, workers]) requires fn and items.', line)
            workers = int(args[2]) if len(args) > 2 else None
            return _conc_real.parallel_filter(args[0], list(args[1]), workers)
        if name == 'real_race':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            return _conc_real.race(*args)
        if name == 'real_all_settled':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            results = _conc_real.all_settled(*args)
            return [_to_epl_dict({'result': r, 'error': str(e) if e else None}) for r, e in results]
        if name == 'real_sleep':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if not args: raise EPLRuntimeError('real_sleep(seconds) requires a duration.', line)
            _conc_real.sleep(float(args[0]))
            return None
        if name == 'real_sleep_ms':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if not args: raise EPLRuntimeError('real_sleep_ms(ms) requires milliseconds.', line)
            _conc_real.sleep_ms(int(args[0]))
            return None
        if name == 'real_cpu_count':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            return _conc_real.cpu_count()
        if name == 'real_current_thread':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            return _conc_real.current_thread_name()
        if name == 'real_active_threads':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            return _conc_real.active_thread_count()
        if name == 'real_process_run':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if not args: raise EPLRuntimeError('real_process_run(command[, timeout]) requires a command.', line)
            timeout = float(args[1]) if len(args) > 1 else None
            result = _conc_real.run_command(str(args[0]), timeout=timeout)
            return _to_epl_dict({'exit_code': result.exit_code, 'stdout': result.stdout, 'stderr': result.stderr, 'ok': result.ok})
        if name == 'real_timer':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if len(args) < 2: raise EPLRuntimeError('real_timer(delay, fn) requires delay and function.', line)
            t = _conc_real.Timer(float(args[0]), args[1])
            t.start()
            return None
        if name == 'real_interval':
            _conc_real = _require_module('epl.concurrency_real', feature_name='Real Concurrency')
            if len(args) < 2: raise EPLRuntimeError('real_interval(interval, fn) requires interval and function.', line)
            iv = _conc_real.Interval(float(args[0]), args[1])
            iv.start()
            ivid = f'iv_{_new_id()}'
            _real_intervals[ivid] = iv
            return ivid
        if name == 'real_interval_stop':
            if not args: raise EPLRuntimeError('real_interval_stop(interval_id) requires an interval ID.', line)
            ivid = str(args[0])
            if ivid in _real_intervals:
                _real_intervals[ivid].stop()
                del _real_intervals[ivid]
            return None

        # ══════════════════════════════════════════════════
        #  Bytecode VM (epl.vm)
        # ══════════════════════════════════════════════════
        if name == 'vm_run':
            from epl.vm import compile_and_run
            if not args: raise EPLRuntimeError('vm_run(source) requires EPL source code.', line)
            result = compile_and_run(str(args[0]))
            return _to_epl_dict(result)
        if name == 'vm_compile':
            from epl.vm import compile_to_bytecode
            if not args: raise EPLRuntimeError('vm_compile(source) requires EPL source code.', line)
            result = compile_to_bytecode(str(args[0]))
            return _to_epl_dict(result)
        if name == 'vm_disassemble':
            from epl.vm import disassemble
            if not args: raise EPLRuntimeError('vm_disassemble(source) requires EPL source code.', line)
            return disassemble(str(args[0]))

        # ══════════════════════════════════════════════════════
        #  Phase 2: Production Standard Library
        # ══════════════════════════════════════════════════════

        # ── JSON (extended) ──
        if name == 'json_valid':
            if not args: raise EPLRuntimeError('json_valid(text) requires a string.', line)
            try:
                _json.loads(str(args[0]))
                return True
            except (ValueError, _json.JSONDecodeError):
                return False
        if name == 'json_merge':
            if len(args) < 2: raise EPLRuntimeError('json_merge(obj1, obj2) requires two maps.', line)
            a, b = _from_epl(args[0]), _from_epl(args[1])
            if not isinstance(a, dict) or not isinstance(b, dict):
                raise EPLRuntimeError('json_merge requires two maps.', line)
            merged = {**a, **b}
            return _to_epl(merged)
        if name == 'json_query':
            if len(args) < 2: raise EPLRuntimeError('json_query(obj, path) requires object and path string.', line)
            obj = _from_epl(args[0])
            path = str(args[1])
            parts = path.strip('.').split('.')
            cur = obj
            for p in parts:
                if not p:
                    continue
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                elif isinstance(cur, list):
                    try:
                        cur = cur[int(p)]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
            return _to_epl(cur)

        # ── Crypto (extended) ──
        if name == 'hash_sha1':
            if not args: raise EPLRuntimeError('hash_sha1(text) requires a string.', line)
            return _hashlib.sha1(str(args[0]).encode()).hexdigest()
        if name == 'hash_sha384':
            if not args: raise EPLRuntimeError('hash_sha384(text) requires a string.', line)
            return _hashlib.sha384(str(args[0]).encode()).hexdigest()
        if name == 'hash_file':
            if len(args) < 1: raise EPLRuntimeError('hash_file(path[, algo]) requires a file path.', line)
            algo = str(args[1]) if len(args) > 1 else 'sha256'
            h = _hashlib.new(algo)
            with open(str(args[0]), 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        if name == 'secure_random_bytes':
            if not args: raise EPLRuntimeError('secure_random_bytes(n) requires byte count.', line)
            n = int(args[0])
            if n < 0 or n > 1048576:
                raise EPLRuntimeError('secure_random_bytes: count must be 0..1048576', line)
            return _os.urandom(n).hex()
        if name == 'secure_random_int':
            if len(args) < 2: raise EPLRuntimeError('secure_random_int(min, max) requires bounds.', line)
            import secrets
            return secrets.randbelow(int(args[1]) - int(args[0]) + 1) + int(args[0])
        if name == 'aes_encrypt':
            if len(args) < 2: raise EPLRuntimeError('aes_encrypt(plaintext, key) requires text and key.', line)
            plaintext = str(args[0]).encode('utf-8')
            key = _hashlib.sha256(str(args[1]).encode('utf-8')).digest()
            iv = _os.urandom(16)
            try:
                # Real AES-CBC via pycryptodome
                from Crypto.Cipher import AES  # type: ignore[import-untyped]
                from Crypto.Util.Padding import pad  # type: ignore[import-untyped]
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct = cipher.encrypt(pad(plaintext, AES.block_size))
            except ImportError:
                # Fallback: AES-CBC via cryptography library
                try:
                    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore[import-untyped]
                    from cryptography.hazmat.primitives.padding import PKCS7  # type: ignore[import-untyped]
                    padder = PKCS7(128).padder()
                    padded = padder.update(plaintext) + padder.finalize()
                    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                    encryptor = cipher.encryptor()
                    ct = encryptor.update(padded) + encryptor.finalize()
                except ImportError:
                    raise EPLRuntimeError(
                        'aes_encrypt requires pycryptodome or cryptography package. '
                        'Run: pip install pycryptodome  (or: pip install cryptography)', line)
            import base64 as _b64
            return _b64.b64encode(iv + ct).decode('ascii')
        if name == 'aes_decrypt':
            if len(args) < 2: raise EPLRuntimeError('aes_decrypt(ciphertext, key) requires ciphertext and key.', line)
            import base64 as _b64
            raw = _b64.b64decode(str(args[0]))
            key = _hashlib.sha256(str(args[1]).encode('utf-8')).digest()
            if len(raw) < 32:
                raise EPLRuntimeError('aes_decrypt: ciphertext too short', line)
            iv = raw[:16]
            ct = raw[16:]
            if len(ct) % 16 != 0:
                raise EPLRuntimeError('aes_decrypt: invalid ciphertext length', line)
            try:
                # Real AES-CBC via pycryptodome
                from Crypto.Cipher import AES  # type: ignore[import-untyped]
                from Crypto.Util.Padding import unpad  # type: ignore[import-untyped]
                cipher = AES.new(key, AES.MODE_CBC, iv)
                plaintext = unpad(cipher.decrypt(ct), AES.block_size)
            except ImportError:
                # Fallback: AES-CBC via cryptography library
                try:
                    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore[import-untyped]
                    from cryptography.hazmat.primitives.padding import PKCS7  # type: ignore[import-untyped]
                    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                    decryptor = cipher.decryptor()
                    padded = decryptor.update(ct) + decryptor.finalize()
                    unpadder = PKCS7(128).unpadder()
                    plaintext = unpadder.update(padded) + unpadder.finalize()
                except ImportError:
                    raise EPLRuntimeError(
                        'aes_decrypt requires pycryptodome or cryptography package. '
                        'Run: pip install pycryptodome  (or: pip install cryptography)', line)
            except (ValueError, KeyError) as e:
                raise EPLRuntimeError(f'aes_decrypt: decryption failed — {e}', line)
            return plaintext.decode('utf-8')
        if name == 'pbkdf2_hash':
            if len(args) < 1: raise EPLRuntimeError('pbkdf2_hash(password[, iterations]) requires password.', line)
            password = str(args[0]).encode('utf-8')
            iterations = int(args[1]) if len(args) > 1 else 100000
            salt = _os.urandom(16)
            dk = _hashlib.pbkdf2_hmac('sha256', password, salt, iterations)
            return f'{iterations}${salt.hex()}${dk.hex()}'
        if name == 'pbkdf2_verify':
            if len(args) < 2: raise EPLRuntimeError('pbkdf2_verify(password, hash) requires password and hash.', line)
            password = str(args[0]).encode('utf-8')
            parts = str(args[1]).split('$')
            if len(parts) != 3:
                raise EPLRuntimeError('pbkdf2_verify: invalid hash format', line)
            iterations = int(parts[0])
            salt = bytes.fromhex(parts[1])
            expected = parts[2]
            dk = _hashlib.pbkdf2_hmac('sha256', password, salt, iterations)
            import hmac as _hmac_mod
            return _hmac_mod.compare_digest(dk.hex(), expected)

        # ── SQL (extended) ──
        if name == 'db_update':
            if len(args) < 4: raise EPLRuntimeError('db_update(conn, table, set_map, where_map) requires 4 args.', line)
            conn_id, table = str(args[0]), str(args[1])
            set_data, where_data = _from_epl(args[2]), _from_epl(args[3])
            conn = _db_connections.get(conn_id)
            if not conn: raise EPLRuntimeError(f'No DB connection: {conn_id}', line)
            set_cols = ', '.join(f'"{k}" = ?' for k in set_data.keys())
            where_cols = ' AND '.join(f'"{k}" = ?' for k in where_data.keys())
            params = list(set_data.values()) + list(where_data.values())
            conn.execute(f'UPDATE "{table}" SET {set_cols} WHERE {where_cols}', params)
            conn.commit()
            return True
        if name == 'db_delete':
            if len(args) < 3: raise EPLRuntimeError('db_delete(conn, table, where_map) requires 3 args.', line)
            conn_id, table = str(args[0]), str(args[1])
            where_data = _from_epl(args[2])
            conn = _db_connections.get(conn_id)
            if not conn: raise EPLRuntimeError(f'No DB connection: {conn_id}', line)
            where_cols = ' AND '.join(f'"{k}" = ?' for k in where_data.keys())
            params = list(where_data.values())
            conn.execute(f'DELETE FROM "{table}" WHERE {where_cols}', params)
            conn.commit()
            return True
        if name == 'db_count':
            if len(args) < 2: raise EPLRuntimeError('db_count(conn, table[, where_map]) requires conn and table.', line)
            conn_id, table = str(args[0]), str(args[1])
            conn = _db_connections.get(conn_id)
            if not conn: raise EPLRuntimeError(f'No DB connection: {conn_id}', line)
            sql = f'SELECT COUNT(*) FROM "{table}"'
            params = []
            if len(args) > 2 and args[2]:
                where_data = _from_epl(args[2])
                where_cols = ' AND '.join(f'"{k}" = ?' for k in where_data.keys())
                sql += f' WHERE {where_cols}'
                params = list(where_data.values())
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else 0
        if name == 'db_table_info':
            if len(args) < 2: raise EPLRuntimeError('db_table_info(conn, table) requires conn and table.', line)
            conn_id, table = str(args[0]), str(args[1])
            conn = _db_connections.get(conn_id)
            if not conn: raise EPLRuntimeError(f'No DB connection: {conn_id}', line)
            rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            return [_to_epl_dict({'cid': r[0], 'name': r[1], 'type': r[2], 'notnull': bool(r[3]), 'pk': bool(r[5])}) for r in rows]
        if name == 'db_begin':
            if not args: raise EPLRuntimeError('db_begin(conn) requires conn.', line)
            conn = _db_connections.get(str(args[0]))
            if not conn: raise EPLRuntimeError(f'No DB connection: {args[0]}', line)
            conn.execute('BEGIN')
            return True
        if name == 'db_commit':
            if not args: raise EPLRuntimeError('db_commit(conn) requires conn.', line)
            conn = _db_connections.get(str(args[0]))
            if not conn: raise EPLRuntimeError(f'No DB connection: {args[0]}', line)
            conn.commit()
            return True
        if name == 'db_rollback':
            if not args: raise EPLRuntimeError('db_rollback(conn) requires conn.', line)
            conn = _db_connections.get(str(args[0]))
            if not conn: raise EPLRuntimeError(f'No DB connection: {args[0]}', line)
            conn.rollback()
            return True
        if name == 'db_backup':
            if len(args) < 2: raise EPLRuntimeError('db_backup(conn, dest_path) requires conn and path.', line)
            conn = _db_connections.get(str(args[0]))
            if not conn: raise EPLRuntimeError(f'No DB connection: {args[0]}', line)
            import sqlite3
            dest = sqlite3.connect(str(args[1]))
            conn.backup(dest)
            dest.close()
            return True

        # ── OS (extended) ──
        if name == 'env_delete':
            if not args: raise EPLRuntimeError('env_delete(name) requires env var name.', line)
            key = str(args[0])
            if key in _os.environ:
                del _os.environ[key]
            return True
        if name == 'hostname':
            import socket as _sock
            return _sock.gethostname()
        if name == 'arch':
            import platform as _plat
            return _plat.machine()
        if name == 'user_home':
            return _os.path.expanduser('~')
        if name == 'user_name':
            return _os.environ.get('USERNAME', _os.environ.get('USER', 'unknown'))
        if name == 'uptime':
            import time
            if hasattr(time, 'monotonic'):
                return time.monotonic()
            return 0.0
        if name == 'exec_async':
            if not args: raise EPLRuntimeError('exec_async(command) requires a command.', line)
            import subprocess, shlex
            cmd = str(args[0])
            proc = _subprocess.Popen(cmd, shell=True, stdout=_subprocess.PIPE, stderr=_subprocess.PIPE)
            pid = f'proc_{_new_id()}'
            _async_processes[pid] = proc
            return pid
        if name == 'kill_process':
            if not args: raise EPLRuntimeError('kill_process(pid_or_id) requires a process ID.', line)
            pid_val = str(args[0])
            if pid_val in _async_processes:
                _async_processes[pid_val].terminate()
                del _async_processes[pid_val]
                return True
            try:
                _os.kill(int(pid_val), 9)
                return True
            except (ProcessLookupError, PermissionError, ValueError):
                return False
        if name == 'is_admin':
            try:
                if _os.name == 'nt':
                    import ctypes
                    return bool(ctypes.windll.shell32.IsUserAnAdmin())
                else:
                    return _os.geteuid() == 0
            except Exception:
                return False

        # ── FileSystem (extended) ──
        if name == 'file_modified_time':
            if not args: raise EPLRuntimeError('file_modified_time(path) requires a path.', line)
            return _os.path.getmtime(str(args[0]))
        if name == 'file_created_time':
            if not args: raise EPLRuntimeError('file_created_time(path) requires a path.', line)
            return _os.path.getctime(str(args[0]))
        if name == 'file_is_dir':
            if not args: raise EPLRuntimeError('file_is_dir(path) requires a path.', line)
            return _os.path.isdir(str(args[0]))
        if name == 'file_is_file':
            if not args: raise EPLRuntimeError('file_is_file(path) requires a path.', line)
            return _os.path.isfile(str(args[0]))
        if name == 'file_read_binary':
            if not args: raise EPLRuntimeError('file_read_binary(path) requires a path.', line)
            with open(str(args[0]), 'rb') as f:
                return f.read().hex()
        if name == 'file_write_binary':
            if len(args) < 2: raise EPLRuntimeError('file_write_binary(path, hex_data) requires path and hex data.', line)
            with open(str(args[0]), 'wb') as f:
                f.write(bytes.fromhex(str(args[1])))
            return True
        if name == 'file_move':
            if len(args) < 2: raise EPLRuntimeError('file_move(src, dst) requires source and dest.', line)
            import shutil
            shutil.move(str(args[0]), str(args[1]))
            return True
        if name == 'dir_walk':
            if not args: raise EPLRuntimeError('dir_walk(path) requires a directory path.', line)
            results = []
            for root, dirs, files in _os.walk(str(args[0])):
                for f in files:
                    results.append(_os.path.join(root, f).replace('\\', '/'))
            return results
        if name == 'file_glob':
            if not args: raise EPLRuntimeError('file_glob(pattern) requires a glob pattern.', line)
            import glob
            return [p.replace('\\', '/') for p in glob.glob(str(args[0]), recursive=True)]
        if name == 'path_normalize':
            if not args: raise EPLRuntimeError('path_normalize(path) requires a path.', line)
            return _os.path.normpath(str(args[0])).replace('\\', '/')
        if name == 'path_relative':
            if len(args) < 2: raise EPLRuntimeError('path_relative(path, base) requires path and base.', line)
            return _os.path.relpath(str(args[0]), str(args[1])).replace('\\', '/')

        # ── Regex (extended) ──
        if name == 'regex_compile':
            if not args: raise EPLRuntimeError('regex_compile(pattern[, flags]) requires a pattern.', line)
            import re
            flags = 0
            if len(args) > 1:
                flag_str = str(args[1]).lower()
                if 'i' in flag_str: flags |= re.IGNORECASE
                if 'm' in flag_str: flags |= re.MULTILINE
                if 's' in flag_str: flags |= re.DOTALL
            compiled = re.compile(str(args[0]), flags)
            rid = f'rx_{_new_id()}'
            _compiled_regexes[rid] = compiled
            return rid
        if name == 'regex_replace_fn':
            if len(args) < 3: raise EPLRuntimeError('regex_replace_fn(pattern, text, fn) requires pattern, text, and function.', line)
            import re
            pattern = str(args[0])
            text = str(args[1])
            fn = args[2]
            # fn should be callable — we'll replace each match with fn(match_text)
            def _repl(m):
                from epl.interpreter import Interpreter
                return str(fn(m.group(0)) if callable(fn) else m.group(0))
            return re.sub(pattern, _repl, text)
        if name == 'regex_groups':
            if len(args) < 2: raise EPLRuntimeError('regex_groups(pattern, text) requires pattern and text.', line)
            import re
            m = re.search(str(args[0]), str(args[1]))
            if m is None:
                return []
            return list(m.groups())

        # ── DateTime (extended) ──
        if name == 'utc_now':
            return _datetime.datetime.utcnow().isoformat() + 'Z'
        if name == 'timezone':
            import time as _time_mod
            offset = -_time_mod.timezone if _time_mod.daylight == 0 else -_time_mod.altzone
            hours = offset // 3600
            return f'UTC{hours:+d}'
        if name == 'to_timestamp':
            if not args: raise EPLRuntimeError('to_timestamp(datetime_str) requires a datetime string.', line)
            dt = _parse_dt(str(args[0]))
            import calendar
            return calendar.timegm(dt.timetuple()) if dt else 0
        if name == 'from_timestamp':
            if not args: raise EPLRuntimeError('from_timestamp(epoch) requires an epoch number.', line)
            return _datetime.datetime.utcfromtimestamp(float(args[0])).isoformat() + 'Z'
        if name == 'week_of_year':
            if not args: raise EPLRuntimeError('week_of_year(date_str) requires a date string.', line)
            dt = _parse_dt(str(args[0]))
            return dt.isocalendar()[1] if dt else 0
        if name == 'is_weekend':
            if not args: raise EPLRuntimeError('is_weekend(date_str) requires a date string.', line)
            dt = _parse_dt(str(args[0]))
            return dt.weekday() >= 5 if dt else False
        if name == 'is_weekday':
            if not args: raise EPLRuntimeError('is_weekday(date_str) requires a date string.', line)
            dt = _parse_dt(str(args[0]))
            return dt.weekday() < 5 if dt else False
        if name == 'date_range':
            if len(args) < 2: raise EPLRuntimeError('date_range(start, end[, step_days]) requires start and end.', line)
            start = _parse_dt(str(args[0]))
            end = _parse_dt(str(args[1]))
            step = int(args[2]) if len(args) > 2 else 1
            if not start or not end: return []
            result = []
            cur = start
            delta = _datetime.timedelta(days=step)
            while cur <= end:
                result.append(cur.strftime('%Y-%m-%d'))
                cur += delta
            return result

        # ── Collections (extended) ──
        if name == 'linked_list_new':
            lid = f'll_{_new_id()}'
            _linked_lists[lid] = []
            return lid
        if name == 'linked_list_append':
            if len(args) < 2: raise EPLRuntimeError('linked_list_append(ll, value) requires list and value.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            ll.append(args[1])
            return True
        if name == 'linked_list_prepend':
            if len(args) < 2: raise EPLRuntimeError('linked_list_prepend(ll, value) requires list and value.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            ll.insert(0, args[1])
            return True
        if name == 'linked_list_pop':
            if not args: raise EPLRuntimeError('linked_list_pop(ll) requires a linked list.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            if not ll: return None
            return ll.pop()
        if name == 'linked_list_pop_front':
            if not args: raise EPLRuntimeError('linked_list_pop_front(ll) requires a linked list.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            if not ll: return None
            return ll.pop(0)
        if name == 'linked_list_get':
            if len(args) < 2: raise EPLRuntimeError('linked_list_get(ll, index) requires list and index.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            idx = int(args[1])
            if idx < 0 or idx >= len(ll): return None
            return ll[idx]
        if name == 'linked_list_size':
            if not args: raise EPLRuntimeError('linked_list_size(ll) requires a linked list.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            return len(ll)
        if name == 'linked_list_to_list':
            if not args: raise EPLRuntimeError('linked_list_to_list(ll) requires a linked list.', line)
            ll = _linked_lists.get(str(args[0]))
            if ll is None: raise EPLRuntimeError(f'No linked list: {args[0]}', line)
            return list(ll)
        if name == 'priority_queue_new':
            pid = f'pq_{_new_id()}'
            _priority_queues[pid] = []
            return pid
        if name == 'priority_queue_push':
            if len(args) < 3: raise EPLRuntimeError('priority_queue_push(pq, priority, value) requires 3 args.', line)
            pq = _priority_queues.get(str(args[0]))
            if pq is None: raise EPLRuntimeError(f'No priority queue: {args[0]}', line)
            import heapq
            heapq.heappush(pq, (float(args[1]), args[2]))
            return True
        if name == 'priority_queue_pop':
            if not args: raise EPLRuntimeError('priority_queue_pop(pq) requires a priority queue.', line)
            pq = _priority_queues.get(str(args[0]))
            if pq is None: raise EPLRuntimeError(f'No priority queue: {args[0]}', line)
            if not pq: return None
            import heapq
            return heapq.heappop(pq)[1]
        if name == 'priority_queue_peek':
            if not args: raise EPLRuntimeError('priority_queue_peek(pq) requires a priority queue.', line)
            pq = _priority_queues.get(str(args[0]))
            if pq is None: raise EPLRuntimeError(f'No priority queue: {args[0]}', line)
            if not pq: return None
            return pq[0][1]
        if name == 'priority_queue_size':
            if not args: raise EPLRuntimeError('priority_queue_size(pq) requires a priority queue.', line)
            pq = _priority_queues.get(str(args[0]))
            if pq is None: raise EPLRuntimeError(f'No priority queue: {args[0]}', line)
            return len(pq)
        if name == 'deque_new':
            did = f'dq_{_new_id()}'
            from collections import deque
            _deques[did] = deque()
            return did
        if name == 'deque_push_back':
            if len(args) < 2: raise EPLRuntimeError('deque_push_back(dq, value) requires deque and value.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            dq.append(args[1])
            return True
        if name == 'deque_push_front':
            if len(args) < 2: raise EPLRuntimeError('deque_push_front(dq, value) requires deque and value.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            dq.appendleft(args[1])
            return True
        if name == 'deque_pop_back':
            if not args: raise EPLRuntimeError('deque_pop_back(dq) requires a deque.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            if not dq: return None
            return dq.pop()
        if name == 'deque_pop_front':
            if not args: raise EPLRuntimeError('deque_pop_front(dq) requires a deque.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            if not dq: return None
            return dq.popleft()
        if name == 'deque_size':
            if not args: raise EPLRuntimeError('deque_size(dq) requires a deque.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            return len(dq)
        if name == 'deque_to_list':
            if not args: raise EPLRuntimeError('deque_to_list(dq) requires a deque.', line)
            dq = _deques.get(str(args[0]))
            if dq is None: raise EPLRuntimeError(f'No deque: {args[0]}', line)
            return list(dq)
        if name == 'ordered_map_new':
            from collections import OrderedDict
            oid = f'om_{_new_id()}'
            _ordered_maps[oid] = OrderedDict()
            return oid
        if name == 'ordered_map_set':
            if len(args) < 3: raise EPLRuntimeError('ordered_map_set(om, key, value) requires 3 args.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            om[str(args[1])] = args[2]
            return True
        if name == 'ordered_map_get':
            if len(args) < 2: raise EPLRuntimeError('ordered_map_get(om, key) requires map and key.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            return om.get(str(args[1]))
        if name == 'ordered_map_delete':
            if len(args) < 2: raise EPLRuntimeError('ordered_map_delete(om, key) requires map and key.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            om.pop(str(args[1]), None)
            return True
        if name == 'ordered_map_keys':
            if not args: raise EPLRuntimeError('ordered_map_keys(om) requires an ordered map.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            return list(om.keys())
        if name == 'ordered_map_values':
            if not args: raise EPLRuntimeError('ordered_map_values(om) requires an ordered map.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            return list(om.values())
        if name == 'ordered_map_size':
            if not args: raise EPLRuntimeError('ordered_map_size(om) requires an ordered map.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            return len(om)
        if name == 'ordered_map_to_list':
            if not args: raise EPLRuntimeError('ordered_map_to_list(om) requires an ordered map.', line)
            om = _ordered_maps.get(str(args[0]))
            if om is None: raise EPLRuntimeError(f'No ordered map: {args[0]}', line)
            return [[k, v] for k, v in om.items()]
        if name == 'set_size':
            if not args: raise EPLRuntimeError('set_size(s) requires a set.', line)
            s = args[0]
            if isinstance(s, set): return len(s)
            if isinstance(s, list): return len(s)
            return 0
        if name == 'set_to_list':
            if not args: raise EPLRuntimeError('set_to_list(s) requires a set.', line)
            s = args[0]
            if isinstance(s, set): return sorted(list(s))
            if isinstance(s, list): return list(s)
            return []
        if name == 'set_clear':
            if not args: raise EPLRuntimeError('set_clear(s) requires a set.', line)
            s = args[0]
            if isinstance(s, set):
                s.clear()
            elif isinstance(s, list):
                s.clear()
            return args[0]
        if name == 'group_by':
            if len(args) < 2: raise EPLRuntimeError('group_by(list, key_fn) requires list and key function.', line)
            items = args[0]
            key_fn = args[1]
            result = {}
            for item in items:
                key = str(key_fn(item)) if callable(key_fn) else str(item)
                if key not in result:
                    result[key] = []
                result[key].append(item)
            return _to_epl(result)
        if name == 'partition':
            if len(args) < 2: raise EPLRuntimeError('partition(list, pred_fn) requires list and predicate.', line)
            items = args[0]
            fn = args[1]
            truthy, falsy = [], []
            for item in items:
                if callable(fn) and fn(item):
                    truthy.append(item)
                else:
                    falsy.append(item)
            return [truthy, falsy]
        if name == 'frequency_map':
            if not args: raise EPLRuntimeError('frequency_map(list) requires a list.', line)
            counts = {}
            for item in args[0]:
                key = str(item)
                counts[key] = counts.get(key, 0) + 1
            return _to_epl(counts)

        # ── Math (extended) ──
        if name == 'log2':
            if not args: raise EPLRuntimeError('log2(x) requires a number.', line)
            return _math.log2(float(args[0]))
        if name == 'log10':
            if not args: raise EPLRuntimeError('log10(x) requires a number.', line)
            return _math.log10(float(args[0]))
        if name == 'exp':
            if not args: raise EPLRuntimeError('exp(x) requires a number.', line)
            return _math.exp(float(args[0]))
        if name == 'hypot':
            if len(args) < 2: raise EPLRuntimeError('hypot(x, y) requires two numbers.', line)
            return _math.hypot(float(args[0]), float(args[1]))
        if name == 'sinh':
            if not args: raise EPLRuntimeError('sinh(x) requires a number.', line)
            return _math.sinh(float(args[0]))
        if name == 'cosh':
            if not args: raise EPLRuntimeError('cosh(x) requires a number.', line)
            return _math.cosh(float(args[0]))
        if name == 'tanh':
            if not args: raise EPLRuntimeError('tanh(x) requires a number.', line)
            return _math.tanh(float(args[0]))
        if name == 'asinh':
            if not args: raise EPLRuntimeError('asinh(x) requires a number.', line)
            return _math.asinh(float(args[0]))
        if name == 'acosh':
            if not args: raise EPLRuntimeError('acosh(x) requires a number.', line)
            return _math.acosh(float(args[0]))
        if name == 'atanh':
            if not args: raise EPLRuntimeError('atanh(x) requires a number.', line)
            return _math.atanh(float(args[0]))
        if name == 'ceil_div':
            if len(args) < 2: raise EPLRuntimeError('ceil_div(a, b) requires two numbers.', line)
            a, b = int(args[0]), int(args[1])
            if b == 0: raise EPLRuntimeError('ceil_div: division by zero', line)
            return -(-a // b)
        if name == 'fmod':
            if len(args) < 2: raise EPLRuntimeError('fmod(x, y) requires two numbers.', line)
            return _math.fmod(float(args[0]), float(args[1]))
        if name == 'copysign':
            if len(args) < 2: raise EPLRuntimeError('copysign(x, y) requires two numbers.', line)
            return _math.copysign(float(args[0]), float(args[1]))
        if name == 'permutations':
            if len(args) < 2: raise EPLRuntimeError('permutations(n, r) requires n and r.', line)
            n, r = int(args[0]), int(args[1])
            return _math.perm(n, r) if hasattr(_math, 'perm') else int(_math.factorial(n) / _math.factorial(n - r))
        if name == 'combinations':
            if len(args) < 2: raise EPLRuntimeError('combinations(n, r) requires n and r.', line)
            n, r = int(args[0]), int(args[1])
            return _math.comb(n, r) if hasattr(_math, 'comb') else int(_math.factorial(n) / (_math.factorial(r) * _math.factorial(n - r)))
        if name == 'variance':
            if not args: raise EPLRuntimeError('variance(list) requires a list of numbers.', line)
            nums = [float(x) for x in args[0]]
            if len(nums) < 2: raise EPLRuntimeError('variance requires at least 2 values.', line)
            mean = sum(nums) / len(nums)
            return sum((x - mean) ** 2 for x in nums) / (len(nums) - 1)
        if name == 'std_dev':
            if not args: raise EPLRuntimeError('std_dev(list) requires a list of numbers.', line)
            nums = [float(x) for x in args[0]]
            if len(nums) < 2: raise EPLRuntimeError('std_dev requires at least 2 values.', line)
            mean = sum(nums) / len(nums)
            var = sum((x - mean) ** 2 for x in nums) / (len(nums) - 1)
            return _math.sqrt(var)

        # ── Encoding (extended) ──
        if name == 'base64_url_encode':
            if not args: raise EPLRuntimeError('base64_url_encode(text) requires a string.', line)
            import base64
            return base64.urlsafe_b64encode(str(args[0]).encode()).decode().rstrip('=')
        if name == 'base64_url_decode':
            if not args: raise EPLRuntimeError('base64_url_decode(text) requires a string.', line)
            import base64
            s = str(args[0])
            s += '=' * (4 - len(s) % 4)  # Add padding
            return base64.urlsafe_b64decode(s).decode('utf-8')
        if name == 'html_encode':
            if not args: raise EPLRuntimeError('html_encode(text) requires a string.', line)
            import html
            return html.escape(str(args[0]))
        if name == 'html_decode':
            if not args: raise EPLRuntimeError('html_decode(text) requires a string.', line)
            import html
            return html.unescape(str(args[0]))
        if name == 'base32_encode':
            if not args: raise EPLRuntimeError('base32_encode(text) requires a string.', line)
            import base64
            return base64.b32encode(str(args[0]).encode()).decode()
        if name == 'base32_decode':
            if not args: raise EPLRuntimeError('base32_decode(text) requires a string.', line)
            import base64
            return base64.b32decode(str(args[0])).decode('utf-8')

        # ── Testing (extended) ──
        if name == 'test_describe':
            if not args: raise EPLRuntimeError('test_describe(name) sets the current test group.', line)
            _test_hooks['current_group'] = str(args[0])
            _test_hooks['describes'].append(str(args[0]))
            return True
        if name == 'test_it':
            if len(args) < 2: raise EPLRuntimeError('test_it(name, fn) requires name and function.', line)
            group = _test_hooks.get('current_group', '')
            full_name = f'{group} > {args[0]}' if group else str(args[0])
            if _test_hooks.get('before_each') and callable(_test_hooks['before_each']):
                _test_hooks['before_each']()
            try:
                if callable(args[1]):
                    args[1]()
                print(f'  PASS: {full_name}')
                result = True
            except Exception as e:
                print(f'  FAIL: {full_name} -> {e}')
                result = False
            if _test_hooks.get('after_each') and callable(_test_hooks['after_each']):
                _test_hooks['after_each']()
            return result
        if name == 'test_before_each':
            if not args: raise EPLRuntimeError('test_before_each(fn) requires a function.', line)
            _test_hooks['before_each'] = args[0]
            return True
        if name == 'test_after_each':
            if not args: raise EPLRuntimeError('test_after_each(fn) requires a function.', line)
            _test_hooks['after_each'] = args[0]
            return True
        if name == 'test_skip':
            if not args: raise EPLRuntimeError('test_skip(name) requires a test name.', line)
            print(f'  SKIP: {args[0]}')
            return True
        if name == 'test_expect_near':
            if len(args) < 3: raise EPLRuntimeError('test_expect_near(actual, expected, tolerance) requires 3 args.', line)
            actual, expected, tol = float(args[0]), float(args[1]), float(args[2])
            if abs(actual - expected) > tol:
                raise EPLRuntimeError(f'Expected {actual} near {expected} (±{tol})', line)
            return True
        if name == 'test_expect_match':
            if len(args) < 2: raise EPLRuntimeError('test_expect_match(text, pattern) requires text and regex.', line)
            import re
            if not re.search(str(args[1]), str(args[0])):
                raise EPLRuntimeError(f'Expected "{args[0]}" to match /{args[1]}/', line)
            return True
        if name == 'test_benchmark':
            if len(args) < 2: raise EPLRuntimeError('test_benchmark(name, fn[, iterations]) requires name and fn.', line)
            import time
            iterations = int(args[2]) if len(args) > 2 else 1000
            start = time.perf_counter()
            for _ in range(iterations):
                if callable(args[1]):
                    args[1]()
            elapsed = time.perf_counter() - start
            per_op = (elapsed / iterations) * 1000
            print(f'  BENCH: {args[0]} — {per_op:.4f}ms/op ({iterations} iterations, {elapsed:.3f}s total)')
            return per_op
        if name == 'test_assert_throws':
            if len(args) < 1: raise EPLRuntimeError('test_assert_throws(fn) requires a function.', line)
            try:
                if callable(args[0]):
                    args[0]()
                raise EPLRuntimeError('Expected function to throw an error', line)
            except EPLRuntimeError:
                raise
            except Exception:
                return True

        # ── Net (extended — HTTP server, WebSocket) ──
        if name == 'net_http_server':
            from http.server import HTTPServer, BaseHTTPRequestHandler
            sid = f'httpd_{_new_id()}'
            port = int(args[0]) if args else 8080
            routes = {}

            class EPLHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    handler = routes.get(('GET', self.path))
                    if handler and callable(handler):
                        resp = str(handler(self.path))
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(resp.encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b'Not Found')
                def do_POST(self):
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length).decode() if length else ''
                    handler = routes.get(('POST', self.path))
                    if handler and callable(handler):
                        resp = str(handler(self.path, body))
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(resp.encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                def log_message(self, format, *a): pass  # Suppress logs

            server = HTTPServer(('0.0.0.0', port), EPLHandler)
            _http_servers[sid] = {'server': server, 'routes': routes, 'handler_class': EPLHandler}
            return sid
        if name == 'net_http_server_route':
            if len(args) < 4: raise EPLRuntimeError('net_http_server_route(server, method, path, handler) requires 4 args.', line)
            sid = str(args[0])
            sdata = _http_servers.get(sid)
            if not sdata: raise EPLRuntimeError(f'No HTTP server: {sid}', line)
            method = str(args[1]).upper()
            path = str(args[2])
            sdata['routes'][(method, path)] = args[3]
            return True
        if name == 'net_http_server_start':
            if not args: raise EPLRuntimeError('net_http_server_start(server) requires server ID.', line)
            sid = str(args[0])
            sdata = _http_servers.get(sid)
            if not sdata: raise EPLRuntimeError(f'No HTTP server: {sid}', line)
            t = _threading.Thread(target=sdata['server'].serve_forever, daemon=True)
            t.start()
            return True
        if name == 'net_http_server_stop':
            if not args: raise EPLRuntimeError('net_http_server_stop(server) requires server ID.', line)
            sid = str(args[0])
            sdata = _http_servers.get(sid)
            if not sdata: raise EPLRuntimeError(f'No HTTP server: {sid}', line)
            sdata['server'].shutdown()
            del _http_servers[sid]
            return True
        if name == 'net_ws_connect':
            if not args: raise EPLRuntimeError('net_ws_connect(url) requires a WebSocket URL.', line)
            try:
                import websocket
            except ImportError:
                raise EPLRuntimeError('WebSocket support requires: pip install websocket-client', line)
            ws = websocket.create_connection(str(args[0]))
            wid = f'ws_{_new_id()}'
            _ws_connections[wid] = ws
            return wid
        if name == 'net_ws_send':
            if len(args) < 2: raise EPLRuntimeError('net_ws_send(ws, message) requires connection and message.', line)
            ws = _ws_connections.get(str(args[0]))
            if not ws: raise EPLRuntimeError(f'No WebSocket: {args[0]}', line)
            ws.send(str(args[1]))
            return True
        if name == 'net_ws_receive':
            if not args: raise EPLRuntimeError('net_ws_receive(ws) requires a connection.', line)
            ws = _ws_connections.get(str(args[0]))
            if not ws: raise EPLRuntimeError(f'No WebSocket: {args[0]}', line)
            return ws.recv()
        if name == 'net_ws_close':
            if not args: raise EPLRuntimeError('net_ws_close(ws) requires a connection.', line)
            wid = str(args[0])
            ws = _ws_connections.get(wid)
            if ws:
                ws.close()
                del _ws_connections[wid]
            return True

        # ══════════════════════════════════════════════════
        #  WebServer (Flask-powered production web server)
        # ══════════════════════════════════════════════════
        if name.startswith('web_'):
            return _call_web(name, args, line)

        # ══════════════════════════════════════════════════
        #  Auth & JWT (Phase 3)
        # ══════════════════════════════════════════════════
        if name.startswith('auth_'):
            return _call_auth(name, args, line)

        # ══════════════════════════════════════════════════
        #  WebSocket Server (Phase 3)
        # ══════════════════════════════════════════════════
        if name.startswith('ws_'):
            return _call_ws_server(name, args, line)

        # ══════════════════════════════════════════════════
        #  Template Engine — standalone (Phase 3)
        # ══════════════════════════════════════════════════
        if name.startswith('template_'):
            return _call_template(name, args, line)

        # ══════════════════════════════════════════════════
        #  HTML Builder (Phase 3)
        # ══════════════════════════════════════════════════
        if name.startswith('html_'):
            return _call_html(name, args, line)

        # ══════════════════════════════════════════════════
        #  API Helpers (Phase 3)
        # ══════════════════════════════════════════════════
        if name.startswith('api_'):
            return _call_api(name, args, line)

        # ══════════════════════════════════════════════════
        #  Desktop GUI (Tkinter-powered)
        # ══════════════════════════════════════════════════
        if name.startswith('gui_'):
            return _call_gui(name, args, line)

        # ══════════════════════════════════════════════════
        #  Mobile Builder (BeeWare/Toga-powered)
        # ══════════════════════════════════════════════════
        if name.startswith('mobile_') or name.startswith('android_'):
            return _call_mobile(name, args, line)

        # ══════════════════════════════════════════════════
        #  Game Development (Pygame-powered 2D)
        # ══════════════════════════════════════════════════
        if name.startswith('game_'):
            return _call_game(name, args, line)

        # ══════════════════════════════════════════════════
        #  3D Graphics (ModernGL / PyOpenGL)
        # ══════════════════════════════════════════════════
        if name.startswith('3d_'):
            return _call_3d(name, args, line)

        # ══════════════════════════════════════════════════
        #  ML / AI (scikit-learn wrappers)
        # ══════════════════════════════════════════════════
        if name.startswith('ml_'):
            return _call_ml(name, args, line)

        # ══════════════════════════════════════════════════
        #  Deep Learning (PyTorch / TensorFlow)
        # ══════════════════════════════════════════════════
        if name.startswith('dl_'):
            return _call_dl(name, args, line)

        # ══════════════════════════════════════════════════
        #  Data Science (Pandas/NumPy/Matplotlib wrappers)
        # ══════════════════════════════════════════════════
        if name.startswith('ds_'):
            return _call_ds(name, args, line)

        # ══════════════════════════════════════════════════
        #  3D Graphics (OpenGL / ModernGL wrappers)
        # ══════════════════════════════════════════════════
        if name.startswith('3d_'):
            return _call_3d(name, args, line)

        raise EPLRuntimeError(f'Unknown stdlib function: {name}', line)

    except EPLRuntimeError:
        raise  # Re-raise EPL errors as-is
    except Exception as e:
        raise EPLRuntimeError(f'{name}() error: {e}', line)


# ═══════════════════════════════════════════════════════════
#  WebServer Module (Flask-powered production web server)
# ═══════════════════════════════════════════════════════════

_web_lock = _threading.Lock()  # Thread safety for all web state
_web_apps = {}        # app_id -> Flask app
_web_routes = {}      # app_id -> list of registered routes
_web_cors = {}        # app_id -> CORS config
_web_error_handlers = {}  # app_id -> {code: handler_fn}
_web_middleware = {}   # app_id -> [middleware_fns]
_web_running = {}     # app_id -> {'thread': Thread, 'shutdown': Event}

_flask_cache = [None]

def _ensure_flask():
    """Import Flask, auto-install if missing. Caches the import."""
    if _flask_cache[0] is not None:
        return _flask_cache[0]
    try:
        import flask  # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('flask', 'Flask'):
            raise EPLRuntimeError('Failed to install Flask. Install manually: pip install flask', 0)
        try:
            import flask  # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError('Installed flask but import still failed. Check pip output.', 0)
    _flask_cache[0] = flask
    return flask

def _call_web(name, args, line):
    """Dispatch web_* stdlib functions."""
    from epl.interpreter import EPLDict

    if name == 'web_create':
        flask = _ensure_flask()
        app_name = str(args[0]) if args else 'epl_app'
        app = flask.Flask(app_name)
        # Set a secret key so sessions work (C3 fix)
        app.secret_key = _os.urandom(32)
        app_id = f'web_{_new_id()}'
        with _web_lock:
            _web_apps[app_id] = app
            _web_routes[app_id] = []
            _web_cors[app_id] = None
            _web_error_handlers[app_id] = {}
            _web_middleware[app_id] = []
        return app_id

    if name in ('web_route', 'web_get', 'web_post', 'web_put', 'web_delete'):
        if len(args) < 2:
            raise EPLRuntimeError(f'{name}(app_id, path[, handler]) requires app_id and path.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        app = _web_apps[app_id]
        path = str(args[1])

        method_map = {
            'web_route': ['GET', 'POST'],
            'web_get': ['GET'],
            'web_post': ['POST'],
            'web_put': ['PUT'],
            'web_delete': ['DELETE'],
        }
        methods = method_map[name]

        handler = args[2] if len(args) > 2 else None

        if handler is None or not callable(handler):
            raise EPLRuntimeError(
                f'{name}(app_id, path, handler) requires a callable handler function.', line)

        # Store route info
        with _web_lock:
            _web_routes[app_id].append({
                'path': path, 'methods': methods, 'handler': handler
            })

        # Register with Flask
        flask = _ensure_flask()
        if handler is not None and callable(handler):
            # EPL callback — wrap it, passing URL params as list
            def make_view(h, m):
                def view_func(**kwargs):
                    try:
                        if kwargs:
                            result = h(*list(kwargs.values()))
                        else:
                            result = h()
                        if isinstance(result, EPLDict):
                            return flask.jsonify(_from_epl(result))
                        if isinstance(result, dict):
                            return flask.jsonify(result)
                        if isinstance(result, flask.wrappers.Response):
                            return result
                        if isinstance(result, tuple):
                            return result
                        return str(result) if result is not None else ''
                    except Exception as e:
                        return str(e), 500
                view_func.__name__ = f'epl_view_{_new_id()}'
                return view_func
            app.add_url_rule(path, view_func=make_view(handler, methods), methods=methods)
        return path

    if name == 'web_start':
        if not args:
            raise EPLRuntimeError('web_start(app_id[, port, host, debug, background]) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        app = _web_apps[app_id]
        port = int(args[1]) if len(args) > 1 else 5000
        host = str(args[2]) if len(args) > 2 else '127.0.0.1'
        # debug is accepted but NEVER passed to app.run — Werkzeug debugger is RCE
        background = bool(args[4]) if len(args) > 4 else False

        # Apply CORS if configured (I12: include OPTIONS preflight)
        cors_config = _web_cors.get(app_id)
        if cors_config:
            def make_cors_handler(cfg):
                def add_cors(response):
                    response.headers['Access-Control-Allow-Origin'] = cfg.get('origin', '*')
                    response.headers['Access-Control-Allow-Methods'] = cfg.get('methods', 'GET,POST,PUT,DELETE,OPTIONS')
                    response.headers['Access-Control-Allow-Headers'] = cfg.get('headers', 'Content-Type,Authorization')
                    return response
                return add_cors
            app.after_request(make_cors_handler(cors_config))

            # Handle OPTIONS preflight requests for all routes
            @app.route('/<path:path>', methods=['OPTIONS'])
            @app.route('/', methods=['OPTIONS'])
            def _options_preflight(path=''):
                return '', 204

        print(f'[EPL WebServer] Starting on http://{host}:{port}')
        if background:
            shutdown_event = _threading.Event()
            def run_server(a, h, p, evt):
                from werkzeug.serving import make_server  # type: ignore[import-not-found]
                srv = make_server(h, p, a)
                srv.timeout = 1
                while not evt.is_set():
                    srv.handle_request()
                srv.server_close()
            t = _threading.Thread(
                target=run_server,
                args=(app, host, port, shutdown_event),
                daemon=True,
            )
            t.start()
            with _web_lock:
                _web_running[app_id] = {'thread': t, 'shutdown': shutdown_event}
            return app_id
        else:
            app.run(host=host, port=port, debug=False)
            return None

    if name == 'web_json':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_json(data[, status]) requires data.', line)
        data = args[0]
        if isinstance(data, EPLDict):
            data = _from_epl(data)
        elif isinstance(data, list):
            data = [_from_epl(item) if isinstance(item, EPLDict) else item for item in data]
        status = int(args[1]) if len(args) > 1 else 200
        resp = flask.jsonify(data)
        resp.status_code = status
        return resp

    if name == 'web_html':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_html(content[, status]) requires content.', line)
        # Auto-escape to prevent XSS — use web_html_raw() for unescaped
        from markupsafe import Markup, escape  # type: ignore[import-not-found]
        content = str(args[0])
        status = int(args[1]) if len(args) > 1 else 200
        safe = bool(args[2]) if len(args) > 2 else False
        if not safe:
            content = str(escape(content))
        return flask.make_response(content, status)

    if name == 'web_redirect':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_redirect(url[, code]) requires URL.', line)
        url = str(args[0])
        # Prevent open redirect: only allow relative paths or same-origin URLs
        if url.startswith('//') or '://' in url:
            raise EPLRuntimeError(
                f'web_redirect() does not allow external URLs for security. '
                f'Use relative paths like "/dashboard" instead.', line)
        code = int(args[1]) if len(args) > 1 else 302
        return flask.redirect(url, code=code)

    if name == 'web_static':
        flask = _ensure_flask()
        if len(args) < 2:
            raise EPLRuntimeError('web_static(app_id, folder) requires app_id and folder path.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        folder = str(args[1])
        _web_apps[app_id].static_folder = _os.path.abspath(folder)
        return None

    if name == 'web_template':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_template(name[, context]) requires template name.', line)
        template_name = str(args[0])
        context = _from_epl(args[1]) if len(args) > 1 and isinstance(args[1], EPLDict) else {}
        return flask.render_template(template_name, **context)

    if name == 'web_request_data':
        flask = _ensure_flask()
        req = flask.request
        if req.is_json:
            return _to_epl(req.get_json(silent=True) or {})
        return _to_epl(dict(req.form))

    if name == 'web_request_args':
        flask = _ensure_flask()
        return _to_epl(dict(flask.request.args))

    if name == 'web_request_method':
        flask = _ensure_flask()
        return flask.request.method

    if name == 'web_request_path':
        flask = _ensure_flask()
        return flask.request.path

    if name == 'web_request_header':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_request_header(name) requires header name.', line)
        return flask.request.headers.get(str(args[0]), '')

    if name == 'web_request_param':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_request_param(name[, default]) requires parameter name.', line)
        param_name = str(args[0])
        default = str(args[1]) if len(args) > 1 else ''
        # Check URL params (from view_args), then query string, then form data
        val = flask.request.view_args.get(param_name) if flask.request.view_args else None
        if val is None:
            val = flask.request.args.get(param_name)
        if val is None:
            data = flask.request.get_json(silent=True) or {}
            val = data.get(param_name) if isinstance(data, dict) else None
        if val is None:
            val = flask.request.form.get(param_name)
        return val if val is not None else default

    if name == 'web_session_get':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_session_get(key[, default]) requires key.', line)
        key = str(args[0])
        default = args[1] if len(args) > 1 else None
        return flask.session.get(key, default)

    if name == 'web_session_set':
        flask = _ensure_flask()
        if len(args) < 2:
            raise EPLRuntimeError('web_session_set(key, value) requires key and value.', line)
        flask.session[str(args[0])] = args[1]
        return None

    if name == 'web_session_clear':
        flask = _ensure_flask()
        flask.session.clear()
        return None

    if name == 'web_set_cors':
        if not args:
            raise EPLRuntimeError('web_set_cors(app_id[, origin, methods, headers]) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        with _web_lock:
            _web_cors[app_id] = {
                'origin': str(args[1]) if len(args) > 1 else '*',
                'methods': str(args[2]) if len(args) > 2 else 'GET,POST,PUT,DELETE,OPTIONS',
                'headers': str(args[3]) if len(args) > 3 else 'Content-Type,Authorization',
            }
        return None

    if name == 'web_middleware':
        if len(args) < 2:
            raise EPLRuntimeError('web_middleware(app_id, handler) requires app_id and handler.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        handler = args[1]
        with _web_lock:
            _web_middleware[app_id].append(handler)
        # Register as Flask before_request so middleware actually executes
        if callable(handler):
            app = _web_apps[app_id]
            def make_middleware(h):
                def mw_func():
                    try:
                        h()
                    except Exception as exc:
                        import sys as _mw_sys
                        print(f'[EPL Middleware Error] {exc}', file=_mw_sys.stderr)
                    return None  # returning None means continue processing
                return mw_func
            app.before_request(make_middleware(handler))
        return None

    if name == 'web_error_handler':
        if len(args) < 3:
            raise EPLRuntimeError('web_error_handler(app_id, code, handler) requires app_id, status code, and handler.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        code = int(args[1])
        handler = args[2]
        if callable(handler):
            app = _web_apps[app_id]
            with _web_lock:
                _web_error_handlers.setdefault(app_id, {})[code] = handler
            def make_err_handler(h, c):
                def err_view(error):
                    try:
                        return str(h(str(error))), c
                    except TypeError:
                        # Handler doesn't accept args — call without
                        try:
                            return str(h()), c
                        except Exception as exc2:
                            import sys as _eh_sys2
                            print(f'[EPL Error Handler] {exc2}', file=_eh_sys2.stderr)
                            return 'Internal Server Error', 500
                    except Exception as exc:
                        import sys as _eh_sys
                        print(f'[EPL Error Handler] {exc}', file=_eh_sys.stderr)
                        return 'Internal Server Error', 500
                return err_view
            app.register_error_handler(code, make_err_handler(handler, code))
        return None

    if name == 'web_stop':
        if not args:
            raise EPLRuntimeError('web_stop(app_id) requires app_id.', line)
        app_id = str(args[0])
        with _web_lock:
            info = _web_running.pop(app_id, None)
        if info and info.get('shutdown'):
            info['shutdown'].set()  # Signal the background thread to stop
            info['thread'].join(timeout=5)
            return True
        return False

    if name == 'web_api_create':
        # Create a REST API-focused app with JSON defaults
        flask = _ensure_flask()
        app_name = str(args[0]) if args else 'epl_api'
        app = flask.Flask(app_name)
        app.secret_key = _os.urandom(32)
        app_id = f'web_{_new_id()}'
        with _web_lock:
            _web_apps[app_id] = app
            _web_routes[app_id] = []
            _web_cors[app_id] = {'origin': '*', 'methods': 'GET,POST,PUT,DELETE,OPTIONS', 'headers': 'Content-Type,Authorization'}
            _web_error_handlers[app_id] = {}
            _web_middleware[app_id] = []
        # Default JSON error handlers
        @app.errorhandler(404)
        def not_found(e):
            return flask.jsonify({'error': 'Not found'}), 404
        @app.errorhandler(500)
        def server_error(e):
            return flask.jsonify({'error': 'Internal server error'}), 500
        return app_id

    if name == 'web_api_resource':
        # Quick CRUD resource: web_api_resource(app_id, "/items", get_fn, create_fn, update_fn, delete_fn)
        if len(args) < 3:
            raise EPLRuntimeError('web_api_resource(app_id, path, get_handler[, create, update, delete]) requires at least app_id, path, and get handler.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        app = _web_apps[app_id]
        flask = _ensure_flask()
        path = str(args[1])
        get_fn = args[2] if len(args) > 2 else None
        create_fn = args[3] if len(args) > 3 else None
        update_fn = args[4] if len(args) > 4 else None
        delete_fn = args[5] if len(args) > 5 else None

        def make_resource_view(gf, cf, uf, df):
            def resource_view(**kwargs):
                method = flask.request.method
                url_args = list(kwargs.values()) if kwargs else []
                try:
                    if method == 'GET' and gf and callable(gf):
                        result = gf(*url_args)
                    elif method == 'POST' and cf and callable(cf):
                        result = cf(*url_args)
                    elif method == 'PUT' and uf and callable(uf):
                        result = uf(*url_args)
                    elif method == 'DELETE' and df and callable(df):
                        result = df(*url_args)
                    else:
                        return flask.jsonify({'error': 'Method not allowed'}), 405
                    if isinstance(result, EPLDict):
                        return flask.jsonify(_from_epl(result))
                    if isinstance(result, dict):
                        return flask.jsonify(result)
                    if isinstance(result, flask.wrappers.Response):
                        return result
                    if isinstance(result, tuple):
                        return result
                    return str(result) if result is not None else ''
                except Exception as e:
                    return flask.jsonify({'error': str(e)}), 500
            resource_view.__name__ = f'epl_resource_{_new_id()}'
            return resource_view

        methods = []
        if get_fn: methods.append('GET')
        if create_fn: methods.append('POST')
        if update_fn: methods.append('PUT')
        if delete_fn: methods.append('DELETE')
        app.add_url_rule(path, view_func=make_resource_view(get_fn, create_fn, update_fn, delete_fn), methods=methods)
        return path

    # ── Web Enhancements (Phase 3) ──
    if name == 'web_cookie_get':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_cookie_get(name) requires cookie name.', line)
        return flask.request.cookies.get(str(args[0]), '')

    if name == 'web_cookie_set':
        flask = _ensure_flask()
        if len(args) < 2:
            raise EPLRuntimeError('web_cookie_set(name, value[, max_age, httponly, secure, samesite]) requires name and value.', line)
        cookie_name = str(args[0])
        cookie_value = str(args[1])
        max_age = int(args[2]) if len(args) > 2 else 3600
        httponly = bool(args[3]) if len(args) > 3 else True
        secure = bool(args[4]) if len(args) > 4 else False
        samesite = str(args[5]) if len(args) > 5 else 'Lax'
        resp = flask.make_response('')
        resp.set_cookie(cookie_name, cookie_value,
                        max_age=max_age, httponly=httponly,
                        secure=secure, samesite=samesite)
        return resp

    if name == 'web_test_client':
        if not args:
            raise EPLRuntimeError('web_test_client(app_id) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        client = _web_apps[app_id].test_client()
        cid = f'tc_{_new_id()}'
        _web_test_clients[cid] = client
        return cid

    if name == 'web_test_get':
        if len(args) < 2:
            raise EPLRuntimeError('web_test_get(client_id, path[, headers]) requires client_id and path.', line)
        cid = str(args[0])
        if cid not in _web_test_clients:
            raise EPLRuntimeError(f'Unknown test client: {cid}', line)
        client = _web_test_clients[cid]
        path = str(args[1])
        headers = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict):
            headers = args[2]
        resp = client.get(path, headers=headers)
        data = resp.get_data(as_text=True)
        try:
            data = _json.loads(data)
        except (ValueError, TypeError):
            pass
        return _to_epl({'status': resp.status_code, 'data': data, 'headers': dict(resp.headers)})

    if name == 'web_test_post':
        if len(args) < 2:
            raise EPLRuntimeError('web_test_post(client_id, path[, data, headers]) requires client_id and path.', line)
        cid = str(args[0])
        if cid not in _web_test_clients:
            raise EPLRuntimeError(f'Unknown test client: {cid}', line)
        client = _web_test_clients[cid]
        path = str(args[1])
        data = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else None
        if len(args) > 2 and isinstance(args[2], dict):
            data = args[2]
        headers = _from_epl(args[3]) if len(args) > 3 and isinstance(args[3], EPLDict) else {}
        if len(args) > 3 and isinstance(args[3], dict):
            headers = args[3]
        resp = client.post(path, json=data, headers=headers)
        resp_data = resp.get_data(as_text=True)
        try:
            resp_data = _json.loads(resp_data)
        except (ValueError, TypeError):
            pass
        return _to_epl({'status': resp.status_code, 'data': resp_data, 'headers': dict(resp.headers)})

    if name == 'web_upload_config':
        if len(args) < 2:
            raise EPLRuntimeError('web_upload_config(app_id, upload_folder[, max_size]) requires app_id and folder.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        folder = _os.path.abspath(str(args[1]))
        max_size = int(args[2]) if len(args) > 2 else 16 * 1024 * 1024
        _web_upload_configs[app_id] = {'folder': folder, 'max_size': max_size}
        _web_apps[app_id].config['UPLOAD_FOLDER'] = folder
        _web_apps[app_id].config['MAX_CONTENT_LENGTH'] = max_size
        _os.makedirs(folder, exist_ok=True)
        return True

    if name == 'web_request_files':
        flask = _ensure_flask()
        files = {}
        for key in flask.request.files:
            f = flask.request.files[key]
            files[key] = {'filename': f.filename, 'content_type': f.content_type}
        return _to_epl(files)

    if name == 'web_send_file':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_send_file(path[, mimetype]) requires file path.', line)
        fpath = _os.path.abspath(str(args[0]))
        mimetype = str(args[1]) if len(args) > 1 else None
        return flask.send_file(fpath, mimetype=mimetype)

    if name == 'web_response':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_response(body[, status, headers, content_type]) requires body.', line)
        body = str(args[0])
        status = int(args[1]) if len(args) > 1 else 200
        headers = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict):
            headers = args[2]
        content_type = str(args[3]) if len(args) > 3 else 'text/html'
        resp = flask.make_response(body, status)
        resp.content_type = content_type
        for k, v in headers.items():
            resp.headers[str(k)] = str(v)
        return resp

    if name == 'web_url_for':
        flask = _ensure_flask()
        if not args:
            raise EPLRuntimeError('web_url_for(endpoint[, params]) requires endpoint.', line)
        endpoint = str(args[0])
        params = _from_epl(args[1]) if len(args) > 1 and isinstance(args[1], EPLDict) else {}
        if len(args) > 1 and isinstance(args[1], dict):
            params = args[1]
        return flask.url_for(endpoint, **params)

    raise EPLRuntimeError(f'Unknown web function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Auth & JWT Module (Phase 3)
# ═══════════════════════════════════════════════════════════

def _call_auth(name, args, line):
    """Dispatch auth_* stdlib functions."""
    import hmac as _hmac

    if name == 'auth_hash_password':
        if not args:
            raise EPLRuntimeError('auth_hash_password(password) requires a password.', line)
        password = str(args[0])
        salt = _os.urandom(32)
        key = _hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return salt.hex() + ':' + key.hex()

    if name == 'auth_verify_password':
        if len(args) < 2:
            raise EPLRuntimeError('auth_verify_password(password, hash) requires password and hash.', line)
        password = str(args[0])
        stored = str(args[1])
        try:
            salt_hex, key_hex = stored.split(':')
            salt = bytes.fromhex(salt_hex)
            stored_key = bytes.fromhex(key_hex)
            new_key = _hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return _hmac.compare_digest(stored_key, new_key)
        except (ValueError, TypeError):
            return False

    if name == 'auth_jwt_create':
        if len(args) < 2:
            raise EPLRuntimeError('auth_jwt_create(payload, secret[, expiry_seconds]) requires payload and secret.', line)
        from epl.interpreter import EPLDict
        payload = _from_epl(args[0]) if isinstance(args[0], EPLDict) else args[0]
        if not isinstance(payload, dict):
            raise EPLRuntimeError('auth_jwt_create payload must be a dict/map.', line)
        secret = str(args[1])
        expiry = int(args[2]) if len(args) > 2 else 3600
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(_time.time())
        payload = dict(payload)
        payload['iat'] = now
        payload['exp'] = now + expiry
        def b64url(data):
            return _base64.urlsafe_b64encode(
                _json.dumps(data, separators=(',', ':')).encode()
            ).rstrip(b'=').decode()
        h = b64url(header)
        p = b64url(payload)
        sig_input = f'{h}.{p}'.encode()
        sig = _base64.urlsafe_b64encode(
            _hmac.new(secret.encode(), sig_input, _hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        return f'{h}.{p}.{sig}'

    if name == 'auth_jwt_verify':
        if len(args) < 2:
            raise EPLRuntimeError('auth_jwt_verify(token, secret) requires token and secret.', line)
        token = str(args[0])
        secret = str(args[1])
        parts = token.split('.')
        if len(parts) != 3:
            raise EPLRuntimeError('Invalid JWT: expected 3 parts.', line)
        h, p, sig = parts
        sig_input = f'{h}.{p}'.encode()
        expected_sig = _base64.urlsafe_b64encode(
            _hmac.new(secret.encode(), sig_input, _hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        if not _hmac.compare_digest(sig, expected_sig):
            raise EPLRuntimeError('JWT signature verification failed.', line)
        padding = 4 - len(p) % 4
        payload = _json.loads(_base64.urlsafe_b64decode(p + '=' * padding))
        if 'exp' in payload and payload['exp'] < _time.time():
            raise EPLRuntimeError('JWT has expired.', line)
        return _to_epl(payload)

    if name == 'auth_jwt_decode':
        if not args:
            raise EPLRuntimeError('auth_jwt_decode(token) requires a token.', line)
        token = str(args[0])
        parts = token.split('.')
        if len(parts) != 3:
            raise EPLRuntimeError('Invalid JWT: expected 3 parts.', line)
        padding = 4 - len(parts[1]) % 4
        payload = _json.loads(_base64.urlsafe_b64decode(parts[1] + '=' * padding))
        return _to_epl(payload)

    if name == 'auth_generate_token':
        length = int(args[0]) if args else 32
        import secrets
        return secrets.token_urlsafe(length)

    if name == 'auth_api_key_create':
        prefix = str(args[0]) if args else 'epl'
        import secrets
        token = secrets.token_hex(24)
        key = f'{prefix}_{token}'
        key_hash = _hashlib.sha256(key.encode()).hexdigest()
        return _to_epl({'key': key, 'hash': key_hash})

    if name == 'auth_api_key_verify':
        import hmac as _hmac2
        if len(args) < 2:
            raise EPLRuntimeError('auth_api_key_verify(key, stored_hash) requires key and hash.', line)
        key = str(args[0])
        stored_hash = str(args[1])
        computed_hash = _hashlib.sha256(key.encode()).hexdigest()
        return _hmac2.compare_digest(computed_hash, stored_hash)

    if name == 'auth_bearer_token':
        flask = _ensure_flask()
        auth_header = flask.request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return ''

    if name == 'auth_basic_decode':
        if not args:
            raise EPLRuntimeError('auth_basic_decode(encoded) requires encoded string.', line)
        encoded = str(args[0])
        if encoded.startswith('Basic '):
            encoded = encoded[6:]
        try:
            decoded = _base64.b64decode(encoded).decode('utf-8')
            parts = decoded.split(':', 1)
            if len(parts) != 2:
                raise EPLRuntimeError('Invalid Basic auth: expected username:password', line)
            return parts
        except Exception as e:
            raise EPLRuntimeError(f'Failed to decode Basic auth: {e}', line)

    raise EPLRuntimeError(f'Unknown auth function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  WebSocket Server Module (Phase 3)
# ═══════════════════════════════════════════════════════════

def _call_ws_server(name, args, line):
    """Dispatch ws_* stdlib functions for WebSocket server."""

    if name == 'ws_server_create':
        if not args:
            raise EPLRuntimeError('ws_server_create(port) requires a port.', line)
        port = int(args[0])
        sid = f'wss_{_new_id()}'
        _ws_servers[sid] = {
            'port': port, 'server': None,
            'clients': {},
            'rooms': {},
            'handlers': {'on_connect': None, 'on_message': None, 'on_disconnect': None},
            'thread': None, 'running': False,
        }
        return sid

    if name == 'ws_server_start':
        if not args:
            raise EPLRuntimeError('ws_server_start(server_id) requires server_id.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        srv = _ws_servers[sid]
        if srv['running']:
            return True
        server_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        server_sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', srv['port']))
        server_sock.listen(128)
        server_sock.settimeout(1.0)
        srv['server'] = server_sock
        srv['running'] = True

        def ws_accept_key(key):
            GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            accept = _hashlib.sha1((key + GUID).encode()).digest()
            return _base64.b64encode(accept).decode()

        def ws_read_frame(sock):
            try:
                hdr = sock.recv(2)
                if len(hdr) < 2: return None
                b0, b1 = hdr[0], hdr[1]
                opcode = b0 & 0x0F
                masked = b1 & 0x80
                length = b1 & 0x7F
                if length == 126:
                    length = _struct.unpack('!H', sock.recv(2))[0]
                elif length == 127:
                    length = _struct.unpack('!Q', sock.recv(8))[0]
                if length > 16 * 1024 * 1024: return None
                mask_key = sock.recv(4) if masked else b''
                data = b''
                while len(data) < length:
                    chunk = sock.recv(min(length - len(data), 65536))
                    if not chunk: return None
                    data += chunk
                if masked and mask_key:
                    data = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
                return (opcode, data)
            except Exception:
                return None

        def ws_send_frame(sock, data, opcode=1):
            if isinstance(data, str): data = data.encode('utf-8')
            frame = bytearray()
            frame.append(0x80 | opcode)
            length = len(data)
            if length < 126:
                frame.append(length)
            elif length < 65536:
                frame.append(126)
                frame.extend(_struct.pack('!H', length))
            else:
                frame.append(127)
                frame.extend(_struct.pack('!Q', length))
            frame.extend(data)
            sock.sendall(bytes(frame))

        def handle_client(client_sock, addr, server_data, cid):
            try:
                request = b''
                while b'\r\n\r\n' not in request:
                    chunk = client_sock.recv(4096)
                    if not chunk: return
                    request += chunk
                request_str = request.decode('utf-8', errors='replace')
                key = None
                for hline in request_str.split('\r\n'):
                    if hline.lower().startswith('sec-websocket-key:'):
                        key = hline.split(':', 1)[1].strip()
                        break
                if not key:
                    client_sock.close()
                    return
                accept = ws_accept_key(key)
                response = (
                    'HTTP/1.1 101 Switching Protocols\r\n'
                    'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                    f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
                )
                client_sock.sendall(response.encode())
                server_data['clients'][cid] = {
                    'socket': client_sock,
                    'addr': f'{addr[0]}:{addr[1]}',
                    'send': lambda msg, s=client_sock: ws_send_frame(s, msg),
                }
                handler = server_data['handlers'].get('on_connect')
                if handler and callable(handler):
                    try: handler(cid)
                    except Exception: pass
                while server_data['running']:
                    result = ws_read_frame(client_sock)
                    if result is None: break
                    opcode, data = result
                    if opcode == 0x8: break
                    if opcode == 0x9:
                        ws_send_frame(client_sock, data, opcode=0xA)
                        continue
                    if opcode == 0x1:
                        msg = data.decode('utf-8', errors='replace')
                        handler = server_data['handlers'].get('on_message')
                        if handler and callable(handler):
                            try: handler(cid, msg)
                            except Exception: pass
            except Exception:
                pass
            finally:
                handler = server_data['handlers'].get('on_disconnect')
                if handler and callable(handler):
                    try: handler(cid)
                    except Exception: pass
                for room_members in server_data['rooms'].values():
                    room_members.discard(cid)
                server_data['clients'].pop(cid, None)
                try: client_sock.close()
                except Exception: pass

        def accept_loop(server_data):
            while server_data['running']:
                try:
                    client_sock, addr = server_data['server'].accept()
                    cid = f'wsc_{_new_id()}'
                    t = _threading.Thread(target=handle_client,
                                          args=(client_sock, addr, server_data, cid), daemon=True)
                    t.start()
                except _socket.timeout:
                    continue
                except Exception:
                    if server_data['running']: continue
                    break

        t = _threading.Thread(target=accept_loop, args=(srv,), daemon=True)
        t.start()
        srv['thread'] = t
        return True

    if name == 'ws_server_stop':
        if not args:
            raise EPLRuntimeError('ws_server_stop(server_id) requires server_id.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        srv = _ws_servers[sid]
        srv['running'] = False
        if srv['server']:
            try: srv['server'].close()
            except Exception: pass
        for cid, client in list(srv['clients'].items()):
            try: client['socket'].close()
            except Exception: pass
        srv['clients'].clear()
        srv['rooms'].clear()
        del _ws_servers[sid]
        return True

    if name == 'ws_on_connect':
        if len(args) < 2:
            raise EPLRuntimeError('ws_on_connect(server_id, handler) requires server_id and handler.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        _ws_servers[sid]['handlers']['on_connect'] = args[1]
        return True

    if name == 'ws_on_message':
        if len(args) < 2:
            raise EPLRuntimeError('ws_on_message(server_id, handler) requires server_id and handler.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        _ws_servers[sid]['handlers']['on_message'] = args[1]
        return True

    if name == 'ws_on_disconnect':
        if len(args) < 2:
            raise EPLRuntimeError('ws_on_disconnect(server_id, handler) requires server_id and handler.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        _ws_servers[sid]['handlers']['on_disconnect'] = args[1]
        return True

    if name == 'ws_broadcast':
        if len(args) < 2:
            raise EPLRuntimeError('ws_broadcast(server_id, message) requires server_id and message.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        msg = str(args[1])
        count = 0
        for cid, client in list(_ws_servers[sid]['clients'].items()):
            try:
                client['send'](msg)
                count += 1
            except Exception:
                pass
        return count

    if name == 'ws_send_to':
        if len(args) < 3:
            raise EPLRuntimeError('ws_send_to(server_id, client_id, message) requires 3 args.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        cid = str(args[1])
        client = _ws_servers[sid]['clients'].get(cid)
        if not client:
            raise EPLRuntimeError(f'Unknown WS client: {cid}', line)
        client['send'](str(args[2]))
        return True

    if name == 'ws_room_join':
        if len(args) < 3:
            raise EPLRuntimeError('ws_room_join(server_id, client_id, room) requires 3 args.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        room = str(args[2])
        if room not in _ws_servers[sid]['rooms']:
            _ws_servers[sid]['rooms'][room] = set()
        _ws_servers[sid]['rooms'][room].add(str(args[1]))
        return True

    if name == 'ws_room_leave':
        if len(args) < 3:
            raise EPLRuntimeError('ws_room_leave(server_id, client_id, room) requires 3 args.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        room = str(args[2])
        if room in _ws_servers[sid]['rooms']:
            _ws_servers[sid]['rooms'][room].discard(str(args[1]))
        return True

    if name == 'ws_room_broadcast':
        if len(args) < 3:
            raise EPLRuntimeError('ws_room_broadcast(server_id, room, message) requires 3 args.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        room = str(args[1])
        msg = str(args[2])
        members = _ws_servers[sid]['rooms'].get(room, set())
        count = 0
        for cid in members:
            client = _ws_servers[sid]['clients'].get(cid)
            if client:
                try:
                    client['send'](msg)
                    count += 1
                except Exception:
                    pass
        return count

    if name == 'ws_clients':
        if not args:
            raise EPLRuntimeError('ws_clients(server_id) requires server_id.', line)
        sid = str(args[0])
        if sid not in _ws_servers:
            raise EPLRuntimeError(f'Unknown WS server: {sid}', line)
        return list(_ws_servers[sid]['clients'].keys())

    raise EPLRuntimeError(f'Unknown ws function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Template Engine Module (Phase 3) — standalone templates
# ═══════════════════════════════════════════════════════════

class _SafeString(str):
    """String that won't be auto-escaped by the template engine."""
    _safe = True


def _resolve_context(expr, context):
    """Resolve a dotted name from context. e.g. 'user.name' -> context['user']['name']"""
    from epl.interpreter import EPLDict
    parts = expr.split('.')
    value = context
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, EPLDict):
            value = value.data.get(part)
        elif hasattr(value, part):
            value = getattr(value, part)
        else:
            return None
    return value


def _eval_template_condition(cond, context):
    """Evaluate a simple template condition."""
    if cond.startswith('not '):
        return not _eval_template_condition(cond[4:].strip(), context)
    for op, fn in [('==', lambda a, b: a == b), ('!=', lambda a, b: a != b),
                   ('>=', lambda a, b: a >= b), ('<=', lambda a, b: a <= b),
                   ('>', lambda a, b: a > b), ('<', lambda a, b: a < b)]:
        if op in cond:
            left, right = cond.split(op, 1)
            left_val = _resolve_context(left.strip(), context)
            right_val = right.strip().strip('"').strip("'")
            try:
                if isinstance(left_val, (int, float)):
                    right_val = type(left_val)(right_val)
            except (ValueError, TypeError):
                pass
            return fn(left_val, right_val)
    val = _resolve_context(cond, context)
    return bool(val)


def _apply_template_filter(value, filter_name, arg):
    """Apply a template filter."""
    import html as _html_mod
    if filter_name in _template_filters:
        return _template_filters[filter_name](value, arg) if arg else _template_filters[filter_name](value)
    if filter_name == 'safe':
        return _SafeString(str(value) if value is not None else '')
    if filter_name == 'upper':
        return str(value).upper() if value else ''
    if filter_name == 'lower':
        return str(value).lower() if value else ''
    if filter_name == 'title':
        return str(value).title() if value else ''
    if filter_name == 'capitalize':
        return str(value).capitalize() if value else ''
    if filter_name in ('strip', 'trim'):
        return str(value).strip() if value else ''
    if filter_name in ('length', 'len'):
        return len(value) if value else 0
    if filter_name == 'reverse':
        if isinstance(value, (list, tuple)): return list(reversed(value))
        return str(value)[::-1] if value else ''
    if filter_name == 'first':
        return value[0] if isinstance(value, (list, tuple)) and value else ''
    if filter_name == 'last':
        return value[-1] if isinstance(value, (list, tuple)) and value else ''
    if filter_name == 'sort':
        return sorted(value) if isinstance(value, (list, tuple)) else value
    if filter_name == 'join':
        sep = arg if arg else ', '
        return sep.join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)
    if filter_name == 'truncate':
        max_len = int(arg) if arg else 50
        s = str(value)
        return s[:max_len] + '...' if len(s) > max_len else s
    if filter_name == 'default':
        return value if value else (arg or '')
    if filter_name == 'replace':
        if arg and ':' in arg:
            old, new = arg.split(':', 1)
            return str(value).replace(old, new)
        return str(value)
    if filter_name == 'nl2br':
        return _SafeString(str(value).replace('\n', '<br>'))
    if filter_name == 'json':
        from epl.interpreter import EPLDict
        v = value.data if isinstance(value, EPLDict) else value
        return _SafeString(_json.dumps(v))
    if filter_name == 'url_encode':
        return _urllib_parse.quote(str(value))
    if filter_name in ('escape', 'e'):
        return _html_mod.escape(str(value))
    if filter_name == 'int':
        try: return int(value)
        except (ValueError, TypeError): return 0
    if filter_name == 'float':
        try: return float(value)
        except (ValueError, TypeError): return 0.0
    if filter_name == 'abs':
        try: return abs(value)
        except (ValueError, TypeError): return value
    if filter_name == 'round':
        digits = int(arg) if arg else 0
        try: return round(float(value), digits)
        except (ValueError, TypeError): return value
    return value


def _render_template_string(template, context, line):
    """Render a template string with the given context."""
    import html as _html_mod
    result = template

    # Process {% for item in list %}...{% endfor %}
    for_pattern = _re.compile(
        r'\{%\s*for\s+(\w+)\s+in\s+(\w+(?:\.\w+)*)\s*%\}(.*?)\{%\s*endfor\s*%\}', _re.DOTALL)
    depth = 0
    while for_pattern.search(result) and depth < 10:
        depth += 1
        def replace_for(match):
            var_name, list_name, body = match.group(1), match.group(2), match.group(3)
            items = _resolve_context(list_name, context)
            if not isinstance(items, (list, tuple)): return ''
            output = []
            for i, item in enumerate(items):
                iter_ctx = dict(context)
                iter_ctx[var_name] = item
                iter_ctx['loop'] = {
                    'index': i + 1, 'index0': i,
                    'first': i == 0, 'last': i == len(items) - 1, 'length': len(items),
                }
                output.append(_render_template_string(body, iter_ctx, line))
            return ''.join(output)
        result = for_pattern.sub(replace_for, result)

    # Process {% if cond %}...{% else %}...{% endif %}
    if_else_pattern = _re.compile(
        r'\{%\s*if\s+(.+?)\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}', _re.DOTALL)
    depth = 0
    while if_else_pattern.search(result) and depth < 10:
        depth += 1
        def replace_if_else(match):
            cond, true_block, false_block = match.group(1).strip(), match.group(2), match.group(3)
            if _eval_template_condition(cond, context):
                return _render_template_string(true_block, context, line)
            return _render_template_string(false_block, context, line)
        result = if_else_pattern.sub(replace_if_else, result)

    # Process {% if cond %}...{% endif %} (no else)
    if_pattern = _re.compile(r'\{%\s*if\s+(.+?)\s*%\}(.*?)\{%\s*endif\s*%\}', _re.DOTALL)
    depth = 0
    while if_pattern.search(result) and depth < 10:
        depth += 1
        def replace_if(match):
            cond, body = match.group(1).strip(), match.group(2)
            if _eval_template_condition(cond, context):
                return _render_template_string(body, context, line)
            return ''
        result = if_pattern.sub(replace_if, result)

    # Process {% include "name" %}
    include_pattern = _re.compile(r'\{%\s*include\s+["\'](.+?)["\']\s*%\}')
    depth = 0
    while include_pattern.search(result) and depth < 10:
        depth += 1
        def replace_include(match):
            inc_name = match.group(1)
            if inc_name in _templates:
                return _render_template_string(_templates[inc_name], context, line)
            return f'<!-- template not found: {_html_mod.escape(inc_name)} -->'
        result = include_pattern.sub(replace_include, result)

    # Process {{ variable|filter }}
    var_pattern = _re.compile(r'\{\{\s*(.+?)\s*\}\}')
    def replace_var(match):
        expr = match.group(1)
        parts = expr.split('|')
        var_expr = parts[0].strip()
        value = _resolve_context(var_expr, context)
        for filt in parts[1:]:
            filt = filt.strip()
            filt_parts = filt.split(':', 1)
            filt_name = filt_parts[0].strip()
            filt_arg = filt_parts[1].strip() if len(filt_parts) > 1 else None
            if filt_arg and len(filt_arg) >= 2 and filt_arg[0] == filt_arg[-1] and filt_arg[0] in ('"', "'"):
                filt_arg = filt_arg[1:-1]
            value = _apply_template_filter(value, filt_name, filt_arg)
        if value is None: return ''
        if isinstance(value, str) and not getattr(value, '_safe', False):
            return _html_mod.escape(str(value))
        return str(value)
    result = var_pattern.sub(replace_var, result)

    return result


def _call_template(name, args, line):
    """Dispatch template_* stdlib functions."""
    if name == 'template_create':
        if len(args) < 2:
            raise EPLRuntimeError('template_create(name, content) requires name and content.', line)
        tname = str(args[0])
        _templates[tname] = str(args[1])
        return tname

    if name == 'template_render':
        if not args:
            raise EPLRuntimeError('template_render(name[, context]) requires template name.', line)
        tname = str(args[0])
        if tname not in _templates:
            raise EPLRuntimeError(f'Template not found: {tname}', line)
        from epl.interpreter import EPLDict
        context = _from_epl(args[1]) if len(args) > 1 and isinstance(args[1], EPLDict) else {}
        if len(args) > 1 and isinstance(args[1], dict):
            context = args[1]
        return _render_template_string(_templates[tname], context, line)

    if name == 'template_render_string':
        if not args:
            raise EPLRuntimeError('template_render_string(template[, context]) requires template string.', line)
        template_str = str(args[0])
        from epl.interpreter import EPLDict
        context = _from_epl(args[1]) if len(args) > 1 and isinstance(args[1], EPLDict) else {}
        if len(args) > 1 and isinstance(args[1], dict):
            context = args[1]
        return _render_template_string(template_str, context, line)

    if name == 'template_add_filter':
        if len(args) < 2:
            raise EPLRuntimeError('template_add_filter(name, handler) requires name and handler.', line)
        fname = str(args[0])
        handler = args[1]
        if not callable(handler):
            raise EPLRuntimeError('template_add_filter handler must be callable.', line)
        _template_filters[fname] = handler
        return True

    if name == 'template_from_file':
        if not args:
            raise EPLRuntimeError('template_from_file(path) requires file path.', line)
        fpath = str(args[0])
        if not _os.path.isfile(fpath):
            raise EPLRuntimeError(f'Template file not found: {fpath}', line)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        tname = _os.path.basename(fpath)
        _templates[tname] = content
        return tname

    if name == 'template_exists':
        if not args:
            raise EPLRuntimeError('template_exists(name) requires template name.', line)
        return str(args[0]) in _templates

    raise EPLRuntimeError(f'Unknown template function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  HTML Builder Module (Phase 3)
# ═══════════════════════════════════════════════════════════

def _build_attrs(attrs):
    """Build HTML attribute string from dict. Escapes values for safety."""
    import html as _html_mod
    if not attrs:
        return ''
    parts = []
    for k, v in attrs.items():
        if not _re.match(r'^[a-zA-Z_][\w-]*$', str(k)):
            continue
        parts.append(f' {_html_mod.escape(str(k))}="{_html_mod.escape(str(v))}"')
    return ''.join(parts)


def _call_html(name, args, line):
    """Dispatch html_* stdlib functions."""
    import html as _html_mod
    from epl.interpreter import EPLDict

    if name == 'html_element':
        if not args:
            raise EPLRuntimeError('html_element(tag[, content, attrs]) requires tag.', line)
        tag = str(args[0])
        if not _re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', tag):
            raise EPLRuntimeError(f'Invalid HTML tag: {tag}', line)
        content = str(args[1]) if len(args) > 1 and args[1] is not None else ''
        attrs = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict): attrs = args[2]
        attr_str = _build_attrs(attrs)
        void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
        if tag.lower() in void_tags:
            return f'<{tag}{attr_str}>'
        return f'<{tag}{attr_str}>{content}</{tag}>'

    if name == 'html_table':
        if len(args) < 2:
            raise EPLRuntimeError('html_table(headers, rows[, attrs]) requires headers and rows.', line)
        headers = args[0] if isinstance(args[0], list) else [args[0]]
        rows = args[1] if isinstance(args[1], list) else []
        attrs = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict): attrs = args[2]
        attr_str = _build_attrs(attrs)
        parts = [f'<table{attr_str}>', '<thead><tr>']
        for h in headers:
            parts.append(f'<th>{_html_mod.escape(str(h))}</th>')
        parts.append('</tr></thead><tbody>')
        for row in rows:
            parts.append('<tr>')
            cells = row if isinstance(row, list) else [row]
            for cell in cells:
                parts.append(f'<td>{_html_mod.escape(str(cell))}</td>')
            parts.append('</tr>')
        parts.append('</tbody></table>')
        return ''.join(parts)

    if name == 'html_form':
        if not args:
            raise EPLRuntimeError('html_form(action[, method, fields]) requires action.', line)
        action = _html_mod.escape(str(args[0]))
        method = _html_mod.escape(str(args[1])) if len(args) > 1 else 'POST'
        fields = args[2] if len(args) > 2 and isinstance(args[2], list) else []
        parts = [f'<form action="{action}" method="{method}">']
        for field in fields:
            if isinstance(field, EPLDict): fd = field.data
            elif isinstance(field, dict): fd = field
            else: continue
            ftype = _html_mod.escape(str(fd.get('type', 'text')))
            fname = _html_mod.escape(str(fd.get('name', '')))
            flabel = fd.get('label', '')
            fplaceholder = _html_mod.escape(str(fd.get('placeholder', '')))
            frequired = ' required' if fd.get('required') else ''
            if flabel:
                parts.append(f'<label for="{fname}">{_html_mod.escape(str(flabel))}</label>')
            if ftype == 'textarea':
                parts.append(f'<textarea name="{fname}" placeholder="{fplaceholder}"{frequired}></textarea>')
            elif ftype == 'select':
                options = fd.get('options', [])
                parts.append(f'<select name="{fname}"{frequired}>')
                if isinstance(options, list):
                    for opt in options:
                        parts.append(f'<option value="{_html_mod.escape(str(opt))}">{_html_mod.escape(str(opt))}</option>')
                parts.append('</select>')
            elif ftype == 'submit':
                fvalue = _html_mod.escape(str(fd.get('value', 'Submit')))
                parts.append(f'<input type="submit" value="{fvalue}">')
            else:
                parts.append(f'<input type="{ftype}" name="{fname}" placeholder="{fplaceholder}"{frequired}>')
        parts.append('</form>')
        return ''.join(parts)

    if name == 'html_list':
        if not args:
            raise EPLRuntimeError('html_list(items[, ordered]) requires items.', line)
        items = args[0] if isinstance(args[0], list) else [args[0]]
        ordered = bool(args[1]) if len(args) > 1 else False
        tag = 'ol' if ordered else 'ul'
        parts = [f'<{tag}>']
        for item in items:
            parts.append(f'<li>{_html_mod.escape(str(item))}</li>')
        parts.append(f'</{tag}>')
        return ''.join(parts)

    if name == 'html_link':
        if not args:
            raise EPLRuntimeError('html_link(href[, text, attrs]) requires href.', line)
        href = str(args[0])
        if _re.match(r'^\s*javascript\s*:', href, _re.IGNORECASE):
            raise EPLRuntimeError('html_link() does not allow javascript: URIs.', line)
        text = str(args[1]) if len(args) > 1 else href
        attrs = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict): attrs = args[2]
        attrs['href'] = href
        attr_str = _build_attrs(attrs)
        return f'<a{attr_str}>{_html_mod.escape(text)}</a>'

    if name == 'html_image':
        if not args:
            raise EPLRuntimeError('html_image(src[, alt, attrs]) requires src.', line)
        src = str(args[0])
        alt = str(args[1]) if len(args) > 1 else ''
        attrs = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict): attrs = args[2]
        attrs['src'] = src
        attrs['alt'] = alt
        attr_str = _build_attrs(attrs)
        return f'<img{attr_str}>'

    if name == 'html_page':
        if not args:
            raise EPLRuntimeError('html_page(title[, body, css, js]) requires title.', line)
        title = _html_mod.escape(str(args[0]))
        body = str(args[1]) if len(args) > 1 else ''
        css = str(args[2]) if len(args) > 2 and args[2] else ''
        js = str(args[3]) if len(args) > 3 and args[3] else ''
        css_tag = f'<style>{css}</style>' if css else ''
        js_tag = f'<script>{js}</script>' if js else ''
        return (
            '<!DOCTYPE html>'
            f'<html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title>{css_tag}</head>'
            f'<body>{body}{js_tag}</body></html>'
        )

    if name == 'html_escape':
        if not args:
            raise EPLRuntimeError('html_escape(text) requires text.', line)
        return _html_mod.escape(str(args[0]))

    if name == 'html_unescape':
        if not args:
            raise EPLRuntimeError('html_unescape(text) requires text.', line)
        return _html_mod.unescape(str(args[0]))

    if name == 'html_minify':
        if not args:
            raise EPLRuntimeError('html_minify(html) requires HTML string.', line)
        text = str(args[0])
        text = _re.sub(r'<!--.*?-->', '', text, flags=_re.DOTALL)
        text = _re.sub(r'>\s+<', '><', text)
        text = _re.sub(r'\s+', ' ', text)
        return text.strip()

    raise EPLRuntimeError(f'Unknown html function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  API Helpers Module (Phase 3)
# ═══════════════════════════════════════════════════════════

def _call_api(name, args, line):
    """Dispatch api_* stdlib functions."""
    from epl.interpreter import EPLDict

    if name == 'api_paginate':
        if not args:
            raise EPLRuntimeError('api_paginate(items[, page, per_page]) requires items.', line)
        items = args[0] if isinstance(args[0], list) else []
        page = max(1, int(args[1])) if len(args) > 1 else 1
        per_page = max(1, min(int(args[2]), 1000)) if len(args) > 2 else 20
        total = len(items)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start = (page - 1) * per_page
        page_items = items[start:start + per_page]
        return _to_epl({
            'items': page_items, 'page': page, 'per_page': per_page,
            'total': total, 'total_pages': total_pages,
            'has_next': page < total_pages, 'has_prev': page > 1,
        })

    if name == 'api_validate':
        if len(args) < 2:
            raise EPLRuntimeError('api_validate(data, schema) requires data and schema.', line)
        data = _from_epl(args[0]) if isinstance(args[0], EPLDict) else args[0]
        schema = _from_epl(args[1]) if isinstance(args[1], EPLDict) else args[1]
        if not isinstance(data, dict) or not isinstance(schema, dict):
            return _to_epl({'valid': False, 'errors': ['data and schema must be dicts']})
        errors = []
        for field, rules in schema.items():
            if isinstance(rules, str):
                rules = {'type': rules}
            elif isinstance(rules, EPLDict):
                rules = rules.data
            value = data.get(field)
            field_type = rules.get('type', 'string') if isinstance(rules, dict) else str(rules)
            required = rules.get('required', False) if isinstance(rules, dict) else False
            if value is None or value == '':
                if required:
                    errors.append(f'{field} is required')
                continue
            if field_type == 'string' and not isinstance(value, str):
                errors.append(f'{field} must be a string')
            elif field_type == 'number' and not isinstance(value, (int, float)):
                errors.append(f'{field} must be a number')
            elif field_type == 'integer' and not isinstance(value, int):
                errors.append(f'{field} must be an integer')
            elif field_type == 'boolean' and not isinstance(value, bool):
                errors.append(f'{field} must be a boolean')
            elif field_type == 'list' and not isinstance(value, list):
                errors.append(f'{field} must be a list')
            if isinstance(rules, dict):
                if 'min' in rules and isinstance(value, (int, float)) and value < rules['min']:
                    errors.append(f'{field} must be >= {rules["min"]}')
                if 'max' in rules and isinstance(value, (int, float)) and value > rules['max']:
                    errors.append(f'{field} must be <= {rules["max"]}')
                if 'min_length' in rules and isinstance(value, str) and len(value) < rules['min_length']:
                    errors.append(f'{field} must be at least {rules["min_length"]} characters')
                if 'max_length' in rules and isinstance(value, str) and len(value) > rules['max_length']:
                    errors.append(f'{field} must be at most {rules["max_length"]} characters')
                if 'pattern' in rules and isinstance(value, str):
                    if not _re.match(rules['pattern'], value):
                        errors.append(f'{field} does not match required pattern')
                if 'enum' in rules and value not in rules['enum']:
                    errors.append(f'{field} must be one of: {rules["enum"]}')
        return _to_epl({'valid': len(errors) == 0, 'errors': errors})

    if name == 'api_error':
        if not args:
            raise EPLRuntimeError('api_error(message[, status, details]) requires message.', line)
        message = str(args[0])
        status = int(args[1]) if len(args) > 1 else 400
        details = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else None
        if len(args) > 2 and isinstance(args[2], dict):
            details = args[2]
        resp = {'error': True, 'message': message, 'status': status}
        if details:
            resp['details'] = details
        try:
            flask = _ensure_flask()
            return flask.jsonify(resp), status
        except Exception:
            return _to_epl(resp)

    if name == 'api_success':
        data = _from_epl(args[0]) if args and isinstance(args[0], EPLDict) else (args[0] if args else None)
        message = str(args[1]) if len(args) > 1 else 'Success'
        meta = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else None
        resp = {'success': True, 'message': message}
        if data is not None:
            resp['data'] = data
        if meta:
            resp['meta'] = meta
        try:
            flask = _ensure_flask()
            return flask.jsonify(resp)
        except Exception:
            return _to_epl(resp)

    if name == 'api_response':
        if not args:
            raise EPLRuntimeError('api_response(data[, status, headers, content_type]) requires data.', line)
        data = _from_epl(args[0]) if isinstance(args[0], EPLDict) else args[0]
        status = int(args[1]) if len(args) > 1 else 200
        headers = _from_epl(args[2]) if len(args) > 2 and isinstance(args[2], EPLDict) else {}
        if len(args) > 2 and isinstance(args[2], dict): headers = args[2]
        content_type = str(args[3]) if len(args) > 3 else 'application/json'
        try:
            flask = _ensure_flask()
            if content_type == 'application/json':
                resp = flask.jsonify(data)
            else:
                resp = flask.make_response(str(data))
                resp.content_type = content_type
            resp.status_code = status
            for k, v in headers.items():
                resp.headers[str(k)] = str(v)
            return resp
        except Exception:
            return _to_epl({'data': data, 'status': status})

    if name == 'api_parse_query':
        if not args:
            raise EPLRuntimeError('api_parse_query(query_string) requires query string.', line)
        qs = str(args[0])
        if qs.startswith('?'): qs = qs[1:]
        return _to_epl(dict(_urllib_parse.parse_qsl(qs)))

    if name == 'api_version':
        if len(args) < 2:
            raise EPLRuntimeError('api_version(app_id, version[, prefix]) requires app_id and version.', line)
        app_id = str(args[0])
        if app_id not in _web_apps:
            raise EPLRuntimeError(f'Unknown web app: {app_id}', line)
        version = str(args[1])
        prefix = str(args[2]) if len(args) > 2 else '/api'
        flask = _ensure_flask()
        bp = flask.Blueprint(f'api_{version}_{_new_id()}', __name__, url_prefix=f'{prefix}/{version}')
        _web_apps[app_id].register_blueprint(bp)
        return f'{prefix}/{version}'

    if name == 'api_link_header':
        if len(args) < 4:
            raise EPLRuntimeError('api_link_header(url, page, per_page, total) requires 4 args.', line)
        url = str(args[0])
        page = int(args[1])
        per_page = int(args[2])
        total = int(args[3])
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        links = []
        if page > 1:
            links.append(f'<{url}?page=1&per_page={per_page}>; rel="first"')
            links.append(f'<{url}?page={page - 1}&per_page={per_page}>; rel="prev"')
        if page < total_pages:
            links.append(f'<{url}?page={page + 1}&per_page={per_page}>; rel="next"')
            links.append(f'<{url}?page={total_pages}&per_page={per_page}>; rel="last"')
        return ', '.join(links)

    raise EPLRuntimeError(f'Unknown api function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Desktop GUI Module (Tkinter-powered)
# ═══════════════════════════════════════════════════════════

_gui_windows = {}     # window_id -> Tk/Toplevel
_gui_widgets = {}     # widget_id -> widget
_gui_vars = {}        # widget_id -> StringVar/IntVar etc.
_gui_callbacks = {}   # widget_id -> callback

# Cross-platform font: use TkDefaultFont as the safe fallback
_GUI_FONT_FAMILY = 'TkDefaultFont'

_tk_cache = [None]


def _widget_belongs_to(widget, window):
    """Return True if *widget* is a descendant of *window*."""
    try:
        w = widget
        while w is not None:
            if w is window:
                return True
            w = w.master
    except Exception:
        pass
    return False


def _ensure_tk():
    """Import tkinter. Caches the imports."""
    if _tk_cache[0] is not None:
        return _tk_cache[0]
    try:
        import tkinter as tk
        import tkinter.ttk as ttk
        import tkinter.messagebox as messagebox
        import tkinter.filedialog as filedialog
    except ImportError:
        raise EPLRuntimeError(
            'tkinter is not available. On Linux: sudo apt install python3-tk. '
            'On macOS: brew install python-tk. On Windows: reinstall Python with tk option.', 0)
    _tk_cache[0] = (tk, ttk, messagebox, filedialog)
    return _tk_cache[0]

def _call_gui(name, args, line):
    """Dispatch gui_* stdlib functions."""
    from epl.interpreter import EPLDict
    tk, ttk, messagebox, filedialog = _ensure_tk()

    if name == 'gui_window':
        title = str(args[0]) if args else 'EPL Application'
        width = int(args[1]) if len(args) > 1 else 800
        height = int(args[2]) if len(args) > 2 else 600

        if not _gui_windows:
            root = tk.Tk()
        else:
            root = tk.Toplevel()
        root.title(title)
        root.geometry(f'{width}x{height}')
        wid = f'win_{_new_id()}'
        _gui_windows[wid] = root
        return wid

    if name == 'gui_label':
        if not args:
            raise EPLRuntimeError('gui_label(window_id, text[, font_size, color]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        text = str(args[1]) if len(args) > 1 else ''
        font_size = int(args[2]) if len(args) > 2 else 12
        color = str(args[3]) if len(args) > 3 else 'black'
        label = ttk.Label(parent, text=text, font=(_GUI_FONT_FAMILY, font_size), foreground=color)
        label.pack(pady=5)
        lid = f'lbl_{_new_id()}'
        _gui_widgets[lid] = label
        return lid

    if name == 'gui_button':
        if len(args) < 2:
            raise EPLRuntimeError('gui_button(window_id, text[, callback]) requires window_id and text.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        text = str(args[1])
        callback = args[2] if len(args) > 2 else None
        cmd = None
        if callback and callable(callback):
            def make_cmd(cb):
                def handler():
                    try:
                        cb()
                    except Exception as e:
                        messagebox.showerror('EPL Error', str(e))
                return handler
            cmd = make_cmd(callback)
        btn = ttk.Button(parent, text=text, command=cmd)
        btn.pack(pady=5)
        bid = f'btn_{_new_id()}'
        _gui_widgets[bid] = btn
        if callback:
            _gui_callbacks[bid] = callback
        return bid

    if name == 'gui_input':
        if not args:
            raise EPLRuntimeError('gui_input(window_id[, placeholder, width]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        placeholder = str(args[1]) if len(args) > 1 else ''
        width = int(args[2]) if len(args) > 2 else 30
        var = tk.StringVar(value=placeholder)
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.pack(pady=5)
        eid = f'inp_{_new_id()}'
        _gui_widgets[eid] = entry
        _gui_vars[eid] = var
        return eid

    if name == 'gui_text':
        if not args:
            raise EPLRuntimeError('gui_text(window_id[, height, width]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        height = int(args[1]) if len(args) > 1 else 10
        width = int(args[2]) if len(args) > 2 else 40
        text_widget = tk.Text(parent, height=height, width=width, font=('TkFixedFont', 11))
        text_widget.pack(pady=5, fill=tk.BOTH, expand=True)
        tid = f'txt_{_new_id()}'
        _gui_widgets[tid] = text_widget
        return tid

    if name == 'gui_checkbox':
        if len(args) < 2:
            raise EPLRuntimeError('gui_checkbox(window_id, text[, callback]) requires window_id and text.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        text = str(args[1])
        var = tk.BooleanVar()
        callback = args[2] if len(args) > 2 else None
        cmd = None
        if callback and callable(callback):
            def make_cb(cb):
                def handler():
                    try:
                        cb()
                    except Exception as e:
                        messagebox.showerror('EPL Error', str(e))
                return handler
            cmd = make_cb(callback)
        cb_widget = ttk.Checkbutton(parent, text=text, variable=var, command=cmd)
        cb_widget.pack(pady=3)
        cid = f'chk_{_new_id()}'
        _gui_widgets[cid] = cb_widget
        _gui_vars[cid] = var
        return cid

    if name == 'gui_dropdown':
        if len(args) < 2:
            raise EPLRuntimeError('gui_dropdown(window_id, options[, callback]) requires window_id and options list.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        options = args[1] if isinstance(args[1], list) else [str(args[1])]
        var = tk.StringVar(value=options[0] if options else '')
        callback = args[2] if len(args) > 2 else None
        dd = ttk.Combobox(parent, textvariable=var, values=options, state='readonly')
        dd.pack(pady=5)
        if callback and callable(callback):
            def make_dd_cmd(cb):
                def handler(e):
                    try:
                        cb(e.widget.get())
                    except Exception as exc:
                        messagebox.showerror('EPL Error', str(exc))
                return handler
            dd.bind('<<ComboboxSelected>>', make_dd_cmd(callback))
        did = f'dd_{_new_id()}'
        _gui_widgets[did] = dd
        _gui_vars[did] = var
        return did

    if name == 'gui_slider':
        if not args:
            raise EPLRuntimeError('gui_slider(window_id[, min, max, callback]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        min_val = float(args[1]) if len(args) > 1 else 0
        max_val = float(args[2]) if len(args) > 2 else 100
        var = tk.DoubleVar(value=min_val)
        callback = args[3] if len(args) > 3 else None
        cmd = None
        if callback and callable(callback):
            def make_slider_cmd(cb):
                def handler(val):
                    try:
                        cb(float(val))
                    except Exception as e:
                        messagebox.showerror('EPL Error', str(e))
                return handler
            cmd = make_slider_cmd(callback)
        slider = ttk.Scale(parent, from_=min_val, to=max_val, variable=var, command=cmd)
        slider.pack(pady=5, fill=tk.X)
        sid = f'sld_{_new_id()}'
        _gui_widgets[sid] = slider
        _gui_vars[sid] = var
        return sid

    if name == 'gui_image':
        if len(args) < 2:
            raise EPLRuntimeError('gui_image(window_id, file_path) requires window_id and image path.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        path = str(args[1])
        ext = _os.path.splitext(path)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
            # Use Pillow for formats tkinter can't handle natively
            try:
                from PIL import Image, ImageTk  # type: ignore[import-not-found]
                pil_img = Image.open(path)
                img = ImageTk.PhotoImage(pil_img)
            except ImportError:
                raise EPLRuntimeError(
                    f'Pillow is required for {ext} images. Install with: pip install Pillow', line)
        else:
            from tkinter import PhotoImage
            img = PhotoImage(file=path)
        label = tk.Label(parent, image=img)
        label.image = img  # keep reference
        label.pack(pady=5)
        iid = f'img_{_new_id()}'
        _gui_widgets[iid] = label
        return iid

    if name == 'gui_frame':
        if not args:
            raise EPLRuntimeError('gui_frame(window_id) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        frame = ttk.Frame(parent)
        frame.pack(pady=5, fill=tk.BOTH, expand=True)
        fid = f'frm_{_new_id()}'
        _gui_widgets[fid] = frame
        return fid

    if name == 'gui_grid':
        if len(args) < 3:
            raise EPLRuntimeError('gui_grid(widget_id, row, col[, colspan, rowspan]) requires widget_id, row, col.', line)
        widget_id = str(args[0])
        widget = _gui_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown widget: {widget_id}', line)
        row = int(args[1])
        col = int(args[2])
        colspan = int(args[3]) if len(args) > 3 else 1
        rowspan = int(args[4]) if len(args) > 4 else 1
        widget.pack_forget()
        widget.grid(row=row, column=col, columnspan=colspan, rowspan=rowspan, padx=5, pady=5)
        return None

    if name == 'gui_pack':
        if not args:
            raise EPLRuntimeError('gui_pack(widget_id[, side, fill, expand]) requires widget_id.', line)
        widget_id = str(args[0])
        widget = _gui_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown widget: {widget_id}', line)
        side = str(args[1]) if len(args) > 1 else 'top'
        fill = str(args[2]) if len(args) > 2 else 'none'
        expand = bool(args[3]) if len(args) > 3 else False
        widget.pack_forget()
        widget.pack(side=side, fill=fill, expand=expand, padx=5, pady=5)
        return None

    if name == 'gui_place':
        if len(args) < 3:
            raise EPLRuntimeError('gui_place(widget_id, x, y) requires widget_id, x, y.', line)
        widget_id = str(args[0])
        widget = _gui_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown widget: {widget_id}', line)
        widget.pack_forget()
        widget.place(x=int(args[1]), y=int(args[2]))
        return None

    if name == 'gui_on_click':
        if len(args) < 2:
            raise EPLRuntimeError('gui_on_click(widget_id, callback) requires widget_id and callback.', line)
        widget_id = str(args[0])
        widget = _gui_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown widget: {widget_id}', line)
        callback = args[1]
        if callable(callback):
            widget.bind('<Button-1>', lambda e: callback())
        _gui_callbacks[widget_id] = callback
        return None

    if name == 'gui_get_value':
        if not args:
            raise EPLRuntimeError('gui_get_value(widget_id) requires widget_id.', line)
        widget_id = str(args[0])
        if widget_id in _gui_vars:
            return _gui_vars[widget_id].get()
        widget = _gui_widgets.get(widget_id)
        if widget and isinstance(widget, tk.Text):
            return widget.get('1.0', tk.END).rstrip('\n')
        if widget and hasattr(widget, 'get'):
            return widget.get()
        raise EPLRuntimeError(f'Cannot get value from widget: {widget_id}', line)

    if name == 'gui_set_value':
        if len(args) < 2:
            raise EPLRuntimeError('gui_set_value(widget_id, value) requires widget_id and value.', line)
        widget_id = str(args[0])
        value = args[1]
        if widget_id in _gui_vars:
            _gui_vars[widget_id].set(value)
            return None
        widget = _gui_widgets.get(widget_id)
        if widget and isinstance(widget, tk.Text):
            widget.delete('1.0', tk.END)
            widget.insert('1.0', str(value))
            return None
        if widget and isinstance(widget, ttk.Label):
            widget.configure(text=str(value))
            return None
        raise EPLRuntimeError(f'Cannot set value on widget: {widget_id}', line)

    if name == 'gui_messagebox':
        title = str(args[0]) if args else 'EPL'
        message = str(args[1]) if len(args) > 1 else ''
        msg_type = str(args[2]) if len(args) > 2 else 'info'
        if msg_type == 'error':
            messagebox.showerror(title, message)
        elif msg_type == 'warning':
            messagebox.showwarning(title, message)
        elif msg_type == 'question':
            return messagebox.askyesno(title, message)
        else:
            messagebox.showinfo(title, message)
        return None

    if name == 'gui_file_dialog':
        dialog_type = str(args[0]) if args else 'open'
        filetypes = [('All files', '*.*')]
        if dialog_type == 'save':
            return filedialog.asksaveasfilename(filetypes=filetypes) or ''
        elif dialog_type == 'folder':
            return filedialog.askdirectory() or ''
        else:
            return filedialog.askopenfilename(filetypes=filetypes) or ''

    if name == 'gui_run':
        # Start the Tkinter main loop
        if not _gui_windows:
            raise EPLRuntimeError('No GUI window created. Call gui_window() first.', line)
        # Use specific window if provided, otherwise first window
        if args:
            wid = str(args[0])
            root = _gui_windows.get(wid)
            if not root:
                raise EPLRuntimeError(f'Unknown window: {wid}', line)
        else:
            root = list(_gui_windows.values())[0]
        root.mainloop()
        return None

    if name == 'gui_menu':
        if not args:
            raise EPLRuntimeError('gui_menu(window_id) requires window_id.', line)
        wid = str(args[0])
        window = _gui_windows.get(wid)
        if not window:
            raise EPLRuntimeError(f'Unknown window: {wid}', line)
        menubar = tk.Menu(window)
        window.config(menu=menubar)
        mid = f'menu_{_new_id()}'
        _gui_widgets[mid] = menubar
        return mid

    if name == 'gui_menu_item':
        if len(args) < 3:
            raise EPLRuntimeError('gui_menu_item(menu_id, label, callback) requires menu_id, label, callback.', line)
        mid = str(args[0])
        menu = _gui_widgets.get(mid)
        if not menu or not isinstance(menu, tk.Menu):
            raise EPLRuntimeError(f'Unknown menu: {mid}', line)
        label = str(args[1])
        callback = args[2]
        cmd = callback if callable(callback) else None
        menu.add_command(label=label, command=cmd)
        return None

    if name == 'gui_canvas':
        if not args:
            raise EPLRuntimeError('gui_canvas(window_id[, width, height, bg]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        width = int(args[1]) if len(args) > 1 else 400
        height = int(args[2]) if len(args) > 2 else 300
        bg = str(args[3]) if len(args) > 3 else 'white'
        canvas = tk.Canvas(parent, width=width, height=height, bg=bg)
        canvas.pack(pady=5)
        cid = f'cvs_{_new_id()}'
        _gui_widgets[cid] = canvas
        return cid

    if name == 'gui_draw_rect':
        if len(args) < 5:
            raise EPLRuntimeError('gui_draw_rect(canvas_id, x, y, width, height[, color]) requires 5 args.', line)
        cid = str(args[0])
        canvas = _gui_widgets.get(cid)
        if not canvas or not isinstance(canvas, tk.Canvas):
            raise EPLRuntimeError(f'Unknown canvas: {cid}', line)
        x, y, w, h = int(args[1]), int(args[2]), int(args[3]), int(args[4])
        color = str(args[5]) if len(args) > 5 else 'black'
        return canvas.create_rectangle(x, y, x + w, y + h, fill=color)

    if name == 'gui_draw_circle':
        if len(args) < 4:
            raise EPLRuntimeError('gui_draw_circle(canvas_id, x, y, radius[, color]) requires 4 args.', line)
        cid = str(args[0])
        canvas = _gui_widgets.get(cid)
        if not canvas or not isinstance(canvas, tk.Canvas):
            raise EPLRuntimeError(f'Unknown canvas: {cid}', line)
        x, y, r = int(args[1]), int(args[2]), int(args[3])
        color = str(args[4]) if len(args) > 4 else 'black'
        return canvas.create_oval(x - r, y - r, x + r, y + r, fill=color)

    if name == 'gui_draw_line':
        if len(args) < 5:
            raise EPLRuntimeError('gui_draw_line(canvas_id, x1, y1, x2, y2[, color]) requires 5 args.', line)
        cid = str(args[0])
        canvas = _gui_widgets.get(cid)
        if not canvas or not isinstance(canvas, tk.Canvas):
            raise EPLRuntimeError(f'Unknown canvas: {cid}', line)
        x1, y1, x2, y2 = int(args[1]), int(args[2]), int(args[3]), int(args[4])
        color = str(args[5]) if len(args) > 5 else 'black'
        return canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

    if name == 'gui_draw_text':
        if len(args) < 4:
            raise EPLRuntimeError('gui_draw_text(canvas_id, x, y, text[, color, font_size]) requires 4 args.', line)
        cid = str(args[0])
        canvas = _gui_widgets.get(cid)
        if not canvas or not isinstance(canvas, tk.Canvas):
            raise EPLRuntimeError(f'Unknown canvas: {cid}', line)
        x, y = int(args[1]), int(args[2])
        text = str(args[3])
        color = str(args[4]) if len(args) > 4 else 'black'
        font_size = int(args[5]) if len(args) > 5 else 12
        return canvas.create_text(x, y, text=text, fill=color, font=(_GUI_FONT_FAMILY, font_size))

    if name == 'gui_style':
        if len(args) < 2:
            raise EPLRuntimeError('gui_style(widget_id, options_map) requires widget_id and options.', line)
        widget_id = str(args[0])
        widget = _gui_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown widget: {widget_id}', line)
        options = _from_epl(args[1]) if isinstance(args[1], EPLDict) else {}
        # Allowlist safe style properties to prevent injection via 'command' etc.
        _SAFE_STYLE_KEYS = frozenset({
            'bg', 'fg', 'background', 'foreground', 'font', 'text',
            'width', 'height', 'relief', 'borderwidth', 'padx', 'pady',
            'anchor', 'justify', 'wraplength', 'state', 'cursor',
        })
        unsafe_keys = set(options.keys()) - _SAFE_STYLE_KEYS
        if unsafe_keys:
            raise EPLRuntimeError(
                f'gui_style: unsafe properties not allowed: {unsafe_keys}. '
                f'Allowed: {sorted(_SAFE_STYLE_KEYS)}', line)
        try:
            widget.configure(**options)
        except Exception as e:
            raise EPLRuntimeError(f'Style error: {e}', line)
        return None

    if name == 'gui_close':
        if not args:
            # Close all windows and clean up ALL state
            for w in _gui_windows.values():
                w.destroy()
            _gui_windows.clear()
            _gui_widgets.clear()
            _gui_vars.clear()
            _gui_callbacks.clear()
            return None
        wid = str(args[0])
        window = _gui_windows.get(wid)
        if window:
            window.destroy()
            del _gui_windows[wid]
            # Clean up child widgets, vars, and callbacks belonging to this window
            dead_ids = [k for k, v in _gui_widgets.items()
                        if _widget_belongs_to(v, window)]
            for k in dead_ids:
                _gui_widgets.pop(k, None)
                _gui_vars.pop(k, None)
                _gui_callbacks.pop(k, None)
        return None

    if name == 'gui_update':
        if not _gui_windows:
            return None
        root = list(_gui_windows.values())[0]
        root.update()
        return None

    if name == 'gui_after':
        if len(args) < 2:
            raise EPLRuntimeError('gui_after(delay_ms, callback) requires delay and callback.', line)
        delay = int(args[0])
        callback = args[1]
        if not _gui_windows:
            raise EPLRuntimeError('No GUI window exists.', line)
        root = list(_gui_windows.values())[0]
        if callable(callback):
            root.after(delay, callback)
        return None

    if name == 'gui_list':
        if not args:
            raise EPLRuntimeError('gui_list(window_id[, items, height]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        items = args[1] if len(args) > 1 and isinstance(args[1], list) else []
        height = int(args[2]) if len(args) > 2 else 10
        listbox = tk.Listbox(parent, height=height, font=(_GUI_FONT_FAMILY, 11))
        for item in items:
            listbox.insert(tk.END, str(item))
        listbox.pack(pady=5, fill=tk.BOTH, expand=True)
        lid = f'lst_{_new_id()}'
        _gui_widgets[lid] = listbox
        return lid

    if name == 'gui_table':
        if not args:
            raise EPLRuntimeError('gui_table(window_id, columns[, rows]) requires window_id and columns.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        columns = args[1] if isinstance(args[1], list) else [str(args[1])]
        rows = args[2] if len(args) > 2 and isinstance(args[2], list) else []
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=str(col))
            tree.column(col, width=120)
        for row in rows:
            if isinstance(row, list):
                tree.insert('', tk.END, values=row)
        tree.pack(pady=5, fill=tk.BOTH, expand=True)
        tid = f'tbl_{_new_id()}'
        _gui_widgets[tid] = tree
        return tid

    if name == 'gui_progress':
        if not args:
            raise EPLRuntimeError('gui_progress(window_id[, max_value, mode]) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        max_val = int(args[1]) if len(args) > 1 else 100
        mode = str(args[2]) if len(args) > 2 else 'determinate'
        var = tk.DoubleVar(value=0)
        progress = ttk.Progressbar(parent, maximum=max_val, mode=mode, variable=var)
        progress.pack(pady=5, fill=tk.X)
        pid = f'prg_{_new_id()}'
        _gui_widgets[pid] = progress
        _gui_vars[pid] = var
        return pid

    if name == 'gui_tab':
        if not args:
            raise EPLRuntimeError('gui_tab(window_id) requires window_id.', line)
        wid = str(args[0])
        parent = _gui_windows.get(wid) or _gui_widgets.get(wid)
        if not parent:
            raise EPLRuntimeError(f'Unknown window/widget: {wid}', line)
        notebook = ttk.Notebook(parent)
        notebook.pack(pady=5, fill=tk.BOTH, expand=True)
        nid = f'tab_{_new_id()}'
        _gui_widgets[nid] = notebook
        return nid

    if name == 'gui_tab_add':
        if len(args) < 2:
            raise EPLRuntimeError('gui_tab_add(notebook_id, title) requires notebook_id and title.', line)
        nid = str(args[0])
        notebook = _gui_widgets.get(nid)
        if not notebook or not isinstance(notebook, ttk.Notebook):
            raise EPLRuntimeError(f'Unknown notebook: {nid}', line)
        title = str(args[1])
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        fid = f'tabf_{_new_id()}'
        _gui_widgets[fid] = frame
        return fid

    if name == 'gui_submenu':
        if len(args) < 2:
            raise EPLRuntimeError('gui_submenu(menu_id, title) requires menu_id and title.', line)
        mid = str(args[0])
        parent_menu = _gui_widgets.get(mid)
        if not parent_menu or not isinstance(parent_menu, tk.Menu):
            raise EPLRuntimeError(f'Unknown menu: {mid}', line)
        title = str(args[1])
        submenu = tk.Menu(parent_menu, tearoff=0)
        parent_menu.add_cascade(label=title, menu=submenu)
        sid = f'mnu_{_new_id()}'
        _gui_widgets[sid] = submenu
        return sid

    if name == 'gui_list_on_select':
        if len(args) < 2:
            raise EPLRuntimeError('gui_list_on_select(listbox_id, callback) requires listbox_id and callback.', line)
        lid = str(args[0])
        listbox = _gui_widgets.get(lid)
        if not listbox or not isinstance(listbox, tk.Listbox):
            raise EPLRuntimeError(f'Unknown listbox: {lid}', line)
        callback = args[1]
        def make_select_handler(cb):
            def handler(event):
                sel = event.widget.curselection()
                if sel:
                    value = event.widget.get(sel[0])
                    try:
                        cb(value)
                    except Exception as e:
                        messagebox.showerror('EPL Error', str(e))
            return handler
        listbox.bind('<<ListboxSelect>>', make_select_handler(callback))
        return None

    raise EPLRuntimeError(f'Unknown GUI function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Mobile Builder (BeeWare / Toga)
# ═══════════════════════════════════════════════════════════

_mobile_apps = {}       # app_id -> {'toga_app': App, 'main_box': Box, ...}
_mobile_widgets = {}    # widget_id -> toga widget
_mobile_screens = {}    # screen_name -> toga Box
_mobile_callbacks = {}  # widget_id -> callback
_mobile_widget_meta = {}  # widget_id -> {'type': str, ...props}  — for Android export
_toga_cache = [None]
_pygame_cache = [None]
_sklearn_cache = [None]
_joblib_cache = [None]


def _setup_toga(toga):
    """Attach style helpers to the toga module for internal use."""
    from toga.style import Pack            # type: ignore[import-not-found]
    from toga.style.pack import COLUMN, ROW  # type: ignore[import-not-found]
    toga._Pack = Pack
    toga._COLUMN = COLUMN
    toga._ROW = ROW
    return toga


def _ensure_toga():
    """Lazy-import toga, auto-install if missing. Returns the toga module."""
    if _toga_cache[0] is not None:
        return _toga_cache[0]
    try:
        import toga                      # type: ignore[import-not-found]
        _toga_cache[0] = _setup_toga(toga)
        return _toga_cache[0]
    except ImportError:
        if not _auto_install('toga', 'Toga (BeeWare)'):
            raise EPLRuntimeError(
                'Failed to install Toga. Install manually: pip install toga', 0)
        try:
            import toga                  # type: ignore[import-not-found]
            _toga_cache[0] = _setup_toga(toga)
            return _toga_cache[0]
        except ImportError:
            raise EPLRuntimeError(
                'Installed toga but import still failed. Check pip output.', 0)


def _widget_meta_to_compose(meta, indent=2):
    """Convert a widget metadata dict to Jetpack Compose Kotlin code."""
    pad = '    ' * indent
    t = meta.get('type', '')
    lines = []
    if t == 'label':
        txt = _escape_kotlin_string(meta.get('text', ''))
        fs = meta.get('font_size', 14)
        lines.append(f'{pad}Text("{txt}", fontSize = {fs}.sp, modifier = Modifier.padding(5.dp))')
    elif t == 'button':
        txt = _escape_kotlin_string(meta.get('text', 'Button'))
        lines.append(f'{pad}Button(onClick = {{ /* TODO: add handler */ }}, modifier = Modifier.padding(5.dp)) {{')
        lines.append(f'{pad}    Text("{txt}")')
        lines.append(f'{pad}}}')
    elif t == 'input':
        ph = _escape_kotlin_string(meta.get('placeholder', ''))
        lines.append(f'{pad}var textField by remember {{ mutableStateOf("") }}')
        lines.append(f'{pad}OutlinedTextField(')
        lines.append(f'{pad}    value = textField,')
        lines.append(f'{pad}    onValueChange = {{ textField = it }},')
        lines.append(f'{pad}    label = {{ Text("{ph}") }},')
        lines.append(f'{pad}    modifier = Modifier.fillMaxWidth().padding(5.dp)')
        lines.append(f'{pad})')
    elif t == 'image':
        lines.append(f'{pad}// Image: {_escape_kotlin_string(meta.get("path", "unknown"))}')
        lines.append(f'{pad}Image(')
        lines.append(f'{pad}    painter = painterResource(id = R.drawable.ic_launcher_foreground),')
        lines.append(f'{pad}    contentDescription = null,')
        lines.append(f'{pad}    modifier = Modifier.padding(5.dp)')
        lines.append(f'{pad})')
    elif t == 'box':
        dr = meta.get('direction', 'COLUMN')
        container = 'Row' if dr == 'ROW' else 'Column'
        lines.append(f'{pad}{container}(modifier = Modifier.fillMaxWidth().padding(5.dp)) {{')
        lines.append(f'{pad}    // Add child widgets here')
        lines.append(f'{pad}}}')
    elif t == 'scroll':
        lines.append(f'{pad}Column(modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {{')
        lines.append(f'{pad}    // Add scrollable content here')
        lines.append(f'{pad}}}')
    elif t == 'switch':
        lbl = _escape_kotlin_string(meta.get('label', 'Toggle'))
        lines.append(f'{pad}var switchState by remember {{ mutableStateOf(false) }}')
        lines.append(f'{pad}Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(5.dp)) {{')
        lines.append(f'{pad}    Text("{lbl}")')
        lines.append(f'{pad}    Spacer(modifier = Modifier.width(8.dp))')
        lines.append(f'{pad}    Switch(checked = switchState, onCheckedChange = {{ switchState = it }})')
        lines.append(f'{pad}}}')
    elif t == 'slider':
        mn = meta.get('min', 0.0)
        mx = meta.get('max', 100.0)
        lines.append(f'{pad}var sliderVal by remember {{ mutableStateOf({mn}f) }}')
        lines.append(f'{pad}Slider(')
        lines.append(f'{pad}    value = sliderVal,')
        lines.append(f'{pad}    onValueChange = {{ sliderVal = it }},')
        lines.append(f'{pad}    valueRange = {mn}f..{mx}f,')
        lines.append(f'{pad}    modifier = Modifier.padding(5.dp)')
        lines.append(f'{pad})')
    elif t == 'select':
        opts = meta.get('options', [])
        first_opt = _escape_kotlin_string(opts[0]) if opts else ''
        lines.append(f'{pad}var expanded by remember {{ mutableStateOf(false) }}')
        lines.append(f'{pad}var selectedOption by remember {{ mutableStateOf("{first_opt}") }}')
        lines.append(f'{pad}ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = {{ expanded = !expanded }}) {{')
        lines.append(f'{pad}    TextField(value = selectedOption, onValueChange = {{}}, readOnly = true, modifier = Modifier.menuAnchor())')
        lines.append(f'{pad}    ExposedDropdownMenu(expanded = expanded, onDismissRequest = {{ expanded = false }}) {{')
        for opt in opts:
            opt_esc = _escape_kotlin_string(opt)
            lines.append(f'{pad}        DropdownMenuItem(text = {{ Text("{opt_esc}") }}, onClick = {{ selectedOption = "{opt_esc}"; expanded = false }})')
        lines.append(f'{pad}    }}')
        lines.append(f'{pad}}}')
    elif t == 'webview':
        url = _escape_kotlin_string(meta.get('url', 'https://example.com'))
        lines.append(f'{pad}AndroidView(factory = {{ context ->')
        lines.append(f'{pad}    android.webkit.WebView(context).apply {{')
        lines.append(f'{pad}        settings.javaScriptEnabled = true')
        lines.append(f'{pad}        loadUrl("{url}")')
        lines.append(f'{pad}    }}')
        lines.append(f'{pad}}}, modifier = Modifier.fillMaxSize())')
    else:
        lines.append(f'{pad}// TODO: widget type "{_escape_kotlin_string(t)}"')
    return lines


def _generate_android_project(app_id, output_dir, package_name, title, line):
    """Generate a complete Android Studio project from an EPL mobile app."""
    import os as _os

    # Path traversal protection
    output_dir = _os.path.normpath(output_dir)
    if '..' in output_dir.split(_os.sep):
        raise EPLRuntimeError(f'Path traversal not allowed: {output_dir}', line)

    # Warn if output directory already exists
    if _os.path.isdir(output_dir) and _os.listdir(output_dir):
        print(f'[EPL] Warning: {output_dir} already exists. Files will be overwritten.',
              file=_sys.stderr)

    # Collect widgets belonging to this app
    app_widgets = [
        _mobile_widget_meta[wid]
        for wid in _mobile_widget_meta
        if _mobile_widget_meta[wid].get('app_id') == app_id
            and _mobile_widget_meta[wid].get('type') != 'screen'
    ]
    # Collect screens
    app_screens = {
        _mobile_widget_meta[wid].get('screen_name'): wid
        for wid in _mobile_widget_meta
        if _mobile_widget_meta[wid].get('app_id') == app_id
            and _mobile_widget_meta[wid].get('type') == 'screen'
    }

    pkg_path = package_name.replace('.', '/')
    safe_title = _re.sub(r'[^A-Za-z0-9]', '', title)
    if not safe_title or safe_title[0].isdigit():
        safe_title = 'EPL' + safe_title
    xml_title = _escape_xml(title)
    kt_title = _escape_kotlin_string(title)

    # ── Generate Compose code for main screen widgets ──
    compose_widgets = []
    for w in app_widgets:
        compose_widgets.extend(_widget_meta_to_compose(w, indent=3))
    if not compose_widgets:
        compose_widgets = ['            Text("Hello from EPL!", fontSize = 20.sp)']
    widget_code = '\n'.join(compose_widgets)

    # ── Generate screen composables ──
    screen_composables = []
    for screen_name in app_screens:
        safe_screen = _re.sub(r'[^A-Za-z0-9]', '', screen_name)
        if not safe_screen or safe_screen[0].isdigit():
            safe_screen = 'Screen' + safe_screen
        kt_screen_name = _escape_kotlin_string(screen_name)
        screen_composables.append(f'''
@Composable
fun {safe_screen}Screen() {{
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.Top
    ) {{
        Text("{kt_screen_name}", fontSize = 24.sp, fontWeight = FontWeight.Bold)
        // TODO: Add screen widgets
    }}
}}''')
    screen_code = '\n'.join(screen_composables)

    # ── Directory structure ──
    dirs = [
        f'{output_dir}/app/src/main/java/{pkg_path}',
        f'{output_dir}/app/src/main/java/{pkg_path}/ui/theme',
        f'{output_dir}/app/src/main/res/values',
        f'{output_dir}/app/src/main/res/drawable',
        f'{output_dir}/app/src/main/res/mipmap-hdpi',
        f'{output_dir}/gradle/wrapper',
    ]
    for d in dirs:
        _os.makedirs(d, exist_ok=True)

    try:
        _generate_android_files(output_dir, pkg_path, package_name, safe_title, xml_title, kt_title, widget_code, screen_code)
    except OSError as e:
        raise EPLRuntimeError(f'Failed to write Android project files: {e}', line)

    abs_path = _os.path.abspath(output_dir)
    print(f'[EPL] Android Studio project generated at: {abs_path}', file=_sys.stderr)
    print(f'[EPL] Open this folder in Android Studio to build and run.', file=_sys.stderr)
    return abs_path


def _generate_android_files(output_dir, pkg_path, package_name, safe_title, xml_title, kt_title, widget_code, screen_code):
    """Write all Android Studio project files. Separated for clean error handling."""

    # ── settings.gradle.kts ──
    with open(f'{output_dir}/settings.gradle.kts', 'w', encoding='utf-8') as f:
        f.write(f'''pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = "{safe_title}"
include(":app")
''')

    # ── build.gradle.kts (project-level) ──
    with open(f'{output_dir}/build.gradle.kts', 'w', encoding='utf-8') as f:
        f.write('''plugins {
    id("com.android.application") version "8.2.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.20" apply false
}
''')

    # ── app/build.gradle.kts ──
    with open(f'{output_dir}/app/build.gradle.kts', 'w', encoding='utf-8') as f:
        f.write(f'''plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}}

android {{
    namespace = "{package_name}"
    compileSdk = 34

    defaultConfig {{
        applicationId = "{package_name}"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }}

    buildFeatures {{
        compose = true
    }}

    composeOptions {{
        kotlinCompilerExtensionVersion = "1.5.5"
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlinOptions {{
        jvmTarget = "17"
    }}
}}

dependencies {{
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation(platform("androidx.compose:compose-bom:2024.01.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
}}
''')

    # ── AndroidManifest.xml ──
    with open(f'{output_dir}/app/src/main/AndroidManifest.xml', 'w', encoding='utf-8') as f:
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:allowBackup="true"
        android:label="{xml_title}"
        android:supportsRtl="true"
        android:theme="@style/Theme.{safe_title}">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.{safe_title}">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>

</manifest>
''')

    # ── MainActivity.kt ──
    with open(f'{output_dir}/app/src/main/java/{pkg_path}/MainActivity.kt', 'w', encoding='utf-8') as f:
        f.write(f'''package {package_name}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import {package_name}.ui.theme.{safe_title}Theme

class MainActivity : ComponentActivity() {{
    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        setContent {{
            {safe_title}Theme {{
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {{
                    MainScreen()
                }}
            }}
        }}
    }}
}}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {{
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Top
    ) {{
        Text(
            text = "{kt_title}",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 16.dp)
        )
{widget_code}
    }}
}}
{screen_code}
''')

    # ── Theme files ──
    with open(f'{output_dir}/app/src/main/java/{pkg_path}/ui/theme/Color.kt', 'w', encoding='utf-8') as f:
        f.write(f'''package {package_name}.ui.theme

import androidx.compose.ui.graphics.Color

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)
val Purple40 = Color(0xFF6650a4)
val PurpleGrey40 = Color(0xFF625b71)
val Pink40 = Color(0xFF7D5260)
''')

    with open(f'{output_dir}/app/src/main/java/{pkg_path}/ui/theme/Theme.kt', 'w', encoding='utf-8') as f:
        f.write(f'''package {package_name}.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = Purple80,
    secondary = PurpleGrey80,
    tertiary = Pink80
)

private val LightColorScheme = lightColorScheme(
    primary = Purple40,
    secondary = PurpleGrey40,
    tertiary = Pink40
)

@Composable
fun {safe_title}Theme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {{
    val colorScheme = when {{
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {{
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }}
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }}

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}}
''')

    # ── res/values/themes.xml ──
    with open(f'{output_dir}/app/src/main/res/values/themes.xml', 'w', encoding='utf-8') as f:
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.{safe_title}" parent="android:Theme.Material.Light.NoActionBar" />
</resources>
''')

    # ── res/values/strings.xml ──
    with open(f'{output_dir}/app/src/main/res/values/strings.xml', 'w', encoding='utf-8') as f:
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{xml_title}</string>
</resources>
''')

    # ── res/values/colors.xml ──
    with open(f'{output_dir}/app/src/main/res/values/colors.xml', 'w', encoding='utf-8') as f:
        f.write('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="purple_200">#FFBB86FC</color>
    <color name="purple_500">#FF6200EE</color>
    <color name="purple_700">#FF3700B3</color>
    <color name="teal_200">#FF03DAC5</color>
    <color name="teal_700">#FF018786</color>
    <color name="black">#FF000000</color>
    <color name="white">#FFFFFFFF</color>
</resources>
''')

    # ── gradle.properties ──
    with open(f'{output_dir}/gradle.properties', 'w', encoding='utf-8') as f:
        f.write('''android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
''')

    # ── gradle-wrapper.properties ──
    with open(f'{output_dir}/gradle/wrapper/gradle-wrapper.properties', 'w', encoding='utf-8') as f:
        f.write('''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
''')


def _call_mobile(name, args, line):
    """Dispatcher for mobile_* functions."""

    if name == 'mobile_create':
        if not args:
            raise EPLRuntimeError('mobile_create(app_name[, title]) requires app_name.', line)
        toga = _ensure_toga()
        app_name = str(args[0])
        title = str(args[1]) if len(args) > 1 else app_name
        app_id = f'mob_{_new_id()}'

        main_box = toga.Box(style=toga._Pack(direction=toga._COLUMN, margin=10))

        def startup(app):
            app.main_window = toga.MainWindow(title=title)
            app.main_window.content = main_box
            app.main_window.show()

        toga_app = toga.App(app_name, f'org.epl.{app_name}', startup=startup)
        _mobile_apps[app_id] = {
            'toga_app': toga_app,
            'main_box': main_box,
            'title': title,
            'screens': {},
            'current_screen': None,
        }
        return app_id

    if name == 'mobile_label':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_label(app_id, text[, font_size]) requires app_id and text.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        text = str(args[1])
        font_size = int(args[2]) if len(args) > 2 else 14
        label = toga.Label(text, style=toga._Pack(margin=5, font_size=font_size))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = label
        _mobile_widget_meta[wid] = {'type': 'label', 'text': text, 'font_size': font_size, 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(label)
        return wid

    if name == 'mobile_button':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_button(app_id, text[, handler]) requires app_id and text.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        text = str(args[1])
        handler = args[2] if len(args) > 2 else None

        def make_handler(h):
            def on_press(widget):
                if h:
                    try:
                        h()
                    except Exception as e:
                        print(f'[EPL Mobile] Button error: {e}', file=_sys.stderr)
            return on_press

        btn = toga.Button(text, on_press=make_handler(handler),
                          style=toga._Pack(margin=5))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = btn
        _mobile_widget_meta[wid] = {'type': 'button', 'text': text, 'app_id': app_id}
        _mobile_callbacks[wid] = handler
        _mobile_apps[app_id]['main_box'].add(btn)
        return wid

    if name == 'mobile_input':
        if not args:
            raise EPLRuntimeError('mobile_input(app_id[, placeholder]) requires app_id.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        placeholder = str(args[1]) if len(args) > 1 else ''
        inp = toga.TextInput(placeholder=placeholder, style=toga._Pack(margin=5, flex=1))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = inp
        _mobile_widget_meta[wid] = {'type': 'input', 'placeholder': placeholder, 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(inp)
        return wid

    if name == 'mobile_image':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_image(app_id, path) requires app_id and image path.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        path = str(args[1])
        img_view = toga.ImageView(toga.Image(path), style=toga._Pack(margin=5))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = img_view
        _mobile_widget_meta[wid] = {'type': 'image', 'path': path, 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(img_view)
        return wid

    if name == 'mobile_box':
        if not args:
            raise EPLRuntimeError('mobile_box(app_id[, direction]) requires app_id.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        direction = str(args[1]).upper() if len(args) > 1 else 'COLUMN'
        dir_val = toga._ROW if direction == 'ROW' else toga._COLUMN
        box = toga.Box(style=toga._Pack(direction=dir_val, margin=5))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = box
        _mobile_widget_meta[wid] = {'type': 'box', 'direction': direction, 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(box)
        return wid

    if name == 'mobile_scroll':
        if not args:
            raise EPLRuntimeError('mobile_scroll(app_id) requires app_id.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        content = toga.Box(style=toga._Pack(direction=toga._COLUMN))
        scroll = toga.ScrollContainer(content=content, style=toga._Pack(flex=1))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = scroll
        _mobile_widget_meta[wid] = {'type': 'scroll', 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(scroll)
        return wid

    if name == 'mobile_switch':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_switch(app_id, label[, handler]) requires app_id and label.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        label = str(args[1])
        handler = args[2] if len(args) > 2 else None

        def make_switch_handler(h):
            def on_change(widget):
                if h:
                    try:
                        h(widget.value)
                    except Exception as e:
                        print(f'[EPL Mobile] Switch handler error: {e}', file=_sys.stderr)
            return on_change

        switch = toga.Switch(label, on_change=make_switch_handler(handler),
                             style=toga._Pack(margin=5))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = switch
        _mobile_widget_meta[wid] = {'type': 'switch', 'label': label, 'app_id': app_id}
        _mobile_callbacks[wid] = handler
        _mobile_apps[app_id]['main_box'].add(switch)
        return wid

    if name == 'mobile_slider':
        if not args:
            raise EPLRuntimeError('mobile_slider(app_id[, min, max, handler]) requires app_id.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        min_val = float(args[1]) if len(args) > 1 else 0.0
        max_val = float(args[2]) if len(args) > 2 else 100.0
        handler = args[3] if len(args) > 3 else None

        def make_slider_handler(h):
            def on_change(widget):
                if h:
                    try:
                        h(widget.value)
                    except Exception as e:
                        print(f'[EPL Mobile] Slider handler error: {e}', file=_sys.stderr)
            return on_change

        slider = toga.Slider(min=min_val, max=max_val,
                             on_change=make_slider_handler(handler),
                             style=toga._Pack(margin=5, flex=1))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = slider
        _mobile_widget_meta[wid] = {'type': 'slider', 'min': min_val, 'max': max_val, 'app_id': app_id}
        _mobile_callbacks[wid] = handler
        _mobile_apps[app_id]['main_box'].add(slider)
        return wid

    if name == 'mobile_select':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_select(app_id, options[, handler]) requires app_id and options.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        options = args[1] if isinstance(args[1], list) else [str(args[1])]
        handler = args[2] if len(args) > 2 else None

        def make_select_handler(h):
            def on_change(widget):
                if h:
                    try:
                        h(widget.value)
                    except Exception as e:
                        print(f'[EPL Mobile] Select handler error: {e}', file=_sys.stderr)
            return on_change

        sel = toga.Selection(items=[str(o) for o in options],
                             on_change=make_select_handler(handler),
                             style=toga._Pack(margin=5))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = sel
        _mobile_widget_meta[wid] = {'type': 'select', 'options': [str(o) for o in options], 'app_id': app_id}
        _mobile_callbacks[wid] = handler
        _mobile_apps[app_id]['main_box'].add(sel)
        return wid

    if name == 'mobile_webview':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_webview(app_id, url) requires app_id and URL.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        url = str(args[1])
        webview = toga.WebView(url=url, style=toga._Pack(flex=1))
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = webview
        _mobile_widget_meta[wid] = {'type': 'webview', 'url': url, 'app_id': app_id}
        _mobile_apps[app_id]['main_box'].add(webview)
        return wid

    if name == 'mobile_run':
        if not args:
            raise EPLRuntimeError('mobile_run(app_id) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        _mobile_apps[app_id]['toga_app'].main_loop()
        return None

    if name == 'mobile_build':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_build(app_id, platform) requires app_id and platform ("ios" or "android").', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        platform = str(args[1]).lower()
        if platform not in ('ios', 'android', 'windows', 'macos', 'linux', 'web'):
            raise EPLRuntimeError(f'Unknown platform: {platform}. Use: ios, android, windows, macos, linux, web', line)
        # Ensure briefcase is installed (try importing)
        try:
            import importlib as _il
            _il.import_module('briefcase')
        except ImportError:
            if not _auto_install('briefcase', 'BeeWare Briefcase'):
                raise EPLRuntimeError(
                    'Failed to install BeeWare Briefcase. Install manually: pip install briefcase', line)
        import subprocess as _sp
        try:
            result = _sp.run(
                [_sys.executable, '-m', 'briefcase', 'build', platform],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise EPLRuntimeError(f'Build failed: {result.stderr[:500]}', line)
            return f'Build successful for {platform}'
        except FileNotFoundError:
            raise EPLRuntimeError(
                'Python executable not found for briefcase. Check your Python installation.', line)

    if name == 'mobile_style':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_style(widget_id, options) requires widget_id and options map.', line)
        widget_id = str(args[0])
        widget = _mobile_widgets.get(widget_id)
        if not widget:
            raise EPLRuntimeError(f'Unknown mobile widget: {widget_id}', line)
        from epl.interpreter import EPLDict
        options = _from_epl(args[1]) if isinstance(args[1], EPLDict) else {}
        _SAFE_MOBILE_STYLE = frozenset({
            'padding', 'margin', 'flex', 'width', 'height',
            'font_size', 'font_weight', 'color', 'background_color',
            'text_align', 'direction', 'alignment',
        })
        unsafe = set(options.keys()) - _SAFE_MOBILE_STYLE
        if unsafe:
            raise EPLRuntimeError(
                f'mobile_style: unsafe properties: {unsafe}. Allowed: {sorted(_SAFE_MOBILE_STYLE)}', line)
        try:
            for k, v in options.items():
                setattr(widget.style, k, v)
        except Exception as e:
            raise EPLRuntimeError(f'Mobile style error: {e}', line)
        return None

    if name == 'mobile_navigate':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_navigate(app_id, screen_name) requires app_id and screen name.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        screen_name = str(args[1])
        app_data = _mobile_apps[app_id]
        if screen_name not in app_data['screens']:
            raise EPLRuntimeError(f'Unknown screen: {screen_name}', line)
        app_data['toga_app'].main_window.content = app_data['screens'][screen_name]
        app_data['current_screen'] = screen_name
        return None

    if name == 'mobile_screen':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_screen(app_id, name) requires app_id and screen name.', line)
        toga = _ensure_toga()
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        screen_name = str(args[1])
        box = toga.Box(style=toga._Pack(direction=toga._COLUMN, margin=10))
        _mobile_apps[app_id]['screens'][screen_name] = box
        wid = f'mob_w_{_new_id()}'
        _mobile_widgets[wid] = box
        _mobile_widget_meta[wid] = {'type': 'screen', 'screen_name': screen_name, 'app_id': app_id}
        return wid

    if name == 'mobile_get_value':
        if not args:
            raise EPLRuntimeError('mobile_get_value(widget_id) requires widget_id.', line)
        wid = str(args[0])
        widget = _mobile_widgets.get(wid)
        if not widget:
            raise EPLRuntimeError(f'Unknown mobile widget: {wid}', line)
        _ensure_toga()
        import toga as _toga_mod
        if isinstance(widget, _toga_mod.TextInput):
            return widget.value or ''
        if isinstance(widget, _toga_mod.Switch):
            return widget.value
        if isinstance(widget, _toga_mod.Slider):
            return widget.value
        if isinstance(widget, _toga_mod.Selection):
            return widget.value
        if isinstance(widget, _toga_mod.Label):
            return widget.text
        return str(widget)

    if name == 'mobile_set_value':
        if len(args) < 2:
            raise EPLRuntimeError('mobile_set_value(widget_id, value) requires widget_id and value.', line)
        wid = str(args[0])
        widget = _mobile_widgets.get(wid)
        if not widget:
            raise EPLRuntimeError(f'Unknown mobile widget: {wid}', line)
        _ensure_toga()
        import toga as _toga_mod
        val = args[1]
        if isinstance(widget, _toga_mod.TextInput):
            widget.value = str(val)
        elif isinstance(widget, _toga_mod.Switch):
            widget.value = bool(val)
        elif isinstance(widget, _toga_mod.Slider):
            widget.value = float(val)
        elif isinstance(widget, _toga_mod.Label):
            widget.text = str(val)
        else:
            raise EPLRuntimeError(f'Cannot set value on widget type: {type(widget).__name__}', line)
        return None

    if name == 'mobile_destroy':
        if not args:
            raise EPLRuntimeError('mobile_destroy(app_id) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        # Clean up all widgets belonging to this app using metadata
        for wid in list(_mobile_widget_meta.keys()):
            if _mobile_widget_meta[wid].get('app_id') == app_id:
                _mobile_widgets.pop(wid, None)
                _mobile_callbacks.pop(wid, None)
                _mobile_widget_meta.pop(wid, None)
        del _mobile_apps[app_id]
        return None

    if name == 'mobile_alert':
        if len(args) < 3:
            raise EPLRuntimeError('mobile_alert(app_id, title, message) requires app_id, title, and message.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        title = str(args[1])
        message = str(args[2])
        try:
            dialog = _mobile_apps[app_id]['toga_app'].main_window.info_dialog(title, message)
            # Toga 0.5+ returns an awaitable; handle if coroutine
            import asyncio
            if asyncio.iscoroutine(dialog) or asyncio.isfuture(dialog):
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.ensure_future(dialog)
                except RuntimeError:
                    asyncio.run(dialog)
        except Exception as e:
            print(f'[EPL Mobile] Alert dialog error: {e}', file=_sys.stderr)
        return None

    if name == 'mobile_status_bar':
        if not args:
            raise EPLRuntimeError('mobile_status_bar(app_id[, style]) requires app_id.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        style = str(args[1]) if len(args) > 1 else 'default'
        _mobile_apps[app_id]['status_bar_style'] = style
        # Attempt to apply style if the Toga API supports it
        try:
            app = _mobile_apps[app_id].get('toga_app')
            if app and hasattr(app, 'main_window') and app.main_window:
                if hasattr(app.main_window, 'status_bar'):
                    app.main_window.status_bar = style
        except Exception:
            pass  # Status bar styling is best-effort
        return None

    # ── Android Studio Project Generator ──

    if name == 'android_project':
        if len(args) < 2:
            raise EPLRuntimeError(
                'android_project(app_id, output_dir[, package_name]) requires app_id and output_dir.', line)
        app_id = str(args[0])
        if app_id not in _mobile_apps:
            raise EPLRuntimeError(f'Unknown mobile app: {app_id}', line)
        output_dir = str(args[1])
        app_data = _mobile_apps[app_id]
        title = app_data.get('title', 'EPLApp')
        default_pkg = 'com.epl.' + _re.sub(r'[^a-z0-9]', '', title.lower())
        package_name = str(args[2]) if len(args) > 2 else default_pkg
        # Validate package name
        if not _re.match(r'^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$', package_name):
            raise EPLRuntimeError(
                f'Invalid package name: {package_name}. Use format: com.example.myapp', line)
        return _generate_android_project(app_id, output_dir, package_name, title, line)

    raise EPLRuntimeError(f'Unknown mobile function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Game Development (Pygame)
# ═══════════════════════════════════════════════════════════

_game_instances = {}    # game_id -> {...}
_game_sprites = {}      # sprite_id -> {...}
_game_sounds = {}       # sound_id -> pygame.mixer.Sound
_game_callbacks = {}    # game_id -> {'on_update': fn, 'on_key': {key: fn}, 'on_click': fn}


def _ensure_pygame():
    """Lazy-import pygame, auto-install if missing. Returns the pygame module."""
    if _pygame_cache[0] is not None:
        return _pygame_cache[0]
    try:
        import pygame               # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('pygame', 'Pygame'):
            raise EPLRuntimeError(
                'Failed to install Pygame. Install manually: pip install pygame', 0)
        try:
            import pygame           # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Installed pygame but import still failed. Check pip output.', 0)
    if not pygame.get_init():
        pygame.init()
    _pygame_cache[0] = pygame
    return pygame


def _call_game(name, args, line):
    """Dispatcher for game_* functions."""

    if name == 'game_create':
        if not args:
            raise EPLRuntimeError('game_create(title[, width, height]) requires title.', line)
        pygame = _ensure_pygame()
        title = str(args[0])
        width = int(args[1]) if len(args) > 1 else 800
        height = int(args[2]) if len(args) > 2 else 600
        if width < 1 or height < 1:
            raise EPLRuntimeError(f'game_create requires positive dimensions (got {width}x{height}).', line)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        gid = f'game_{_new_id()}'
        _game_instances[gid] = {
            'screen': screen, 'width': width, 'height': height,
            'clock': pygame.time.Clock(), 'fps': 60,
            'running': False, 'bg_color': (0, 0, 0),
            'sprites': [], 'score': 0, 'scene': 'default',
            'timers': {},
        }
        _game_callbacks[gid] = {'on_update': None, 'on_key': {}, 'on_click': None}
        return gid

    if name == 'game_sprite':
        if len(args) < 4:
            raise EPLRuntimeError('game_sprite(game_id, image_path, x, y) requires game_id, image, x, y.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        image_path = str(args[1])
        x, y = float(args[2]), float(args[3])
        if not _os.path.isfile(image_path):
            raise EPLRuntimeError(f'Image file not found: {image_path}', line)
        img = pygame.image.load(image_path).convert_alpha()
        sid = f'spr_{_new_id()}'
        _game_sprites[sid] = {
            'image': img, 'x': x, 'y': y,
            'rect': img.get_rect(topleft=(x, y)),
            'visible': True, 'game_id': gid,
        }
        _game_instances[gid]['sprites'].append(sid)
        return sid

    if name == 'game_text':
        if len(args) < 4:
            raise EPLRuntimeError('game_text(game_id, text, x, y[, size, color]) requires game_id, text, x, y.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        text = str(args[1])
        x, y = float(args[2]), float(args[3])
        size = int(args[4]) if len(args) > 4 else 24
        color = _parse_color(args[5]) if len(args) > 5 else (255, 255, 255)
        font = pygame.font.Font(None, size)
        surface = font.render(text, True, color)
        sid = f'txt_{_new_id()}'
        _game_sprites[sid] = {
            'image': surface, 'x': x, 'y': y,
            'rect': surface.get_rect(topleft=(x, y)),
            'visible': True, 'game_id': gid, 'is_text': True,
            'text': text, 'size': size, 'color': color,
        }
        _game_instances[gid]['sprites'].append(sid)
        return sid

    if name == 'game_rect':
        if len(args) < 5:
            raise EPLRuntimeError('game_rect(game_id, x, y, w, h[, color]) requires game_id, x, y, w, h.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        x, y = float(args[1]), float(args[2])
        w, h = float(args[3]), float(args[4])
        if w <= 0 or h <= 0:
            raise EPLRuntimeError(f'game_rect requires positive width and height (got {w}x{h}).', line)
        color = _parse_color(args[5]) if len(args) > 5 else (255, 255, 255)
        sid = f'rect_{_new_id()}'
        _game_sprites[sid] = {
            'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h,
            'color': color, 'visible': True, 'game_id': gid,
            'rect': pygame.Rect(x, y, w, h),
        }
        _game_instances[gid]['sprites'].append(sid)
        return sid

    if name == 'game_circle':
        if len(args) < 4:
            raise EPLRuntimeError('game_circle(game_id, x, y, radius[, color]) requires game_id, x, y, radius.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        x, y = float(args[1]), float(args[2])
        r = float(args[3])
        if r <= 0:
            raise EPLRuntimeError(f'game_circle requires positive radius (got {r}).', line)
        color = _parse_color(args[4]) if len(args) > 4 else (255, 255, 255)
        sid = f'circ_{_new_id()}'
        _game_sprites[sid] = {
            'type': 'circle', 'x': x, 'y': y, 'radius': r,
            'color': color, 'visible': True, 'game_id': gid,
            'rect': pygame.Rect(x - r, y - r, r * 2, r * 2),
        }
        _game_instances[gid]['sprites'].append(sid)
        return sid

    if name == 'game_line':
        if len(args) < 5:
            raise EPLRuntimeError('game_line(game_id, x1, y1, x2, y2[, color]) requires game_id, x1, y1, x2, y2.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        x1, y1 = float(args[1]), float(args[2])
        x2, y2 = float(args[3]), float(args[4])
        color = _parse_color(args[5]) if len(args) > 5 else (255, 255, 255)
        sid = f'line_{_new_id()}'
        _game_sprites[sid] = {
            'type': 'line', 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            'color': color, 'visible': True, 'game_id': gid,
        }
        _game_instances[gid]['sprites'].append(sid)
        return sid

    if name == 'game_image':
        if len(args) < 4:
            raise EPLRuntimeError('game_image(game_id, path, x, y) requires game_id, path, x, y.', line)
        return _call_game('game_sprite', args, line)

    if name == 'game_sound':
        if not args:
            raise EPLRuntimeError('game_sound(path) requires audio file path.', line)
        pygame = _ensure_pygame()
        path = str(args[0])
        if not _os.path.isfile(path):
            raise EPLRuntimeError(f'game_sound() error: Audio file not found: {path}', line)
        try:
            sound = pygame.mixer.Sound(path)
        except Exception as e:
            raise EPLRuntimeError(f'game_sound() error: {e}', line)
        sid = f'snd_{_new_id()}'
        _game_sounds[sid] = sound
        return sid

    if name == 'game_play_sound':
        if not args:
            raise EPLRuntimeError('game_play_sound(sound_id) requires sound_id.', line)
        sid = str(args[0])
        if sid not in _game_sounds:
            raise EPLRuntimeError(f'Unknown sound: {sid}', line)
        _game_sounds[sid].play()
        return None

    if name == 'game_music':
        if not args:
            raise EPLRuntimeError('game_music(path) requires music file path.', line)
        pygame = _ensure_pygame()
        path = str(args[0])
        if not _os.path.isfile(path):
            raise EPLRuntimeError(f'game_music() error: Music file not found: {path}', line)
        try:
            pygame.mixer.music.load(path)
        except Exception as e:
            raise EPLRuntimeError(f'game_music() error: {e}', line)
        return None

    if name == 'game_play_music':
        pygame = _ensure_pygame()
        loops = int(args[0]) if args else -1  # -1 = loop forever
        pygame.mixer.music.play(loops)
        return None

    if name == 'game_stop_music':
        pygame = _ensure_pygame()
        pygame.mixer.music.stop()
        return None

    if name == 'game_key_pressed':
        if not args:
            raise EPLRuntimeError('game_key_pressed(key_name) requires key name.', line)
        pygame = _ensure_pygame()
        key_name = str(args[0]).lower()
        key_map = {
            'up': pygame.K_UP, 'down': pygame.K_DOWN,
            'left': pygame.K_LEFT, 'right': pygame.K_RIGHT,
            'space': pygame.K_SPACE, 'enter': pygame.K_RETURN,
            'escape': pygame.K_ESCAPE, 'tab': pygame.K_TAB,
        }
        for c in 'abcdefghijklmnopqrstuvwxyz':
            key_map[c] = getattr(pygame, f'K_{c}')
        for n in '0123456789':
            key_map[n] = getattr(pygame, f'K_{n}')
        key_const = key_map.get(key_name)
        if key_const is None:
            raise EPLRuntimeError(f'Unknown key: {key_name}', line)
        keys = pygame.key.get_pressed()
        return keys[key_const]

    if name == 'game_mouse_pos':
        pygame = _ensure_pygame()
        pos = pygame.mouse.get_pos()
        return list(pos)

    if name == 'game_mouse_clicked':
        pygame = _ensure_pygame()
        return pygame.mouse.get_pressed()[0]

    if name == 'game_collide':
        if len(args) < 2:
            raise EPLRuntimeError('game_collide(sprite1, sprite2) requires two sprite IDs.', line)
        s1 = _game_sprites.get(str(args[0]))
        s2 = _game_sprites.get(str(args[1]))
        if not s1 or not s2:
            raise EPLRuntimeError('Invalid sprite ID for collision check.', line)
        # Lines don't have simple rect-based collision
        if s1.get('type') == 'line' or s2.get('type') == 'line':
            raise EPLRuntimeError('game_collide does not support line sprites. Use rect, circle, text, or image sprites.', line)
        return s1['rect'].colliderect(s2['rect'])

    if name == 'game_move':
        if len(args) < 3:
            raise EPLRuntimeError('game_move(sprite_id, dx, dy) requires sprite_id, dx, dy.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        dx, dy = float(args[1]), float(args[2])
        sprite = _game_sprites[sid]
        sprite['x'] += dx
        sprite['y'] += dy
        sprite['rect'].x = int(sprite['x'])
        sprite['rect'].y = int(sprite['y'])
        return None

    if name == 'game_set_pos':
        if len(args) < 3:
            raise EPLRuntimeError('game_set_pos(sprite_id, x, y) requires sprite_id, x, y.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        sprite = _game_sprites[sid]
        sprite['x'] = float(args[1])
        sprite['y'] = float(args[2])
        sprite['rect'].x = int(sprite['x'])
        sprite['rect'].y = int(sprite['y'])
        return None

    if name == 'game_get_pos':
        if not args:
            raise EPLRuntimeError('game_get_pos(sprite_id) requires sprite_id.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        s = _game_sprites[sid]
        return [s['x'], s['y']]

    if name == 'game_remove':
        if not args:
            raise EPLRuntimeError('game_remove(sprite_id) requires sprite_id.', line)
        sid = str(args[0])
        if sid in _game_sprites:
            gid = _game_sprites[sid].get('game_id')
            if gid and gid in _game_instances:
                sprites = _game_instances[gid]['sprites']
                if sid in sprites:
                    sprites.remove(sid)
            del _game_sprites[sid]
        return None

    if name == 'game_on_update':
        if len(args) < 2:
            raise EPLRuntimeError('game_on_update(game_id, handler) requires game_id and handler.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_callbacks[gid]['on_update'] = args[1]
        return None

    if name == 'game_on_key':
        if len(args) < 3:
            raise EPLRuntimeError('game_on_key(game_id, key, handler) requires game_id, key, handler.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        key = str(args[1]).lower()
        _game_callbacks[gid]['on_key'][key] = args[2]
        return None

    if name == 'game_on_click':
        if len(args) < 2:
            raise EPLRuntimeError('game_on_click(game_id, handler) requires game_id and handler.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_callbacks[gid]['on_click'] = args[1]
        return None

    if name == 'game_run':
        if not args:
            raise EPLRuntimeError('game_run(game_id) requires game_id.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        game = _game_instances[gid]
        cbs = _game_callbacks[gid]
        game['running'] = True
        import math as _math

        try:
            while game['running']:
                dt = game['clock'].tick(game['fps']) / 1000.0

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        game['running'] = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if cbs['on_click']:
                            try:
                                cbs['on_click'](event.pos[0], event.pos[1])
                            except Exception as e:
                                print(f'[EPL Game] on_click error: {e}', file=_sys.stderr)
                    elif event.type == pygame.KEYDOWN:
                        key_name = pygame.key.name(event.key)
                        if key_name in cbs['on_key']:
                            try:
                                cbs['on_key'][key_name]()
                            except Exception as e:
                                print(f'[EPL Game] on_key error: {e}', file=_sys.stderr)

                if cbs['on_update']:
                    try:
                        cbs['on_update'](dt)
                    except Exception as e:
                        print(f'[EPL Game] on_update error: {e}', file=_sys.stderr)

                # Timers
                now = pygame.time.get_ticks()
                for tid, timer in list(game['timers'].items()):
                    if now >= timer['next_fire']:
                        try:
                            timer['handler']()
                        except Exception as e:
                            print(f'[EPL Game] timer error: {e}', file=_sys.stderr)
                        if timer['repeat']:
                            timer['next_fire'] = now + timer['interval_ms']
                        else:
                            del game['timers'][tid]

                # Process animations
                for sid in game['sprites']:
                    sprite = _game_sprites.get(sid)
                    if not sprite:
                        continue
                    target = sprite.get('anim_target')
                    if target:
                        speed = sprite.get('anim_speed', 100.0)
                        tx, ty = target
                        dx = tx - sprite['x']
                        dy = ty - sprite['y']
                        dist = _math.sqrt(dx * dx + dy * dy)
                        if dist < speed * dt:
                            sprite['x'] = tx
                            sprite['y'] = ty
                            sprite.pop('anim_target', None)
                            sprite.pop('anim_speed', None)
                        else:
                            ratio = (speed * dt) / dist
                            sprite['x'] += dx * ratio
                            sprite['y'] += dy * ratio
                        sprite['rect'].x = int(sprite['x'])
                        sprite['rect'].y = int(sprite['y'])

                # Camera offset
                cam_x, cam_y = game.get('camera', (0, 0))

                # Draw
                game['screen'].fill(game['bg_color'])
                current_scene = game.get('scene', 'default')
                for sid in game['sprites']:
                    sprite = _game_sprites.get(sid)
                    if not sprite or not sprite.get('visible'):
                        continue
                    # Scene filtering — only draw sprites in current scene or global
                    sprite_scene = sprite.get('scene', 'default')
                    if sprite_scene != 'default' and sprite_scene != current_scene:
                        continue
                    stype = sprite.get('type')
                    ox = int(sprite.get('x', 0) - cam_x)
                    oy = int(sprite.get('y', 0) - cam_y)
                    if stype == 'rect':
                        pygame.draw.rect(game['screen'], sprite['color'],
                                         pygame.Rect(ox, oy,
                                                     int(sprite['w']), int(sprite['h'])))
                    elif stype == 'circle':
                        pygame.draw.circle(game['screen'], sprite['color'],
                                           (ox, oy), int(sprite['radius']))
                    elif stype == 'line':
                        pygame.draw.line(game['screen'], sprite['color'],
                                         (int(sprite.get('x1', 0) - cam_x),
                                          int(sprite.get('y1', 0) - cam_y)),
                                         (int(sprite.get('x2', 0) - cam_x),
                                          int(sprite.get('y2', 0) - cam_y)))
                    else:
                        game['screen'].blit(sprite['image'], (ox, oy))

                pygame.display.flip()
        finally:
            # Guarantee resource cleanup even on exception
            try:
                pygame.mixer.stop()
            except Exception:
                pass
            try:
                pygame.display.quit()
                pygame.display.init()
            except Exception:
                pass
        return None

    if name == 'game_fps':
        if len(args) < 2:
            raise EPLRuntimeError('game_fps(game_id, fps) requires game_id and fps value.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_instances[gid]['fps'] = int(args[1])
        return None

    if name == 'game_set_score':
        if len(args) < 2:
            raise EPLRuntimeError('game_set_score(game_id, score) requires game_id and score.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_instances[gid]['score'] = int(args[1])
        return None

    if name == 'game_get_score':
        if not args:
            raise EPLRuntimeError('game_get_score(game_id) requires game_id.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        return _game_instances[gid]['score']

    if name == 'game_scene':
        if len(args) < 2:
            raise EPLRuntimeError('game_scene(game_id, scene_name) requires game_id and scene name.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_instances[gid]['scene'] = str(args[1])
        return None

    if name == 'game_timer':
        if len(args) < 3:
            raise EPLRuntimeError('game_timer(game_id, seconds, handler[, repeat]) requires game_id, seconds, handler.', line)
        pygame = _ensure_pygame()
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        seconds = float(args[1])
        handler = args[2]
        repeat = bool(args[3]) if len(args) > 3 else False
        tid = f'tmr_{_new_id()}'
        _game_instances[gid]['timers'][tid] = {
            'interval_ms': int(seconds * 1000),
            'next_fire': pygame.time.get_ticks() + int(seconds * 1000),
            'handler': handler, 'repeat': repeat,
        }
        return tid

    if name == 'game_animate':
        if len(args) < 4:
            raise EPLRuntimeError('game_animate(sprite_id, target_x, target_y, speed) requires sprite_id, target_x, target_y, speed.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        _game_sprites[sid]['anim_target'] = (float(args[1]), float(args[2]))
        _game_sprites[sid]['anim_speed'] = float(args[3])
        return None

    if name == 'game_camera':
        if len(args) < 3:
            raise EPLRuntimeError('game_camera(game_id, x, y) requires game_id, x, y.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_instances[gid]['camera'] = (float(args[1]), float(args[2]))
        return None

    if name == 'game_set_bg':
        if len(args) < 2:
            raise EPLRuntimeError('game_set_bg(game_id, color) requires game_id and color.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        _game_instances[gid]['bg_color'] = _parse_color(args[1])
        return None

    if name == 'game_get_size':
        if not args:
            raise EPLRuntimeError('game_get_size(game_id) requires game_id.', line)
        gid = str(args[0])
        if gid not in _game_instances:
            raise EPLRuntimeError(f'Unknown game: {gid}', line)
        g = _game_instances[gid]
        return [g['width'], g['height']]

    if name == 'game_quit':
        if not args:
            raise EPLRuntimeError('game_quit(game_id) requires game_id.', line)
        gid = str(args[0])
        if gid in _game_instances:
            _game_instances[gid]['running'] = False
        return None

    if name == 'game_show':
        if not args:
            raise EPLRuntimeError('game_show(sprite_id) requires sprite_id.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        _game_sprites[sid]['visible'] = True
        return None

    if name == 'game_hide':
        if not args:
            raise EPLRuntimeError('game_hide(sprite_id) requires sprite_id.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        _game_sprites[sid]['visible'] = False
        return None

    if name == 'game_update_text':
        if len(args) < 2:
            raise EPLRuntimeError('game_update_text(sprite_id, new_text) requires sprite_id and text.', line)
        pygame = _ensure_pygame()
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        sprite = _game_sprites[sid]
        if not sprite.get('is_text'):
            raise EPLRuntimeError(f'Sprite {sid} is not a text sprite.', line)
        new_text = str(args[1])
        sprite['text'] = new_text
        font = pygame.font.Font(None, sprite.get('size', 24))
        sprite['image'] = font.render(new_text, True, sprite.get('color', (255, 255, 255)))
        sprite['rect'] = sprite['image'].get_rect(topleft=(int(sprite['x']), int(sprite['y'])))
        return None

    if name == 'game_set_sprite_scene':
        if len(args) < 2:
            raise EPLRuntimeError('game_set_sprite_scene(sprite_id, scene_name) requires sprite_id and scene.', line)
        sid = str(args[0])
        if sid not in _game_sprites:
            raise EPLRuntimeError(f'Unknown sprite: {sid}', line)
        _game_sprites[sid]['scene'] = str(args[1])
        return None

    if name == 'game_destroy':
        if not args:
            raise EPLRuntimeError('game_destroy(game_id) requires game_id.', line)
        gid = str(args[0])
        if gid in _game_instances:
            game = _game_instances[gid]
            # Stop audio and clear timers
            try:
                pygame = _ensure_pygame()
                pygame.mixer.stop()
            except Exception:
                pass
            game.get('timers', {}).clear()
            # Clean up sprites belonging to this game
            for sid in list(game.get('sprites', [])):
                _game_sprites.pop(sid, None)
            del _game_instances[gid]
            _game_callbacks.pop(gid, None)
        return None

    raise EPLRuntimeError(f'Unknown game function: {name}', line)


def _parse_color(val):
    """Convert EPL color value to RGB tuple."""
    if isinstance(val, (list, tuple)) and len(val) >= 3:
        return (int(val[0]), int(val[1]), int(val[2]))
    s = str(val).lower().strip()
    color_map = {
        'white': (255, 255, 255), 'black': (0, 0, 0),
        'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255),
        'yellow': (255, 255, 0), 'cyan': (0, 255, 255), 'magenta': (255, 0, 255),
        'orange': (255, 165, 0), 'purple': (128, 0, 128),
        'gray': (128, 128, 128), 'grey': (128, 128, 128),
        'pink': (255, 192, 203), 'brown': (139, 69, 19),
    }
    if s in color_map:
        return color_map[s]
    if s.startswith('#') and len(s) == 7:
        try:
            return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
        except ValueError:
            return (255, 255, 255)
    return (255, 255, 255)


# ═══════════════════════════════════════════════════════════
#  ML / AI (scikit-learn wrappers)
# ═══════════════════════════════════════════════════════════

_ml_models = {}     # model_id -> sklearn model
_ml_data = {}       # data_id -> dict of arrays
_ml_model_data = {} # model_id -> data_id (set during ml_train)


def _ensure_sklearn():
    """Lazy-import scikit-learn, auto-install if missing."""
    if _sklearn_cache[0] is not None:
        return _sklearn_cache[0]
    try:
        import sklearn              # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('scikit-learn', 'scikit-learn'):
            raise EPLRuntimeError(
                'Failed to install scikit-learn. Install manually: pip install scikit-learn', 0)
        try:
            import sklearn          # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Installed scikit-learn but import still failed. Check pip output.', 0)
    _sklearn_cache[0] = sklearn
    return sklearn


def _ensure_joblib():
    """Lazy-import joblib, auto-install if missing."""
    if _joblib_cache[0] is not None:
        return _joblib_cache[0]
    try:
        import joblib               # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('joblib', 'Joblib'):
            raise EPLRuntimeError(
                'Failed to install joblib. Install manually: pip install joblib', 0)
        try:
            import joblib           # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Installed joblib but import still failed. Check pip output.', 0)
    _joblib_cache[0] = joblib
    return joblib


def _call_ml(name, args, line):
    """Dispatcher for ml_* functions."""

    if name == 'ml_load_data':
        if not args:
            raise EPLRuntimeError('ml_load_data(source) requires a data source (path or name).', line)
        _ensure_sklearn()
        source = str(args[0])
        from sklearn import datasets
        builtin = {
            'iris': datasets.load_iris, 'wine': datasets.load_wine,
            'digits': datasets.load_digits, 'breast_cancer': datasets.load_breast_cancer,
            'diabetes': datasets.load_diabetes,
        }
        if source.lower() in builtin:
            data = builtin[source.lower()]()
            did = f'data_{_new_id()}'
            _ml_data[did] = {'X': data.data.tolist(), 'y': data.target.tolist(),
                             'feature_names': list(data.feature_names) if hasattr(data, 'feature_names') else []}
            return did
        if source.endswith('.csv'):
            norm = _os.path.normpath(source)
            if '..' in norm.split(_os.sep):
                raise EPLRuntimeError(f'Path traversal not allowed: {source}', line)
            if not _os.path.isfile(norm):
                raise EPLRuntimeError(f'CSV file not found: {source}', line)
            import pandas as pd     # type: ignore[import-not-found]
            df = pd.read_csv(norm)
            did = f'data_{_new_id()}'
            _ml_data[did] = {'X': df.iloc[:, :-1].values.tolist(),
                             'y': df.iloc[:, -1].values.tolist(),
                             'feature_names': list(df.columns[:-1])}
            return did
        raise EPLRuntimeError(f'Unknown data source: {source}. Use a built-in name or .csv path.', line)

    if name == 'ml_split':
        if not args:
            raise EPLRuntimeError('ml_split(data_id[, test_ratio]) requires data_id.', line)
        _ensure_sklearn()
        from sklearn.model_selection import train_test_split
        did = str(args[0])
        if did not in _ml_data:
            raise EPLRuntimeError(f'Unknown data: {did}', line)
        ratio = float(args[1]) if len(args) > 1 else 0.2
        data = _ml_data[did]
        X_train, X_test, y_train, y_test = train_test_split(
            data['X'], data['y'], test_size=ratio, random_state=42)
        split_id = f'split_{_new_id()}'
        _ml_data[split_id] = {
            'X_train': X_train, 'X_test': X_test,
            'y_train': y_train, 'y_test': y_test,
        }
        return split_id

    _model_factories = {
        'ml_linear_regression': lambda: __import__('sklearn.linear_model', fromlist=['LinearRegression']).LinearRegression(),
        'ml_logistic_regression': lambda: __import__('sklearn.linear_model', fromlist=['LogisticRegression']).LogisticRegression(max_iter=1000),
        'ml_decision_tree': lambda: __import__('sklearn.tree', fromlist=['DecisionTreeClassifier']).DecisionTreeClassifier(),
        'ml_random_forest': lambda: __import__('sklearn.ensemble', fromlist=['RandomForestClassifier']).RandomForestClassifier(),
        'ml_svm': lambda: __import__('sklearn.svm', fromlist=['SVC']).SVC(),
    }
    if name in _model_factories:
        _ensure_sklearn()
        model = _model_factories[name]()
        mid = f'model_{_new_id()}'
        _ml_models[mid] = model
        return mid

    if name == 'ml_knn':
        _ensure_sklearn()
        from sklearn.neighbors import KNeighborsClassifier
        k = int(args[0]) if args else 5
        model = KNeighborsClassifier(n_neighbors=k)
        mid = f'model_{_new_id()}'
        _ml_models[mid] = model
        return mid

    if name == 'ml_kmeans':
        _ensure_sklearn()
        from sklearn.cluster import KMeans
        k = int(args[0]) if args else 3
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        mid = f'model_{_new_id()}'
        _ml_models[mid] = model
        return mid

    if name == 'ml_neural_network':
        _ensure_sklearn()
        from sklearn.neural_network import MLPClassifier
        layers = args[0] if args and isinstance(args[0], list) else [100]
        model = MLPClassifier(hidden_layer_sizes=tuple(int(x) for x in layers),
                              max_iter=500, random_state=42)
        mid = f'model_{_new_id()}'
        _ml_models[mid] = model
        return mid

    if name == 'ml_train':
        if len(args) < 2:
            raise EPLRuntimeError('ml_train(model_id, data_or_split_id) requires model_id and data.', line)
        mid = str(args[0])
        if mid not in _ml_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        did = str(args[1])
        if did not in _ml_data:
            raise EPLRuntimeError(f'Unknown data: {did}', line)
        data = _ml_data[did]
        model = _ml_models[mid]
        if 'X_train' in data:
            model.fit(data['X_train'], data['y_train'])
        else:
            model.fit(data['X'], data['y'])
        _ml_model_data[mid] = did
        return mid

    if name == 'ml_predict':
        if len(args) < 2:
            raise EPLRuntimeError('ml_predict(model_id, input) requires model_id and input data.', line)
        mid = str(args[0])
        if mid not in _ml_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        model = _ml_models[mid]
        inp = args[1]
        if isinstance(inp, list) and inp and not isinstance(inp[0], list):
            inp = [inp]
        # Apply scaler if model was trained on normalized data
        train_did = _ml_model_data.get(mid)
        if train_did and train_did in _ml_data:
            scaler = _ml_data[train_did].get('_scaler')
            if scaler is not None:
                try:
                    inp = scaler.transform(inp).tolist()
                except Exception:
                    pass  # If transform fails, use raw input
        try:
            result = model.predict(inp)
        except Exception as e:
            # Check for NotFittedError by class name (works across sklearn versions)
            if type(e).__name__ == 'NotFittedError' or 'not fitted' in str(e).lower():
                raise EPLRuntimeError(f'Model {mid} has not been trained yet. Call ml_train() first.', line)
            raise EPLRuntimeError(f'ml_predict error: {e}', line)
        return result.tolist() if hasattr(result, 'tolist') else list(result)

    if name == 'ml_accuracy':
        if len(args) < 2:
            raise EPLRuntimeError('ml_accuracy(model_id, data_or_split_id) requires model_id and data.', line)
        _ensure_sklearn()
        mid = str(args[0])
        did = str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        model = _ml_models[mid]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        try:
            preds = model.predict(X)
        except Exception as e:
            if 'not fitted' in str(e).lower():
                raise EPLRuntimeError(f'Model {mid} has not been trained yet.', line)
            raise EPLRuntimeError(f'ml_accuracy error: {e}', line)
        # Detect regression vs classification
        from sklearn.base import is_classifier
        if is_classifier(model):
            from sklearn.metrics import accuracy_score
            return float(accuracy_score(y, preds))
        else:
            # For regression models, return R² score instead
            from sklearn.metrics import r2_score
            return float(r2_score(y, preds))

    if name == 'ml_mse':
        if len(args) < 2:
            raise EPLRuntimeError('ml_mse(model_id, data_id) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.metrics import mean_squared_error
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        preds = _ml_models[mid].predict(X)
        return float(mean_squared_error(y, preds))

    if name == 'ml_mae':
        if len(args) < 2:
            raise EPLRuntimeError('ml_mae(model_id, data_id) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.metrics import mean_absolute_error
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        preds = _ml_models[mid].predict(X)
        return float(mean_absolute_error(y, preds))

    if name == 'ml_r2':
        if len(args) < 2:
            raise EPLRuntimeError('ml_r2(model_id, data_id) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.metrics import r2_score
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        preds = _ml_models[mid].predict(X)
        return float(r2_score(y, preds))

    if name == 'ml_save_model':
        if len(args) < 2:
            raise EPLRuntimeError('ml_save_model(model_id, path) requires model_id and file path.', line)
        joblib = _ensure_joblib()
        mid = str(args[0])
        if mid not in _ml_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        path = _os.path.normpath(str(args[1]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[1]}', line)
        joblib.dump(_ml_models[mid], path)
        return path

    if name == 'ml_load_model':
        if not args:
            raise EPLRuntimeError('ml_load_model(path) requires file path.', line)
        joblib = _ensure_joblib()
        path = _os.path.normpath(str(args[0]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[0]}', line)
        if not _os.path.isfile(path):
            raise EPLRuntimeError(f'Model file not found: {path}', line)
        import sys
        print(f'Warning: ml_load_model loads serialized objects which can execute arbitrary code. '
              f'Only load models you trust.', file=sys.stderr)
        model = joblib.load(path)
        mid = f'model_{_new_id()}'
        _ml_models[mid] = model
        return mid

    if name == 'ml_normalize':
        if not args:
            raise EPLRuntimeError('ml_normalize(data_id) requires data_id.', line)
        _ensure_sklearn()
        from sklearn.preprocessing import StandardScaler
        did = str(args[0])
        if did not in _ml_data:
            raise EPLRuntimeError(f'Unknown data: {did}', line)
        data = _ml_data[did]
        scaler = StandardScaler()
        import copy
        new_data = copy.deepcopy({k: v for k, v in data.items() if k != '_scaler'})
        if 'X_train' in new_data:
            new_data['X_train'] = scaler.fit_transform(new_data['X_train']).tolist()
            new_data['X_test'] = scaler.transform(new_data['X_test']).tolist()
        else:
            new_data['X'] = scaler.fit_transform(new_data['X']).tolist()
        new_data['_scaler'] = scaler
        new_did = f'data_{_new_id()}'
        _ml_data[new_did] = new_data
        return new_did

    if name == 'ml_confusion_matrix':
        if len(args) < 2:
            raise EPLRuntimeError('ml_confusion_matrix(model_id, data_id) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.metrics import confusion_matrix
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        preds = _ml_models[mid].predict(X)
        return confusion_matrix(y, preds).tolist()

    if name == 'ml_cross_validate':
        if len(args) < 2:
            raise EPLRuntimeError('ml_cross_validate(model_id, data_id[, folds]) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.model_selection import cross_val_score
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        folds = int(args[2]) if len(args) > 2 else 5
        data = _ml_data[did]
        # Cross-validate on full data if available, otherwise training split
        X = data.get('X', data.get('X_train'))
        y = data.get('y', data.get('y_train'))
        return cross_val_score(_ml_models[mid], X, y, cv=folds).tolist()

    if name == 'ml_classification_report':
        if len(args) < 2:
            raise EPLRuntimeError('ml_classification_report(model_id, data_id) requires model_id and data_id.', line)
        _ensure_sklearn()
        from sklearn.metrics import classification_report
        mid, did = str(args[0]), str(args[1])
        if mid not in _ml_models or did not in _ml_data:
            raise EPLRuntimeError('Invalid model or data ID.', line)
        data = _ml_data[did]
        X = data.get('X_test', data.get('X'))
        y = data.get('y_test', data.get('y'))
        return classification_report(y, _ml_models[mid].predict(X))

    if name == 'ml_feature_importance':
        if not args:
            raise EPLRuntimeError('ml_feature_importance(model_id) requires model_id.', line)
        mid = str(args[0])
        if mid not in _ml_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        model = _ml_models[mid]
        if hasattr(model, 'feature_importances_'):
            return model.feature_importances_.tolist()
        elif hasattr(model, 'coef_'):
            import numpy as np      # type: ignore[import-not-found]
            return np.abs(model.coef_).mean(axis=0).tolist() if model.coef_.ndim > 1 else model.coef_.tolist()
        raise EPLRuntimeError('Model does not support feature importance.', line)

    if name == 'ml_delete_model':
        if not args:
            raise EPLRuntimeError('ml_delete_model(model_id) requires model_id.', line)
        mid = str(args[0])
        if mid in _ml_models:
            del _ml_models[mid]
            return True
        return False

    if name == 'ml_delete_data':
        if not args:
            raise EPLRuntimeError('ml_delete_data(data_id) requires data_id.', line)
        did = str(args[0])
        if did in _ml_data:
            del _ml_data[did]
            return True
        return False

    raise EPLRuntimeError(f'Unknown ML function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Deep Learning (PyTorch / TensorFlow)
# ═══════════════════════════════════════════════════════════

_dl_models = {}       # model_id -> {'framework': 'pytorch'|'tensorflow', 'model': <model>, ...}
_dl_data = {}         # data_id -> tensors/arrays

_torch_cache = [None]
_tf_cache = [None]


def _ensure_torch():
    """Lazy-import PyTorch."""
    if _torch_cache[0] is not None:
        return _torch_cache[0]
    try:
        import torch                # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('torch', 'PyTorch'):
            raise EPLRuntimeError(
                'PyTorch not available. Install: pip install torch', 0)
        try:
            import torch            # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Install PyTorch manually: pip install torch', 0)
    _torch_cache[0] = torch
    return torch


def _ensure_tensorflow():
    """Lazy-import TensorFlow."""
    if _tf_cache[0] is not None:
        return _tf_cache[0]
    try:
        import tensorflow as tf     # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('tensorflow', 'TensorFlow'):
            raise EPLRuntimeError(
                'TensorFlow not available. Install: pip install tensorflow', 0)
        try:
            import tensorflow as tf # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Install TensorFlow manually: pip install tensorflow', 0)
    _tf_cache[0] = tf
    return tf


def _call_dl(name, args, line):
    """Dispatcher for dl_* (deep learning) functions."""

    if name == 'dl_tensor':
        if not args:
            raise EPLRuntimeError('dl_tensor(data[, framework]) requires data.', line)
        data = _from_epl(args[0])
        framework = str(args[1]).lower() if len(args) > 1 else 'pytorch'
        tid = f'tensor_{_new_id()}'
        if framework in ('pytorch', 'torch'):
            torch = _ensure_torch()
            _dl_data[tid] = {'framework': 'pytorch', 'tensor': torch.tensor(data, dtype=torch.float32)}
        elif framework in ('tensorflow', 'tf'):
            tf = _ensure_tensorflow()
            _dl_data[tid] = {'framework': 'tensorflow', 'tensor': tf.constant(data, dtype=tf.float32)}
        else:
            raise EPLRuntimeError(f'Unknown framework: {framework}. Use pytorch or tensorflow.', line)
        return tid

    if name == 'dl_sequential':
        if not args:
            raise EPLRuntimeError('dl_sequential(layers[, framework]) requires layers list.', line)
        layers_spec = _from_epl(args[0])
        framework = str(args[1]).lower() if len(args) > 1 else 'pytorch'
        mid = f'dl_{_new_id()}'

        if framework in ('pytorch', 'torch'):
            torch = _ensure_torch()
            import torch.nn as nn   # type: ignore[import-not-found]
            layers = []
            for spec in layers_spec:
                if isinstance(spec, dict):
                    ltype = spec.get('type', 'linear').lower()
                    if ltype == 'linear':
                        layers.append(nn.Linear(int(spec['in']), int(spec['out'])))
                    elif ltype == 'relu':
                        layers.append(nn.ReLU())
                    elif ltype == 'sigmoid':
                        layers.append(nn.Sigmoid())
                    elif ltype == 'tanh':
                        layers.append(nn.Tanh())
                    elif ltype == 'dropout':
                        layers.append(nn.Dropout(float(spec.get('rate', 0.5))))
                    elif ltype == 'batchnorm':
                        layers.append(nn.BatchNorm1d(int(spec['features'])))
                    elif ltype == 'softmax':
                        layers.append(nn.Softmax(dim=int(spec.get('dim', 1))))
                    elif ltype == 'conv2d':
                        layers.append(nn.Conv2d(int(spec['in']), int(spec['out']),
                                                 kernel_size=int(spec.get('kernel', 3)),
                                                 padding=int(spec.get('padding', 1))))
                    elif ltype == 'maxpool2d':
                        layers.append(nn.MaxPool2d(int(spec.get('kernel', 2))))
                    elif ltype == 'flatten':
                        layers.append(nn.Flatten())
                    elif ltype == 'lstm':
                        layers.append(nn.LSTM(int(spec['in']), int(spec['out']),
                                               batch_first=True))
            model = nn.Sequential(*layers)
            _dl_models[mid] = {
                'framework': 'pytorch', 'model': model,
                'optimizer': None, 'loss_fn': None,
            }

        elif framework in ('tensorflow', 'tf'):
            tf = _ensure_tensorflow()
            model = tf.keras.Sequential()
            for spec in layers_spec:
                if isinstance(spec, dict):
                    ltype = spec.get('type', 'dense').lower()
                    if ltype in ('dense', 'linear'):
                        act = spec.get('activation', None)
                        model.add(tf.keras.layers.Dense(int(spec['out']), activation=act,
                                                          input_shape=(int(spec['in']),) if 'in' in spec else None))
                    elif ltype == 'dropout':
                        model.add(tf.keras.layers.Dropout(float(spec.get('rate', 0.5))))
                    elif ltype == 'batchnorm':
                        model.add(tf.keras.layers.BatchNormalization())
                    elif ltype == 'conv2d':
                        model.add(tf.keras.layers.Conv2D(int(spec['out']),
                                                           int(spec.get('kernel', 3)),
                                                           activation=spec.get('activation'),
                                                           padding=spec.get('padding', 'same')))
                    elif ltype == 'maxpool2d':
                        model.add(tf.keras.layers.MaxPooling2D(int(spec.get('kernel', 2))))
                    elif ltype == 'flatten':
                        model.add(tf.keras.layers.Flatten())
                    elif ltype == 'lstm':
                        model.add(tf.keras.layers.LSTM(int(spec['out']),
                                                         return_sequences=spec.get('return_sequences', False)))
            _dl_models[mid] = {
                'framework': 'tensorflow', 'model': model,
            }
        else:
            raise EPLRuntimeError(f'Unknown framework: {framework}', line)
        return mid

    if name == 'dl_compile':
        if len(args) < 2:
            raise EPLRuntimeError('dl_compile(model_id, options) requires model_id and options.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        opts = _from_epl(args[1]) if not isinstance(args[1], dict) else args[1]
        info = _dl_models[mid]

        if info['framework'] == 'pytorch':
            torch = _ensure_torch()
            lr = float(opts.get('lr', opts.get('learning_rate', 0.001)))
            opt_name = opts.get('optimizer', 'adam').lower()
            loss_name = opts.get('loss', 'cross_entropy').lower()
            model = info['model']
            if opt_name == 'adam':
                info['optimizer'] = torch.optim.Adam(model.parameters(), lr=lr)
            elif opt_name == 'sgd':
                info['optimizer'] = torch.optim.SGD(model.parameters(), lr=lr,
                                                      momentum=float(opts.get('momentum', 0.9)))
            elif opt_name == 'rmsprop':
                info['optimizer'] = torch.optim.RMSprop(model.parameters(), lr=lr)
            loss_map = {
                'cross_entropy': torch.nn.CrossEntropyLoss(),
                'mse': torch.nn.MSELoss(),
                'bce': torch.nn.BCELoss(),
                'bce_logits': torch.nn.BCEWithLogitsLoss(),
                'l1': torch.nn.L1Loss(),
                'nll': torch.nn.NLLLoss(),
            }
            info['loss_fn'] = loss_map.get(loss_name, torch.nn.CrossEntropyLoss())

        elif info['framework'] == 'tensorflow':
            model = info['model']
            lr = float(opts.get('lr', opts.get('learning_rate', 0.001)))
            opt_name = opts.get('optimizer', 'adam').lower()
            loss_name = opts.get('loss', 'sparse_categorical_crossentropy')
            metrics = opts.get('metrics', ['accuracy'])
            model.compile(optimizer=opt_name, loss=loss_name, metrics=metrics)

        return mid

    if name == 'dl_train':
        if len(args) < 3:
            raise EPLRuntimeError('dl_train(model_id, X, y[, epochs, batch_size]) requires model_id, X, y.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        info = _dl_models[mid]
        X_raw = _from_epl(args[1])
        y_raw = _from_epl(args[2])
        epochs = int(args[3]) if len(args) > 3 else 10
        batch_size = int(args[4]) if len(args) > 4 else 32

        if info['framework'] == 'pytorch':
            torch = _ensure_torch()
            model = info['model']
            optimizer = info['optimizer']
            loss_fn = info['loss_fn']
            if not optimizer or not loss_fn:
                raise EPLRuntimeError('Model not compiled. Call dl_compile() first.', line)
            X_tensor = torch.tensor(X_raw, dtype=torch.float32)
            y_tensor = torch.tensor(y_raw, dtype=torch.long)
            dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
            loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
            model.train()
            history = []
            for epoch in range(epochs):
                total_loss = 0
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    output = model(batch_X)
                    loss = loss_fn(output, batch_y)
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                avg_loss = total_loss / len(loader)
                history.append(avg_loss)
            info['history'] = history
            return {'epochs': epochs, 'final_loss': history[-1] if history else 0}

        elif info['framework'] == 'tensorflow':
            tf = _ensure_tensorflow()
            import numpy as np      # type: ignore[import-not-found]
            model = info['model']
            X_arr = np.array(X_raw, dtype=np.float32)
            y_arr = np.array(y_raw)
            hist = model.fit(X_arr, y_arr, epochs=epochs, batch_size=batch_size, verbose=0)
            info['history'] = hist.history
            return {
                'epochs': epochs,
                'final_loss': float(hist.history['loss'][-1]),
                'final_accuracy': float(hist.history.get('accuracy', [0])[-1]),
            }

    if name == 'dl_predict':
        if len(args) < 2:
            raise EPLRuntimeError('dl_predict(model_id, input) requires model_id and input.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        info = _dl_models[mid]
        inp = _from_epl(args[1])

        if info['framework'] == 'pytorch':
            torch = _ensure_torch()
            model = info['model']
            model.eval()
            with torch.no_grad():
                X = torch.tensor(inp, dtype=torch.float32)
                if X.dim() == 1:
                    X = X.unsqueeze(0)
                output = model(X)
                return output.tolist()

        elif info['framework'] == 'tensorflow':
            import numpy as np      # type: ignore[import-not-found]
            model = info['model']
            X = np.array(inp, dtype=np.float32)
            if X.ndim == 1:
                X = X.reshape(1, -1)
            return model.predict(X, verbose=0).tolist()

    if name == 'dl_save':
        if len(args) < 2:
            raise EPLRuntimeError('dl_save(model_id, path) requires model_id and path.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        path = _os.path.normpath(str(args[1]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[1]}', line)
        info = _dl_models[mid]
        if info['framework'] == 'pytorch':
            torch = _ensure_torch()
            torch.save(info['model'].state_dict(), path)
        elif info['framework'] == 'tensorflow':
            info['model'].save(path)
        return path

    if name == 'dl_load':
        if len(args) < 2:
            raise EPLRuntimeError('dl_load(model_id, path) requires model_id and path.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        path = _os.path.normpath(str(args[1]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[1]}', line)
        if not _os.path.exists(path):
            raise EPLRuntimeError(f'Model file not found: {path}', line)
        info = _dl_models[mid]
        import sys
        print(f'Warning: dl_load loads serialized models which can execute arbitrary code. '
              f'Only load models you trust.', file=sys.stderr)
        if info['framework'] == 'pytorch':
            torch = _ensure_torch()
            info['model'].load_state_dict(torch.load(path, weights_only=True))
        elif info['framework'] == 'tensorflow':
            tf = _ensure_tensorflow()
            info['model'] = tf.keras.models.load_model(path)
        return mid

    if name == 'dl_summary':
        if not args:
            raise EPLRuntimeError('dl_summary(model_id) requires model_id.', line)
        mid = str(args[0])
        if mid not in _dl_models:
            raise EPLRuntimeError(f'Unknown model: {mid}', line)
        info = _dl_models[mid]
        if info['framework'] == 'pytorch':
            model = info['model']
            total = sum(p.numel() for p in model.parameters())
            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            return {'framework': 'pytorch', 'total_params': total,
                    'trainable_params': trainable, 'layers': str(model)}
        elif info['framework'] == 'tensorflow':
            model = info['model']
            lines = []
            model.summary(print_fn=lambda x: lines.append(x))
            return {'framework': 'tensorflow', 'summary': '\n'.join(lines),
                    'total_params': model.count_params()}

    if name == 'dl_device':
        framework = str(args[0]).lower() if args else 'pytorch'
        if framework in ('pytorch', 'torch'):
            torch = _ensure_torch()
            if torch.cuda.is_available():
                return f'cuda ({torch.cuda.get_device_name(0)})'
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return 'mps'
            return 'cpu'
        elif framework in ('tensorflow', 'tf'):
            tf = _ensure_tensorflow()
            gpus = tf.config.list_physical_devices('GPU')
            return f'gpu ({len(gpus)} devices)' if gpus else 'cpu'
        return 'unknown'

    if name == 'dl_delete':
        if not args:
            raise EPLRuntimeError('dl_delete(model_id) requires model_id.', line)
        mid = str(args[0])
        if mid in _dl_models:
            del _dl_models[mid]
            return True
        return False

    raise EPLRuntimeError(f'Unknown deep learning function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  3D Graphics (PyOpenGL / ModernGL)
# ═══════════════════════════════════════════════════════════

_3d_contexts = {}     # context_id -> {'type': 'moderngl'|'opengl', ...}
_3d_objects = {}      # object_id -> {'type': 'mesh'|'light'|'camera', ...}

_moderngl_cache = [None]


def _ensure_moderngl():
    """Lazy-import moderngl for 3D rendering."""
    if _moderngl_cache[0] is not None:
        return _moderngl_cache[0]
    try:
        import moderngl            # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('moderngl', 'ModernGL'):
            raise EPLRuntimeError(
                'ModernGL not available. Install: pip install moderngl', 0)
        try:
            import moderngl        # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Install ModernGL manually: pip install moderngl', 0)
    _moderngl_cache[0] = moderngl
    return moderngl


def _call_3d(name, args, line):
    """Dispatcher for 3d_* functions (3D graphics/rendering)."""

    if name == '3d_create':
        if not args:
            raise EPLRuntimeError('3d_create(title[, width, height]) requires title.', line)
        pygame = _ensure_pygame()
        mgl = _ensure_moderngl()
        title = str(args[0])
        width = int(args[1]) if len(args) > 1 else 800
        height = int(args[2]) if len(args) > 2 else 600

        pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
        pygame.display.set_caption(title)
        ctx = mgl.create_context()
        ctx.enable(mgl.DEPTH_TEST)

        cid = f'3d_{_new_id()}'
        _3d_contexts[cid] = {
            'ctx': ctx, 'width': width, 'height': height,
            'objects': [], 'camera': {'pos': [0, 0, 5], 'target': [0, 0, 0], 'up': [0, 1, 0]},
            'lights': [{'pos': [2, 4, 3], 'color': [1, 1, 1], 'intensity': 1.0}],
            'bg_color': (0.1, 0.1, 0.15, 1.0),
            'clock': pygame.time.Clock(), 'fps': 60,
            'running': False, 'shaders': {},
        }

        # Create default shader program
        vertex_shader = '''
            #version 330
            in vec3 in_vert;
            in vec3 in_norm;
            in vec3 in_color;
            uniform mat4 model;
            uniform mat4 view;
            uniform mat4 projection;
            out vec3 v_norm;
            out vec3 v_color;
            out vec3 v_pos;
            void main() {
                gl_Position = projection * view * model * vec4(in_vert, 1.0);
                v_norm = mat3(transpose(inverse(model))) * in_norm;
                v_color = in_color;
                v_pos = vec3(model * vec4(in_vert, 1.0));
            }
        '''
        fragment_shader = '''
            #version 330
            in vec3 v_norm;
            in vec3 v_color;
            in vec3 v_pos;
            uniform vec3 light_pos;
            uniform vec3 light_color;
            uniform vec3 camera_pos;
            out vec4 f_color;
            void main() {
                // Ambient
                vec3 ambient = 0.15 * v_color;
                // Diffuse
                vec3 norm = normalize(v_norm);
                vec3 light_dir = normalize(light_pos - v_pos);
                float diff = max(dot(norm, light_dir), 0.0);
                vec3 diffuse = diff * light_color * v_color;
                // Specular
                vec3 view_dir = normalize(camera_pos - v_pos);
                vec3 reflect_dir = reflect(-light_dir, norm);
                float spec = pow(max(dot(view_dir, reflect_dir), 0.0), 32.0);
                vec3 specular = spec * light_color * 0.5;
                f_color = vec4(ambient + diffuse + specular, 1.0);
            }
        '''
        try:
            prog = ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader)
            _3d_contexts[cid]['shaders']['default'] = prog
        except Exception as e:
            _3d_contexts[cid]['shaders']['default'] = None

        return cid

    if name == '3d_cube':
        if not args:
            raise EPLRuntimeError('3d_cube(context_id[, x, y, z, size, color]) requires context_id.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        x = float(args[1]) if len(args) > 1 else 0.0
        y = float(args[2]) if len(args) > 2 else 0.0
        z = float(args[3]) if len(args) > 3 else 0.0
        size = float(args[4]) if len(args) > 4 else 1.0
        color = _from_epl(args[5]) if len(args) > 5 else [0.4, 0.6, 1.0]
        if isinstance(color, (list, tuple)) and len(color) == 3:
            color = [float(c) for c in color]
        else:
            color = [0.4, 0.6, 1.0]

        oid = f'obj_{_new_id()}'
        _3d_objects[oid] = {
            'type': 'cube', 'pos': [x, y, z], 'size': size,
            'color': color, 'rotation': [0, 0, 0], 'context': cid,
        }
        _3d_contexts[cid]['objects'].append(oid)
        return oid

    if name == '3d_sphere':
        if not args:
            raise EPLRuntimeError('3d_sphere(context_id[, x, y, z, radius, color]) requires context_id.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        x = float(args[1]) if len(args) > 1 else 0.0
        y = float(args[2]) if len(args) > 2 else 0.0
        z = float(args[3]) if len(args) > 3 else 0.0
        radius = float(args[4]) if len(args) > 4 else 0.5
        color = _from_epl(args[5]) if len(args) > 5 else [1.0, 0.4, 0.4]
        if isinstance(color, (list, tuple)) and len(color) == 3:
            color = [float(c) for c in color]
        else:
            color = [1.0, 0.4, 0.4]

        oid = f'obj_{_new_id()}'
        _3d_objects[oid] = {
            'type': 'sphere', 'pos': [x, y, z], 'radius': radius,
            'color': color, 'rotation': [0, 0, 0], 'context': cid,
        }
        _3d_contexts[cid]['objects'].append(oid)
        return oid

    if name == '3d_light':
        if not args:
            raise EPLRuntimeError('3d_light(context_id[, x, y, z, color, intensity]) requires context_id.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        x = float(args[1]) if len(args) > 1 else 2.0
        y = float(args[2]) if len(args) > 2 else 4.0
        z = float(args[3]) if len(args) > 3 else 3.0
        color = _from_epl(args[4]) if len(args) > 4 else [1.0, 1.0, 1.0]
        if isinstance(color, (list, tuple)) and len(color) == 3:
            color = [float(c) for c in color]
        else:
            color = [1.0, 1.0, 1.0]
        intensity = float(args[5]) if len(args) > 5 else 1.0
        _3d_contexts[cid]['lights'].append({
            'pos': [x, y, z], 'color': color, 'intensity': intensity})
        return True

    if name == '3d_camera':
        if len(args) < 4:
            raise EPLRuntimeError('3d_camera(context_id, x, y, z[, tx, ty, tz]) requires context_id and position.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        _3d_contexts[cid]['camera']['pos'] = [float(args[1]), float(args[2]), float(args[3])]
        if len(args) > 6:
            _3d_contexts[cid]['camera']['target'] = [float(args[4]), float(args[5]), float(args[6])]
        return True

    if name == '3d_rotate':
        if len(args) < 4:
            raise EPLRuntimeError('3d_rotate(object_id, rx, ry, rz) requires object_id and rotation angles.', line)
        oid = str(args[0])
        if oid not in _3d_objects:
            raise EPLRuntimeError(f'Unknown 3D object: {oid}', line)
        _3d_objects[oid]['rotation'] = [float(args[1]), float(args[2]), float(args[3])]
        return True

    if name == '3d_move':
        if len(args) < 4:
            raise EPLRuntimeError('3d_move(object_id, x, y, z) requires object_id and position.', line)
        oid = str(args[0])
        if oid not in _3d_objects:
            raise EPLRuntimeError(f'Unknown 3D object: {oid}', line)
        _3d_objects[oid]['pos'] = [float(args[1]), float(args[2]), float(args[3])]
        return True

    if name == '3d_color':
        if len(args) < 4:
            raise EPLRuntimeError('3d_color(object_id, r, g, b) requires object_id and RGB.', line)
        oid = str(args[0])
        if oid not in _3d_objects:
            raise EPLRuntimeError(f'Unknown 3D object: {oid}', line)
        _3d_objects[oid]['color'] = [float(args[1]), float(args[2]), float(args[3])]
        return True

    if name == '3d_render':
        if not args:
            raise EPLRuntimeError('3d_render(context_id) requires context_id.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        pygame = _ensure_pygame()
        ctx_data = _3d_contexts[cid]
        ctx = ctx_data['ctx']
        bg = ctx_data['bg_color']
        ctx.clear(*bg)
        # Rendering would use the shader program + VBOs for each object
        # This is the render loop hook — actual GPU rendering happens through ModernGL
        pygame.display.flip()
        return True

    if name == '3d_run':
        if not args:
            raise EPLRuntimeError('3d_run(context_id[, on_update]) requires context_id.', line)
        cid = str(args[0])
        if cid not in _3d_contexts:
            raise EPLRuntimeError(f'Unknown 3D context: {cid}', line)
        pygame = _ensure_pygame()
        ctx_data = _3d_contexts[cid]
        on_update = args[1] if len(args) > 1 and callable(args[1]) else None
        ctx_data['running'] = True
        clock = ctx_data['clock']
        fps = ctx_data['fps']

        while ctx_data['running']:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    ctx_data['running'] = False
                    break
            if on_update:
                try:
                    on_update()
                except Exception:
                    pass
            # Render frame
            ctx = ctx_data['ctx']
            ctx.clear(*ctx_data['bg_color'])
            pygame.display.flip()
            clock.tick(fps)

        pygame.quit()
        return True

    if name == '3d_delete':
        if not args:
            raise EPLRuntimeError('3d_delete(id) requires context or object ID.', line)
        target = str(args[0])
        if target in _3d_contexts:
            del _3d_contexts[target]
            return True
        if target in _3d_objects:
            cid = _3d_objects[target].get('context')
            if cid and cid in _3d_contexts:
                _3d_contexts[cid]['objects'] = [
                    o for o in _3d_contexts[cid]['objects'] if o != target]
            del _3d_objects[target]
            return True
        return False

    raise EPLRuntimeError(f'Unknown 3D function: {name}', line)


# ═══════════════════════════════════════════════════════════
#  Data Science (Pandas / NumPy / Matplotlib)
# ═══════════════════════════════════════════════════════════

_ds_frames = {}     # frame_id -> pandas DataFrame
_ds_groups = {}     # group_id -> DataFrameGroupBy


_pandas_cache = [None]
_matplotlib_cache = [None]


def _ensure_pandas():
    """Lazy-import pandas, auto-install if missing."""
    if _pandas_cache[0] is not None:
        return _pandas_cache[0]
    try:
        import pandas as pd         # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('pandas', 'Pandas'):
            raise EPLRuntimeError(
                'Failed to install Pandas. Install manually: pip install pandas', 0)
        try:
            import pandas as pd     # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Installed pandas but import still failed. Check pip output.', 0)
    _pandas_cache[0] = pd
    return pd


def _ensure_matplotlib():
    """Lazy-import matplotlib, auto-install if missing."""
    if _matplotlib_cache[0] is not None:
        return _matplotlib_cache[0]
    try:
        import matplotlib           # type: ignore[import-not-found]
    except ImportError:
        if not _auto_install('matplotlib', 'Matplotlib'):
            raise EPLRuntimeError(
                'Failed to install Matplotlib. Install manually: pip install matplotlib', 0)
        try:
            import matplotlib       # type: ignore[import-not-found]
        except ImportError:
            raise EPLRuntimeError(
                'Installed matplotlib but import still failed. Check pip output.', 0)
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    _matplotlib_cache[0] = plt
    return plt


def _df_to_epl(df):
    """Convert a Pandas DataFrame to an EPL-friendly list of maps."""
    return df.to_dict(orient='records')


def _call_ds(name, args, line):
    """Dispatcher for ds_* functions."""

    if name == 'ds_dataframe':
        if not args:
            raise EPLRuntimeError('ds_dataframe(data) requires data (list of maps or map of lists).', line)
        pd = _ensure_pandas()
        data = _from_epl(args[0])
        df = pd.DataFrame(data)
        fid = f'df_{_new_id()}'
        _ds_frames[fid] = df
        return fid

    if name == 'ds_read_csv':
        if not args:
            raise EPLRuntimeError('ds_read_csv(path) requires file path.', line)
        pd = _ensure_pandas()
        path = _os.path.normpath(str(args[0]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[0]}', line)
        if not _os.path.isfile(path):
            raise EPLRuntimeError(f'CSV file not found: {path}', line)
        try:
            df = pd.read_csv(path)
        except UnicodeDecodeError:
            raise EPLRuntimeError(f'CSV file encoding error: {args[0]} — try specifying encoding.', line)
        except Exception as e:
            raise EPLRuntimeError(f'CSV parse error: {e}', line)
        fid = f'df_{_new_id()}'
        _ds_frames[fid] = df
        return fid

    if name == 'ds_write_csv':
        if len(args) < 2:
            raise EPLRuntimeError('ds_write_csv(df_id, path) requires df_id and path.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        path = _os.path.normpath(str(args[1]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[1]}', line)
        _ds_frames[fid].to_csv(path, index=False)
        return None

    if name == 'ds_read_json':
        if not args:
            raise EPLRuntimeError('ds_read_json(path) requires file path.', line)
        pd = _ensure_pandas()
        path = _os.path.normpath(str(args[0]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[0]}', line)
        if not _os.path.isfile(path):
            raise EPLRuntimeError(f'JSON file not found: {path}', line)
        try:
            df = pd.read_json(path)
        except Exception as e:
            raise EPLRuntimeError(f'JSON parse error: {e}', line)
        fid = f'df_{_new_id()}'
        _ds_frames[fid] = df
        return fid

    if name == 'ds_head':
        if not args:
            raise EPLRuntimeError('ds_head(df_id[, n]) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        n = int(args[1]) if len(args) > 1 else 5
        return _df_to_epl(_ds_frames[fid].head(n))

    if name == 'ds_tail':
        if not args:
            raise EPLRuntimeError('ds_tail(df_id[, n]) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        n = int(args[1]) if len(args) > 1 else 5
        return _df_to_epl(_ds_frames[fid].tail(n))

    if name == 'ds_shape':
        if not args:
            raise EPLRuntimeError('ds_shape(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        shape = _ds_frames[fid].shape
        return [shape[0], shape[1]]

    if name == 'ds_columns':
        if not args:
            raise EPLRuntimeError('ds_columns(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return list(_ds_frames[fid].columns)

    if name == 'ds_select':
        if len(args) < 2:
            raise EPLRuntimeError('ds_select(df_id, columns) requires df_id and column list.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        cols = args[1] if isinstance(args[1], list) else [str(args[1])]
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid][[str(c) for c in cols]]
        return new_fid

    if name == 'ds_filter':
        if len(args) < 3:
            raise EPLRuntimeError('ds_filter(df_id, column, condition) requires df_id, column, and condition.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        col = str(args[1])
        cond = str(args[2])
        df = _ds_frames[fid]
        if col not in df.columns:
            raise EPLRuntimeError(f'Column not found: {col}', line)
        import operator
        ops = {'>': operator.gt, '<': operator.lt, '>=': operator.ge,
               '<=': operator.le, '==': operator.eq, '!=': operator.ne}
        # Check for string/special operators first
        cond_lower = cond.lower().strip()
        if cond_lower.startswith('contains '):
            val = cond[len('contains '):].strip().strip("'\"")
            mask = df[col].astype(str).str.contains(val, na=False)
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = df[mask].reset_index(drop=True)
            return new_fid
        if cond_lower == 'isna' or cond_lower == 'isnull':
            mask = df[col].isna()
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = df[mask].reset_index(drop=True)
            return new_fid
        if cond_lower == 'notna' or cond_lower == 'notnull':
            mask = df[col].notna()
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = df[mask].reset_index(drop=True)
            return new_fid
        if cond_lower.startswith('isin '):
            val_str = cond[len('isin '):].strip()
            vals = [v.strip().strip("'\"")
                    for v in val_str.strip('[]()').split(',')]
            # Try numeric conversion
            converted = []
            for v in vals:
                try:
                    converted.append(float(v))
                except ValueError:
                    converted.append(v)
            mask = df[col].isin(converted)
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = df[mask].reset_index(drop=True)
            return new_fid
        for op_str, op_fn in sorted(ops.items(), key=lambda x: -len(x[0])):
            if cond.startswith(op_str):
                val_str = cond[len(op_str):].strip().strip("'\"")
                try:
                    val = float(val_str)
                except ValueError:
                    val = val_str
                mask = op_fn(df[col], val)
                new_fid = f'df_{_new_id()}'
                _ds_frames[new_fid] = df[mask].reset_index(drop=True)
                return new_fid
        raise EPLRuntimeError(f'Invalid filter condition: {cond}. Use: >, <, >=, <=, ==, !=', line)

    if name == 'ds_sort':
        if len(args) < 2:
            raise EPLRuntimeError('ds_sort(df_id, column[, ascending]) requires df_id and column.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        col = str(args[1])
        asc = bool(args[2]) if len(args) > 2 else True
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].sort_values(col, ascending=asc).reset_index(drop=True)
        return new_fid

    if name == 'ds_group':
        if len(args) < 2:
            raise EPLRuntimeError('ds_group(df_id, column) requires df_id and column.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        gid = f'grp_{_new_id()}'
        _ds_groups[gid] = _ds_frames[fid].groupby(str(args[1]))
        return gid

    if name == 'ds_mean':
        if not args:
            raise EPLRuntimeError('ds_mean(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].mean(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return float(_ds_frames[fid][str(args[1])].mean())
        return _ds_frames[fid].mean(numeric_only=True).to_dict()

    if name == 'ds_sum':
        if not args:
            raise EPLRuntimeError('ds_sum(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].sum(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return float(_ds_frames[fid][str(args[1])].sum())
        return _ds_frames[fid].sum(numeric_only=True).to_dict()

    if name == 'ds_count':
        if not args:
            raise EPLRuntimeError('ds_count(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].size().reset_index(name='count')
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return len(_ds_frames[fid])

    if name == 'ds_describe':
        if not args:
            raise EPLRuntimeError('ds_describe(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _ds_frames[fid].describe().to_dict()

    if name == 'ds_merge':
        if len(args) < 3:
            raise EPLRuntimeError('ds_merge(df1_id, df2_id, on[, how]) requires two df_ids and join column.', line)
        fid1, fid2 = str(args[0]), str(args[1])
        if fid1 not in _ds_frames or fid2 not in _ds_frames:
            raise EPLRuntimeError('Unknown DataFrame ID.', line)
        how = str(args[3]) if len(args) > 3 else 'inner'
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid1].merge(_ds_frames[fid2], on=str(args[2]), how=how)
        return new_fid

    if name == 'ds_concat':
        if not args:
            raise EPLRuntimeError('ds_concat(df_id_list) requires list of df_ids.', line)
        pd = _ensure_pandas()
        ids = args[0] if isinstance(args[0], list) else [str(a) for a in args]
        dfs = []
        for fid in ids:
            fid = str(fid)
            if fid not in _ds_frames:
                raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
            dfs.append(_ds_frames[fid])
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = pd.concat(dfs, ignore_index=True)
        return new_fid

    if name == 'ds_dropna':
        if not args:
            raise EPLRuntimeError('ds_dropna(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].dropna().reset_index(drop=True)
        return new_fid

    if name == 'ds_fillna':
        if len(args) < 2:
            raise EPLRuntimeError('ds_fillna(df_id, value) requires df_id and fill value.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].fillna(args[1])
        return new_fid

    if name == 'ds_rename':
        if len(args) < 2:
            raise EPLRuntimeError('ds_rename(df_id, column_map) requires df_id and rename map.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        from epl.interpreter import EPLDict
        col_map = _from_epl(args[1]) if isinstance(args[1], EPLDict) else args[1]
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].rename(columns=col_map)
        return new_fid

    if name == 'ds_add_column':
        if len(args) < 3:
            raise EPLRuntimeError('ds_add_column(df_id, name, values) requires df_id, name, and values.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        new_fid = f'df_{_new_id()}'
        new_df = _ds_frames[fid].copy()
        new_df[str(args[1])] = args[2]
        _ds_frames[new_fid] = new_df
        return new_fid

    if name == 'ds_drop_column':
        if len(args) < 2:
            raise EPLRuntimeError('ds_drop_column(df_id, column) requires df_id and column name.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].drop(columns=[str(args[1])])
        return new_fid

    if name == 'ds_unique':
        if len(args) < 2:
            raise EPLRuntimeError('ds_unique(df_id, column) requires df_id and column.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _ds_frames[fid][str(args[1])].unique().tolist()

    if name == 'ds_value_counts':
        if len(args) < 2:
            raise EPLRuntimeError('ds_value_counts(df_id, column) requires df_id and column.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _ds_frames[fid][str(args[1])].value_counts().to_dict()

    if name == 'ds_sample':
        if not args:
            raise EPLRuntimeError('ds_sample(df_id[, n]) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        n = int(args[1]) if len(args) > 1 else 5
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].sample(n=min(n, len(_ds_frames[fid])), random_state=42)
        return new_fid

    # ── Plotting ──
    if name in ('ds_plot', 'ds_histogram', 'ds_scatter', 'ds_bar_chart',
                'ds_line_chart', 'ds_pie_chart'):
        plt = _ensure_matplotlib()
        if not args:
            raise EPLRuntimeError(f'{name}(df_id, ...) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        df = _ds_frames[fid]
        plt.figure(figsize=(10, 6))
        if name == 'ds_plot':
            x = str(args[1]) if len(args) > 1 else None
            y = str(args[2]) if len(args) > 2 else None
            kind = str(args[3]) if len(args) > 3 else 'line'
            if x and y:
                df.plot(x=x, y=y, kind=kind)
            elif x:
                df[x].plot(kind=kind)
            else:
                df.plot(kind=kind)
        elif name == 'ds_histogram':
            col = str(args[1]) if len(args) > 1 else None
            bins = int(args[2]) if len(args) > 2 else 20
            if col:
                df[col].hist(bins=bins)
            else:
                df.hist(bins=bins)
        elif name == 'ds_scatter':
            if len(args) < 3:
                raise EPLRuntimeError('ds_scatter(df_id, x, y) requires x and y columns.', line)
            plt.scatter(df[str(args[1])], df[str(args[2])])
            plt.xlabel(str(args[1]))
            plt.ylabel(str(args[2]))
        elif name == 'ds_bar_chart':
            if len(args) < 3:
                raise EPLRuntimeError('ds_bar_chart(df_id, x, y) requires x and y columns.', line)
            plt.bar(df[str(args[1])], df[str(args[2])])
            plt.xlabel(str(args[1]))
            plt.ylabel(str(args[2]))
        elif name == 'ds_line_chart':
            if len(args) < 3:
                raise EPLRuntimeError('ds_line_chart(df_id, x, y) requires x and y columns.', line)
            plt.plot(df[str(args[1])], df[str(args[2])])
            plt.xlabel(str(args[1]))
            plt.ylabel(str(args[2]))
        elif name == 'ds_pie_chart':
            if len(args) < 2:
                raise EPLRuntimeError('ds_pie_chart(df_id, column) requires column.', line)
            df[str(args[1])].value_counts().plot.pie(autopct='%1.1f%%')
        plt.tight_layout()
        return None

    if name == 'ds_save_plot':
        if not args:
            raise EPLRuntimeError('ds_save_plot(path) requires file path.', line)
        plt = _ensure_matplotlib()
        path = _os.path.normpath(str(args[0]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[0]}', line)
        plt.savefig(path, dpi=150, bbox_inches='tight')
        return str(args[0])

    if name == 'ds_show_plot':
        plt = _ensure_matplotlib()
        try:
            import matplotlib           # type: ignore[import-not-found]
            current_backend = matplotlib.get_backend()
            if current_backend.lower() == 'agg':
                # Agg is non-interactive; try switching to TkAgg for display
                matplotlib.use('TkAgg', force=True)
                import matplotlib.pyplot as plt_show  # type: ignore[import-not-found]
                plt_show.show()
                # Switch back to Agg for future non-interactive plots
                matplotlib.use('Agg', force=True)
            else:
                plt.show()
        except Exception:
            import sys
            print('ds_show_plot: Interactive display not available (no TkAgg backend).', file=sys.stderr)
            print('ds_show_plot: Use ds_save_plot(path) to save the plot to a file.', file=sys.stderr)
        return None

    if name == 'ds_correlation':
        if not args:
            raise EPLRuntimeError('ds_correlation(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _ds_frames[fid].corr(numeric_only=True).to_dict()

    if name == 'ds_pivot':
        if len(args) < 4:
            raise EPLRuntimeError('ds_pivot(df_id, index, columns, values) requires df_id, index, columns, values.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        new_fid = f'df_{_new_id()}'
        _ds_frames[new_fid] = _ds_frames[fid].pivot_table(
            index=str(args[1]), columns=str(args[2]), values=str(args[3]))
        return new_fid

    if name == 'ds_apply':
        if len(args) < 3:
            raise EPLRuntimeError('ds_apply(df_id, column, fn) requires df_id, column, and function.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if not callable(args[2]):
            raise EPLRuntimeError('ds_apply requires a callable function.', line)
        new_fid = f'df_{_new_id()}'
        new_df = _ds_frames[fid].copy()
        new_df[str(args[1])] = new_df[str(args[1])].apply(args[2])
        _ds_frames[new_fid] = new_df
        return new_fid

    if name == 'ds_to_list':
        if not args:
            raise EPLRuntimeError('ds_to_list(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _df_to_epl(_ds_frames[fid])

    if name == 'ds_to_map':
        if not args:
            raise EPLRuntimeError('ds_to_map(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return _ds_frames[fid].to_dict()

    if name == 'ds_write_json':
        if len(args) < 2:
            raise EPLRuntimeError('ds_write_json(df_id, path) requires df_id and path.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        path = _os.path.normpath(str(args[1]))
        if '..' in path.replace('/', _os.sep).split(_os.sep):
            raise EPLRuntimeError(f'Path traversal not allowed: {args[1]}', line)
        _ds_frames[fid].to_json(path, orient='records', indent=2)
        return None

    if name == 'ds_median':
        if not args:
            raise EPLRuntimeError('ds_median(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].median(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return float(_ds_frames[fid][str(args[1])].median())
        return _ds_frames[fid].median(numeric_only=True).to_dict()

    if name == 'ds_std':
        if not args:
            raise EPLRuntimeError('ds_std(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].std(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return float(_ds_frames[fid][str(args[1])].std())
        return _ds_frames[fid].std(numeric_only=True).to_dict()

    if name == 'ds_min':
        if not args:
            raise EPLRuntimeError('ds_min(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].min(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return _ds_frames[fid][str(args[1])].min()
        return _ds_frames[fid].min(numeric_only=True).to_dict()

    if name == 'ds_max':
        if not args:
            raise EPLRuntimeError('ds_max(df_id[, column]) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_groups:
            new_fid = f'df_{_new_id()}'
            _ds_frames[new_fid] = _ds_groups[fid].max(numeric_only=True).reset_index()
            return new_fid
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        if len(args) > 1:
            return _ds_frames[fid][str(args[1])].max()
        return _ds_frames[fid].max(numeric_only=True).to_dict()

    if name == 'ds_dtypes':
        if not args:
            raise EPLRuntimeError('ds_dtypes(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        return {col: str(dtype) for col, dtype in _ds_frames[fid].dtypes.items()}

    if name == 'ds_info':
        if not args:
            raise EPLRuntimeError('ds_info(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid not in _ds_frames:
            raise EPLRuntimeError(f'Unknown DataFrame: {fid}', line)
        df = _ds_frames[fid]
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'null_counts': df.isnull().sum().to_dict(),
            'memory_bytes': int(df.memory_usage(deep=True).sum()),
        }

    if name == 'ds_delete':
        if not args:
            raise EPLRuntimeError('ds_delete(df_id) requires df_id.', line)
        fid = str(args[0])
        if fid in _ds_frames:
            del _ds_frames[fid]
            return True
        if fid in _ds_groups:
            del _ds_groups[fid]
            return True
        return False

    raise EPLRuntimeError(f'Unknown data science function: {name}', line)
