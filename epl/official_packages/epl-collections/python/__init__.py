"""
EPL Collections Package - Python Backend
Advanced data structures: Stack, Queue, PriorityQueue, LinkedList, HashMap, BST, Graph, Set.
"""

import heapq as _heapq
from collections import deque as _deque

# ═══════════════════════════════════════════════════════════
#  Stack (LIFO)
# ═══════════════════════════════════════════════════════════


def stack_create():
    return {'_type': 'stack', 'items': []}


def stack_push(stack, item):
    stack['items'].append(item)
    return None


def stack_pop(stack):
    if not stack['items']:
        return None
    return stack['items'].pop()


def stack_peek(stack):
    if not stack['items']:
        return None
    return stack['items'][-1]


def stack_is_empty(stack):
    return len(stack['items']) == 0


def stack_size(stack):
    return len(stack['items'])


# ═══════════════════════════════════════════════════════════
#  Queue (FIFO)
# ═══════════════════════════════════════════════════════════


def queue_create():
    return {'_type': 'queue', 'items': _deque()}


def queue_enqueue(queue, item):
    queue['items'].append(item)
    return None


def queue_dequeue(queue):
    if not queue['items']:
        return None
    return queue['items'].popleft()


def queue_front(queue):
    if not queue['items']:
        return None
    return queue['items'][0]


def queue_is_empty(queue):
    return len(queue['items']) == 0


def queue_size(queue):
    return len(queue['items'])


# ═══════════════════════════════════════════════════════════
#  Priority Queue
# ═══════════════════════════════════════════════════════════


def pq_create():
    return {'_type': 'pq', 'items': [], 'counter': 0}


def pq_push(pq, item, priority):
    pq['counter'] += 1
    _heapq.heappush(pq['items'], (priority, pq['counter'], item))
    return None


def pq_pop(pq):
    if not pq['items']:
        return None
    _, _, item = _heapq.heappop(pq['items'])
    return item


def pq_peek(pq):
    if not pq['items']:
        return None
    return pq['items'][0][2]


# ═══════════════════════════════════════════════════════════
#  Linked List
# ═══════════════════════════════════════════════════════════


class _Node:
    __slots__ = ('value', 'next')

    def __init__(self, value):
        self.value = value
        self.next = None


def ll_create():
    return {'_type': 'linkedlist', 'head': None, 'size': 0}


def ll_append(ll, item):
    node = _Node(item)
    if ll['head'] is None:
        ll['head'] = node
    else:
        current = ll['head']
        while current.next:
            current = current.next
        current.next = node
    ll['size'] += 1
    return None


def ll_prepend(ll, item):
    node = _Node(item)
    node.next = ll['head']
    ll['head'] = node
    ll['size'] += 1
    return None


def ll_remove(ll, item):
    if ll['head'] is None:
        return False
    if ll['head'].value == item:
        ll['head'] = ll['head'].next
        ll['size'] -= 1
        return True
    current = ll['head']
    while current.next:
        if current.next.value == item:
            current.next = current.next.next
            ll['size'] -= 1
            return True
        current = current.next
    return False


def ll_get(ll, index):
    idx = int(index)
    current = ll['head']
    for _ in range(idx):
        if current is None:
            return None
        current = current.next
    return current.value if current else None


def ll_size(ll):
    return ll['size']


def ll_contains(ll, item):
    current = ll['head']
    while current:
        if current.value == item:
            return True
        current = current.next
    return False


def ll_reverse(ll):
    prev = None
    current = ll['head']
    while current:
        nxt = current.next
        current.next = prev
        prev = current
        current = nxt
    ll['head'] = prev
    return None


def ll_to_array(ll):
    result = []
    current = ll['head']
    while current:
        result.append(current.value)
        current = current.next
    return result


# ═══════════════════════════════════════════════════════════
#  HashMap
# ═══════════════════════════════════════════════════════════


def hm_create():
    return {'_type': 'hashmap', 'data': {}}


def hm_set(hmap, key, value):
    hmap['data'][key] = value
    return None


def hm_get(hmap, key):
    return hmap['data'].get(key, None)


def hm_has(hmap, key):
    return key in hmap['data']


def hm_remove(hmap, key):
    return hmap['data'].pop(key, None)


def hm_keys(hmap):
    return list(hmap['data'].keys())


def hm_values(hmap):
    return list(hmap['data'].values())


def hm_size(hmap):
    return len(hmap['data'])


def hm_clear(hmap):
    hmap['data'].clear()
    return None


# ═══════════════════════════════════════════════════════════
#  Binary Search Tree
# ═══════════════════════════════════════════════════════════


class _TreeNode:
    __slots__ = ('value', 'left', 'right')

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


def tree_create():
    return {'_type': 'bst', 'root': None, 'size': 0}


def _tree_insert_node(node, value):
    if node is None:
        return _TreeNode(value)
    if value < node.value:
        node.left = _tree_insert_node(node.left, value)
    elif value > node.value:
        node.right = _tree_insert_node(node.right, value)
    return node


def tree_insert(bst, value):
    bst['root'] = _tree_insert_node(bst['root'], value)
    bst['size'] += 1
    return None


def _tree_search_node(node, value):
    if node is None:
        return False
    if value == node.value:
        return True
    if value < node.value:
        return _tree_search_node(node.left, value)
    return _tree_search_node(node.right, value)


def tree_search(bst, value):
    return _tree_search_node(bst['root'], value)


def _tree_min_node(node):
    current = node
    while current and current.left:
        current = current.left
    return current


def _tree_remove_node(node, value):
    if node is None:
        return node
    if value < node.value:
        node.left = _tree_remove_node(node.left, value)
    elif value > node.value:
        node.right = _tree_remove_node(node.right, value)
    else:
        if node.left is None:
            return node.right
        if node.right is None:
            return node.left
        successor = _tree_min_node(node.right)
        node.value = successor.value
        node.right = _tree_remove_node(node.right, successor.value)
    return node


def tree_remove(bst, value):
    if _tree_search_node(bst['root'], value):
        bst['root'] = _tree_remove_node(bst['root'], value)
        bst['size'] -= 1
        return True
    return False


def tree_min(bst):
    if bst['root'] is None:
        return None
    node = _tree_min_node(bst['root'])
    return node.value


def tree_max(bst):
    if bst['root'] is None:
        return None
    current = bst['root']
    while current.right:
        current = current.right
    return current.value


def _inorder(node, result):
    if node:
        _inorder(node.left, result)
        result.append(node.value)
        _inorder(node.right, result)


def tree_inorder(bst):
    result = []
    _inorder(bst['root'], result)
    return result


def _tree_height_node(node):
    if node is None:
        return 0
    return 1 + max(_tree_height_node(node.left), _tree_height_node(node.right))


def tree_height(bst):
    return _tree_height_node(bst['root'])


def tree_size(bst):
    return bst['size']


# ═══════════════════════════════════════════════════════════
#  Graph (Adjacency List)
# ═══════════════════════════════════════════════════════════


def graph_create(directed=False):
    return {'_type': 'graph', 'adj': {}, 'directed': bool(directed), 'edge_count': 0}


def graph_add_node(graph, node):
    if node not in graph['adj']:
        graph['adj'][node] = []
    return None


def graph_add_edge(graph, from_node, to_node, weight=1):
    if from_node not in graph['adj']:
        graph['adj'][from_node] = []
    if to_node not in graph['adj']:
        graph['adj'][to_node] = []
    graph['adj'][from_node].append((to_node, weight))
    if not graph['directed']:
        graph['adj'][to_node].append((from_node, weight))
    graph['edge_count'] += 1
    return None


def graph_remove_node(graph, node):
    if node in graph['adj']:
        del graph['adj'][node]
    for key in graph['adj']:
        graph['adj'][key] = [(n, w) for n, w in graph['adj'][key] if n != node]
    return None


def graph_remove_edge(graph, from_node, to_node):
    if from_node in graph['adj']:
        graph['adj'][from_node] = [(n, w) for n, w in graph['adj'][from_node] if n != to_node]
    if not graph['directed'] and to_node in graph['adj']:
        graph['adj'][to_node] = [(n, w) for n, w in graph['adj'][to_node] if n != from_node]
    graph['edge_count'] -= 1
    return None


def graph_neighbors(graph, node):
    return [n for n, w in graph['adj'].get(node, [])]


def graph_has_edge(graph, from_node, to_node):
    return any(n == to_node for n, w in graph['adj'].get(from_node, []))


def graph_bfs(graph, start_node):
    visited = []
    queue = _deque([start_node])
    seen = {start_node}
    while queue:
        node = queue.popleft()
        visited.append(node)
        for neighbor, _ in graph['adj'].get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return visited


def graph_dfs(graph, start_node):
    visited = []
    stack = [start_node]
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        visited.append(node)
        for neighbor, _ in reversed(graph['adj'].get(node, [])):
            if neighbor not in seen:
                stack.append(neighbor)
    return visited


def graph_shortest_path(graph, start_node, end_node):
    import heapq

    dist = {start_node: 0}
    prev = {start_node: None}
    pq = [(0, start_node)]
    while pq:
        d, node = heapq.heappop(pq)
        if node == end_node:
            path = []
            while node is not None:
                path.append(node)
                node = prev[node]
            return list(reversed(path))
        if d > dist.get(node, float('inf')):
            continue
        for neighbor, weight in graph['adj'].get(node, []):
            new_dist = d + weight
            if new_dist < dist.get(neighbor, float('inf')):
                dist[neighbor] = new_dist
                prev[neighbor] = node
                heapq.heappush(pq, (new_dist, neighbor))
    return []


def graph_nodes(graph):
    return list(graph['adj'].keys())


def graph_edges(graph):
    edges = []
    for node in graph['adj']:
        for neighbor, weight in graph['adj'][node]:
            edges.append({'from': node, 'to': neighbor, 'weight': weight})
    return edges


def graph_node_count(graph):
    return len(graph['adj'])


def graph_edge_count(graph):
    return graph['edge_count']


# ═══════════════════════════════════════════════════════════
#  Set
# ═══════════════════════════════════════════════════════════


def set_create():
    return {'_type': 'set', 'items': set()}


def set_add(s, item):
    s['items'].add(item)
    return None


def set_remove(s, item):
    s['items'].discard(item)
    return None


def set_contains(s, item):
    return item in s['items']


def set_union(set1, set2):
    return {'_type': 'set', 'items': set1['items'] | set2['items']}


def set_intersection(set1, set2):
    return {'_type': 'set', 'items': set1['items'] & set2['items']}


def set_difference(set1, set2):
    return {'_type': 'set', 'items': set1['items'] - set2['items']}


def set_size(s):
    return len(s['items'])
