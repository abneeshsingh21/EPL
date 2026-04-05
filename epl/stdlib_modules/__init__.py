"""
EPL Stdlib Modules — Domain-organized standard library functions.

This package provides domain-organized access to EPL's standard library.
The actual implementations live in epl/stdlib.py (the monolith), and this
package provides clean import boundaries for future gradual extraction.

Usage:
    from epl.stdlib_modules import http, db, datetime_funcs
    from epl.stdlib_modules.registry import get_module_for_function
"""

# Domain module map — which function belongs to which domain
DOMAIN_MAP = {
    # HTTP Client
    'http': {
        'http_get', 'http_post', 'http_put', 'http_delete', 'http_request',
        'url_encode', 'url_decode', 'url_parse',
    },
    # JSON
    'json': {
        'json_parse', 'json_stringify', 'json_pretty',
        'json_valid', 'json_merge', 'json_query',
    },
    # Database (SQLite)
    'db': {
        'db_open', 'db_close', 'db_execute', 'db_query', 'db_query_one',
        'db_insert', 'db_tables', 'db_create_table',
        'db_update', 'db_delete', 'db_count', 'db_table_info',
        'db_begin', 'db_commit', 'db_rollback', 'db_backup',
    },
    # DateTime
    'datetime': {
        'now', 'today', 'date_format', 'date_parse', 'date_diff',
        'date_add', 'year', 'month', 'day', 'hour', 'minute', 'second',
        'day_of_week', 'days_in_month', 'is_leap_year', 'sleep',
        'utc_now', 'timezone', 'to_timestamp', 'from_timestamp',
        'week_of_year', 'is_weekend', 'is_weekday', 'date_range',
    },
    # Regex
    'regex': {
        'regex_match', 'regex_find', 'regex_find_all', 'regex_replace',
        'regex_split', 'regex_test',
        'regex_compile', 'regex_replace_fn', 'regex_groups',
    },
    # File System
    'fs': {
        'file_exists', 'file_delete', 'file_rename', 'file_copy',
        'file_size', 'file_read', 'file_write', 'file_append',
        'file_read_lines', 'file_write_lines',
        'dir_list', 'dir_create', 'dir_delete', 'dir_exists',
        'path_join', 'path_basename', 'path_dirname', 'path_extension',
        'path_absolute', 'path_split', 'temp_file', 'temp_dir',
        'file_modified_time', 'file_created_time', 'file_is_dir', 'file_is_file',
        'file_read_binary', 'file_write_binary', 'file_move',
        'dir_walk', 'file_glob',
        'path_normalize', 'path_relative',
    },
    # OS & Process
    'os': {
        'env_get', 'env_set', 'env_has', 'env_all',
        'exec', 'exec_output', 'platform', 'cpu_count',
        'memory_usage', 'cwd', 'chdir', 'pid',
        'env_delete', 'hostname', 'arch', 'user_home', 'user_name',
        'uptime', 'exec_async', 'kill_process', 'is_admin',
    },
    # Crypto & Encoding
    'crypto': {
        'hash_md5', 'hash_sha256', 'hash_sha512',
        'base64_encode', 'base64_decode',
        'uuid', 'uuid4',
        'hmac_sha256', 'hmac_sha512',
        'hash_sha1', 'hash_sha384', 'hash_file',
        'secure_random_bytes', 'secure_random_int',
        'aes_encrypt', 'aes_decrypt',
        'pbkdf2_hash', 'pbkdf2_verify',
        'base64_url_encode', 'base64_url_decode',
        'html_encode', 'html_decode',
        'base32_encode', 'base32_decode',
        'hex_encode', 'hex_decode',
    },
    # Math
    'math': {
        'pi', 'euler', 'inf', 'nan',
        'atan', 'atan2', 'asin', 'acos',
        'degrees', 'radians', 'gcd', 'lcm', 'factorial',
        'is_finite', 'is_nan', 'clamp', 'lerp', 'sign',
        'log2', 'log10', 'exp', 'hypot',
        'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh',
        'ceil_div', 'fmod', 'copysign',
        'permutations', 'combinations',
        'variance', 'std_dev',
    },
    # Strings
    'string': {
        'format', 'regex_escape', 'string_bytes', 'bytes_string',
    },
    # Collections
    'collections': {
        'zip_lists', 'enumerate_list', 'dict_from_lists',
        'set_create', 'set_add', 'set_remove', 'set_contains',
        'set_union', 'set_intersection', 'set_difference',
        'set_size', 'set_to_list', 'set_clear',
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
        'group_by', 'partition', 'frequency_map',
    },
    # CSV
    'csv': {
        'csv_read', 'csv_write', 'csv_parse',
    },
    # Threading & Concurrency
    'concurrency': {
        'thread_run', 'thread_sleep', 'atomic_counter',
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
    },
    # Networking
    'net': {
        'socket_connect', 'socket_send', 'socket_receive', 'socket_close',
        'dns_lookup', 'is_port_open',
        'net_dns_lookup', 'net_dns_lookup_all', 'net_reverse_dns',
        'net_is_port_open', 'net_local_ip', 'net_hostname',
        'net_http_get', 'net_http_post', 'net_http_put', 'net_http_delete',
        'net_http_client', 'net_http_client_get', 'net_http_client_post',
        'net_http_client_put', 'net_http_client_delete',
        'net_tcp_connect', 'net_tcp_server', 'net_tcp_send', 'net_tcp_receive',
        'net_tcp_receive_line', 'net_tcp_close',
        'net_udp_socket', 'net_udp_bind', 'net_udp_send_to',
        'net_udp_receive_from', 'net_udp_close',
        'net_http_server', 'net_http_server_route', 'net_http_server_start',
        'net_http_server_stop',
        'net_ws_connect', 'net_ws_send', 'net_ws_receive', 'net_ws_close',
        'http_client_create', 'http_client_get', 'http_client_post',
        'http_client_put', 'http_client_delete',
        'tcp_connect', 'tcp_send', 'tcp_receive', 'tcp_close',
    },
    # Web Server
    'web': {
        'web_create', 'web_route', 'web_get', 'web_post', 'web_put', 'web_delete',
        'web_start', 'web_json', 'web_html', 'web_redirect', 'web_static',
        'web_template', 'web_request_data', 'web_request_args', 'web_request_method',
        'web_request_path', 'web_request_header', 'web_set_cors',
        'web_middleware', 'web_error_handler', 'web_stop',
        'web_api_create', 'web_api_resource',
        'web_session_get', 'web_session_set', 'web_session_clear',
        'web_request_param',
        'web_cookie_get', 'web_cookie_set',
        'web_test_client', 'web_test_get', 'web_test_post',
        'web_upload_config', 'web_request_files',
        'web_send_file', 'web_response', 'web_url_for',
    },
    # Auth & JWT
    'auth': {
        'auth_hash_password', 'auth_verify_password',
        'auth_jwt_create', 'auth_jwt_verify', 'auth_jwt_decode',
        'auth_generate_token', 'auth_api_key_create', 'auth_api_key_verify',
        'auth_bearer_token', 'auth_basic_decode',
    },
    # WebSocket Server
    'websocket': {
        'ws_server_create', 'ws_server_start', 'ws_server_stop',
        'ws_on_connect', 'ws_on_message', 'ws_on_disconnect',
        'ws_broadcast', 'ws_send_to',
        'ws_room_join', 'ws_room_leave', 'ws_room_broadcast',
        'ws_clients',
    },
    # Template Engine
    'template': {
        'template_create', 'template_render', 'template_render_string',
        'template_add_filter', 'template_from_file', 'template_exists',
    },
    # HTML Builder
    'html': {
        'html_element', 'html_table', 'html_form', 'html_list',
        'html_link', 'html_image', 'html_page',
        'html_escape', 'html_unescape', 'html_minify',
    },
    # API Helpers
    'api': {
        'api_paginate', 'api_validate', 'api_error', 'api_success',
        'api_response', 'api_parse_query', 'api_version', 'api_link_header',
    },
    # ORM
    'orm': {
        'orm_open', 'orm_close', 'orm_define_model', 'orm_add_field',
        'orm_migrate', 'orm_create', 'orm_find', 'orm_find_by_id',
        'orm_update', 'orm_delete', 'orm_delete_where',
        'orm_query', 'orm_raw_query', 'orm_raw_execute',
        'orm_transaction_begin', 'orm_transaction_commit', 'orm_transaction_rollback',
        'orm_table_exists',
        'orm_has_many', 'orm_belongs_to', 'orm_with_related',
        'orm_paginate', 'orm_order_by', 'orm_count_where',
        'orm_seed', 'orm_add_index', 'orm_first', 'orm_last',
    },
    # Desktop GUI
    'gui': {
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
    },
    # Mobile
    'mobile': {
        'mobile_create', 'mobile_label', 'mobile_button', 'mobile_input',
        'mobile_image', 'mobile_box', 'mobile_scroll', 'mobile_switch',
        'mobile_slider', 'mobile_select', 'mobile_webview', 'mobile_run',
        'mobile_build', 'mobile_style', 'mobile_navigate', 'mobile_screen',
        'mobile_alert', 'mobile_status_bar', 'mobile_get_value', 'mobile_set_value',
        'mobile_destroy', 'android_project',
    },
    # Game Development
    'game': {
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
    },
    # ML/AI
    'ml': {
        'ml_load_data', 'ml_split', 'ml_linear_regression', 'ml_logistic_regression',
        'ml_decision_tree', 'ml_random_forest', 'ml_svm', 'ml_knn', 'ml_kmeans',
        'ml_train', 'ml_predict', 'ml_accuracy', 'ml_save_model', 'ml_load_model',
        'ml_neural_network', 'ml_normalize', 'ml_confusion_matrix',
        'ml_mse', 'ml_mae', 'ml_r2',
        'ml_cross_validate', 'ml_classification_report', 'ml_feature_importance',
        'ml_delete_model', 'ml_delete_data',
    },
    # Deep Learning
    'dl': {
        'dl_tensor', 'dl_sequential', 'dl_compile', 'dl_train', 'dl_predict',
        'dl_save', 'dl_load', 'dl_summary', 'dl_device', 'dl_delete',
    },
    # 3D Graphics
    'graphics3d': {
        '3d_create', '3d_cube', '3d_sphere', '3d_light', '3d_camera',
        '3d_rotate', '3d_move', '3d_color', '3d_render', '3d_run', '3d_delete',
    },
    # Data Science
    'ds': {
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
    },
    # Real Database
    'real_db': {
        'real_db_connect', 'real_db_get', 'real_db_close', 'real_db_close_all',
        'real_db_execute', 'real_db_execute_many', 'real_db_query', 'real_db_query_one',
        'real_db_insert', 'real_db_update', 'real_db_delete', 'real_db_find_by_id',
        'real_db_create_table', 'real_db_count', 'real_db_table_exists',
        'real_db_begin', 'real_db_commit', 'real_db_rollback',
        'real_db_migrate', 'real_db_table',
        'real_db_model_define', 'real_db_model_create', 'real_db_model_find',
        'real_db_model_all', 'real_db_model_where', 'real_db_model_first',
        'real_db_model_update', 'real_db_model_delete', 'real_db_model_count',
    },
    # Real Concurrency
    'real_concurrency': {
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
    },
    # VM
    'vm': {
        'vm_run', 'vm_compile', 'vm_disassemble',
    },
    # System
    'system': {
        'print_error', 'read_input', 'exit_code',
        'args', 'timer_start', 'timer_stop',
    },
    # Testing
    'testing': {
        'test_describe', 'test_it', 'test_before_each', 'test_after_each',
        'test_skip', 'test_expect_near', 'test_expect_match',
        'test_benchmark', 'test_assert_throws',
    },
}

# Build reverse lookup: function_name → domain
_FUNCTION_TO_DOMAIN = {}
for _domain, _funcs in DOMAIN_MAP.items():
    for _func in _funcs:
        _FUNCTION_TO_DOMAIN[_func] = _domain


def get_domain(function_name):
    """Return the domain module name for a given function."""
    return _FUNCTION_TO_DOMAIN.get(function_name)


def get_functions_for_domain(domain):
    """Return the set of function names for a given domain."""
    return DOMAIN_MAP.get(domain, set())


def list_domains():
    """Return all available domain names."""
    return list(DOMAIN_MAP.keys())
