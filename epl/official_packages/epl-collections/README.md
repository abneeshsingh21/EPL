# epl-collections

Advanced data structures for EPL — Stack, Queue, LinkedList, HashMap, Tree, Graph, Priority Queue, Set.

## Installation

```
epl install epl-collections
```

## Quick Start

```epl
Import "epl-collections"

Note: Stack
Set stack to create_stack()
stack_push(stack, "hello")
Say stack_pop(stack)

Note: Graph with shortest path
Set g to create_graph(False)
graph_add_edge(g, "A", "B", 5)
graph_add_edge(g, "B", "C", 3)
graph_add_edge(g, "A", "C", 10)
Say graph_shortest_path(g, "A", "C")
```

## Data Structures

### Stack (LIFO)
`create_stack`, `stack_push`, `stack_pop`, `stack_peek`, `stack_is_empty`, `stack_size`

### Queue (FIFO)
`create_queue`, `enqueue`, `dequeue`, `queue_front`, `queue_is_empty`, `queue_size`

### Priority Queue
`create_priority_queue`, `pq_push(pq, item, priority)`, `pq_pop`, `pq_peek`

### Linked List
`create_linked_list`, `ll_append`, `ll_prepend`, `ll_remove`, `ll_get`, `ll_size`, `ll_contains`, `ll_reverse`, `ll_to_array`

### HashMap
`create_hashmap`, `hm_set`, `hm_get`, `hm_has`, `hm_remove`, `hm_keys`, `hm_values`, `hm_size`, `hm_clear`

### Binary Search Tree
`create_tree`, `tree_insert`, `tree_search`, `tree_remove`, `tree_min`, `tree_max`, `tree_inorder`, `tree_height`, `tree_size`

### Graph
`create_graph(directed)`, `graph_add_node`, `graph_add_edge(g, from, to, weight)`, `graph_neighbors`, `graph_bfs`, `graph_dfs`, `graph_shortest_path`, `graph_has_edge`

### Set
`create_set`, `set_add`, `set_remove`, `set_contains`, `set_union`, `set_intersection`, `set_difference`, `set_size`
