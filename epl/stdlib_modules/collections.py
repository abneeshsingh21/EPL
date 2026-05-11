"""
epl.stdlib_modules.collections — Data structures domain public API.
"""

from __future__ import annotations

FUNCTIONS = frozenset(
    {
        # Basic list/map helpers
        'zip_lists',
        'enumerate_list',
        'dict_from_lists',
        # Sets
        'set_create',
        'set_add',
        'set_remove',
        'set_contains',
        'set_union',
        'set_intersection',
        'set_difference',
        'set_size',
        'set_to_list',
        'set_clear',
        # Linked List
        'linked_list_new',
        'linked_list_append',
        'linked_list_prepend',
        'linked_list_pop',
        'linked_list_pop_front',
        'linked_list_get',
        'linked_list_size',
        'linked_list_to_list',
        # Priority Queue
        'priority_queue_new',
        'priority_queue_push',
        'priority_queue_pop',
        'priority_queue_peek',
        'priority_queue_size',
        # Deque
        'deque_new',
        'deque_push_back',
        'deque_push_front',
        'deque_pop_back',
        'deque_pop_front',
        'deque_size',
        'deque_to_list',
        # Ordered Map
        'ordered_map_new',
        'ordered_map_set',
        'ordered_map_get',
        'ordered_map_delete',
        'ordered_map_keys',
        'ordered_map_values',
        'ordered_map_size',
        'ordered_map_to_list',
        # Functional
        'group_by',
        'partition',
        'frequency_map',
    }
)

DOCS: dict[str, str] = {
    'zip_lists': 'Zip two lists into a list of pairs.',
    'enumerate_list': 'Return list of [index, value] pairs.',
    'dict_from_lists': 'Create a map from key list and value list.',
    'set_create': 'Create a new set.',
    'set_add': 'Add an element to a set.',
    'set_remove': 'Remove an element from a set.',
    'set_contains': 'Check if a set contains an element.',
    'set_union': 'Union of two sets.',
    'set_intersection': 'Intersection of two sets.',
    'set_difference': 'Difference of two sets (A - B).',
    'set_size': 'Number of elements in a set.',
    'set_to_list': 'Convert a set to a list.',
    'linked_list_new': 'Create a new linked list.',
    'linked_list_append': 'Append an element to the end.',
    'linked_list_prepend': 'Prepend an element to the front.',
    'linked_list_pop': 'Remove and return the last element.',
    'linked_list_pop_front': 'Remove and return the first element.',
    'priority_queue_new': 'Create a min-heap priority queue.',
    'priority_queue_push': 'Push an element with priority.',
    'priority_queue_pop': 'Pop the highest-priority element.',
    'priority_queue_peek': 'Peek at the highest-priority element.',
    'deque_new': 'Create a double-ended queue.',
    'deque_push_back': 'Push to the back of the deque.',
    'deque_push_front': 'Push to the front of the deque.',
    'deque_pop_back': 'Pop from the back of the deque.',
    'deque_pop_front': 'Pop from the front of the deque.',
    'ordered_map_new': 'Create an insertion-ordered map.',
    'ordered_map_set': 'Set a key in the ordered map.',
    'ordered_map_get': 'Get a value from the ordered map.',
    'ordered_map_keys': 'Get keys in insertion order.',
    'ordered_map_values': 'Get values in insertion order.',
    'group_by': 'Group list elements by a key function.',
    'partition': 'Split list into two based on a predicate.',
    'frequency_map': 'Count occurrences of each element.',
}


def get_functions() -> frozenset[str]:
    return FUNCTIONS


def describe(fn_name: str) -> str:
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
