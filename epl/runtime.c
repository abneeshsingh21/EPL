/*
 * EPL Runtime Library (v2.1)
 * Full-featured C runtime for compiled EPL programs.
 * Provides: tagged values, lists, maps, objects, strings, math, I/O,
 * memory management (arena + free functions), exception handling (setjmp/longjmp).
 * Supports native, WASI, and Emscripten targets.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <time.h>
#include <stdint.h>

/* ─── WASM/Emscripten compatibility layer ──────────── */
#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#include <setjmp.h>
/* No threading in Emscripten single-threaded mode */
static void gc_lock(void)   {}
static void gc_unlock(void) {}
#elif defined(__wasi__) || defined(__wasm__)
#include <setjmp.h>
/* WASI has no threading primitives */
static void gc_lock(void)   {}
static void gc_unlock(void) {}
#elif defined(_WIN32)
#include <setjmp.h>
#include <windows.h>
/* ─── Platform-agnostic mutex for GC thread safety ─ */
static CRITICAL_SECTION gc_mutex;
static int gc_mutex_init = 0;
static void gc_lock(void)   { if (!gc_mutex_init) { InitializeCriticalSection(&gc_mutex); gc_mutex_init = 1; } EnterCriticalSection(&gc_mutex); }
static void gc_unlock(void) { LeaveCriticalSection(&gc_mutex); }
#else
#include <setjmp.h>
#include <unistd.h>
#include <pthread.h>
static pthread_mutex_t gc_mutex = PTHREAD_MUTEX_INITIALIZER;
static void gc_lock(void)   { pthread_mutex_lock(&gc_mutex); }
static void gc_unlock(void) { pthread_mutex_unlock(&gc_mutex); }
#endif

/* ─── Tags ─────────────────────────────────────────── */
#define TAG_INT    0
#define TAG_FLOAT  1
#define TAG_BOOL   2
#define TAG_STRING 3
#define TAG_NONE   4
#define TAG_LIST   5
#define TAG_MAP    6
#define TAG_OBJECT 7

/* ─── EPLValue ─────────────────────────────────────── */
typedef struct {
    int8_t  tag;
    int64_t data;
} EPLValue;

/* ─── EPLList ──────────────────────────────────────── */
typedef struct {
    int32_t  *tags;
    int64_t  *data;
    int       count;
    int       capacity;
} EPLList;

/* ─── EPLMap (dynamically resizable hash table) ──── */
#define MAP_INITIAL_BUCKETS 128
#define MAP_LOAD_FACTOR_NUM 3   /* resize when count > capacity * 3/4 */
#define MAP_LOAD_FACTOR_DEN 4
typedef struct EPLMapEntry {
    char    *key;
    int32_t  tag;
    int64_t  data;
    struct EPLMapEntry *next;
} EPLMapEntry;

typedef struct {
    EPLMapEntry **buckets;
    int           bucket_count;
    int           entry_count;
} EPLMap;

/* ─── EPLObject (dynamically growable properties) ── */
#define OBJ_INITIAL_PROPS 16
typedef struct {
    char     *class_name;
    char    **prop_names;
    int32_t  *prop_tags;
    int64_t  *prop_data;
    int       prop_count;
    int       prop_capacity;
} EPLObject;

/* ════════════════════════════════════════════════════
 * Exception Handling (setjmp/longjmp)
 * ═══════════════════════════════════════════════════ */
#define EPL_EXCEPTION_STACK_SIZE 64
static jmp_buf epl_exception_stack[EPL_EXCEPTION_STACK_SIZE];
static int     epl_exception_depth = 0;
static char    epl_exception_msg[1024] = {0};

int epl_try_begin(void) {
    if (epl_exception_depth >= EPL_EXCEPTION_STACK_SIZE) {
        fprintf(stderr, "EPL: Exception stack overflow\n");
        exit(1);
    }
    int result = setjmp(epl_exception_stack[epl_exception_depth]);
    if (result == 0) {
        epl_exception_depth++;
    }
    return result;  /* 0 = normal entry, non-zero = exception caught */
}

void epl_try_end(void) {
    if (epl_exception_depth > 0)
        epl_exception_depth--;
}

void epl_throw(const char *msg) {
    if (msg) {
        strncpy(epl_exception_msg, msg, sizeof(epl_exception_msg) - 1);
        epl_exception_msg[sizeof(epl_exception_msg) - 1] = '\0';
    } else {
        epl_exception_msg[0] = '\0';
    }
    if (epl_exception_depth > 0) {
        epl_exception_depth--;
        longjmp(epl_exception_stack[epl_exception_depth], 1);
    } else {
        fprintf(stderr, "EPL Unhandled Exception: %s\n", epl_exception_msg);
        exit(1);
    }
}

const char* epl_get_exception(void) {
    return epl_exception_msg;
}

/* ════════════════════════════════════════════════════
 * Memory Management — Arena + Free Functions
 * ═══════════════════════════════════════════════════ */
#define ARENA_BLOCK_SIZE (1024 * 1024)  /* 1 MB */
typedef struct ArenaBlock {
    char *data;
    size_t used;
    size_t capacity;
    struct ArenaBlock *next;
} ArenaBlock;

static ArenaBlock *arena_head = NULL;

static ArenaBlock* arena_new_block(size_t min_size) {
    size_t cap = min_size > ARENA_BLOCK_SIZE ? min_size : ARENA_BLOCK_SIZE;
    ArenaBlock *b = (ArenaBlock*)malloc(sizeof(ArenaBlock));
    if (!b) { fprintf(stderr, "EPL: arena out of memory\n"); exit(1); }
    b->data = (char*)malloc(cap);
    if (!b->data) { free(b); fprintf(stderr, "EPL: arena out of memory\n"); exit(1); }
    b->used = 0;
    b->capacity = cap;
    b->next = arena_head;
    arena_head = b;
    return b;
}

void* epl_arena_alloc(size_t size) {
    /* Align to 8 bytes */
    size = (size + 7) & ~7;
    if (!arena_head || arena_head->used + size > arena_head->capacity) {
        arena_new_block(size);
    }
    void *ptr = arena_head->data + arena_head->used;
    arena_head->used += size;
    return ptr;
}

void epl_arena_reset(void) {
    ArenaBlock *b = arena_head;
    while (b) {
        ArenaBlock *next = b->next;
        free(b->data);
        free(b);
        b = next;
    }
    arena_head = NULL;
}

/* Individual free functions (for non-GC-managed allocations) */
void epl_string_free(char *s) {
    if (s) free(s);
}

void epl_list_free(EPLList *l) {
    if (!l) return;
    /* Free string data in list elements */
    for (int i = 0; i < l->count; i++) {
        if (l->tags[i] == TAG_STRING && l->data[i]) {
            free((char*)(intptr_t)l->data[i]);
        }
    }
    free(l->tags);
    free(l->data);
    free(l);
}

void epl_map_free(EPLMap *m) {
    if (!m) return;
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            EPLMapEntry *next = e->next;
            if (e->key) free(e->key);
            if (e->tag == TAG_STRING && e->data) free((char*)(intptr_t)e->data);
            free(e);
            e = next;
        }
    }
    free(m->buckets);
    free(m);
}

void epl_object_free(EPLObject *o) {
    if (!o) return;
    if (o->class_name) free(o->class_name);
    for (int i = 0; i < o->prop_count; i++) {
        if (o->prop_names[i]) free(o->prop_names[i]);
        if (o->prop_tags[i] == TAG_STRING && o->prop_data[i]) {
            free((char*)(intptr_t)o->prop_data[i]);
        }
    }
    free(o->prop_names);
    free(o->prop_tags);
    free(o->prop_data);
    free(o);
}

/*
 * GC-specific cleanup: free internal data of a GC-managed object
 * WITHOUT freeing the struct itself (since it lives inside the
 * EPLGCHeader allocation block).  The caller frees `hdr` which
 * encompasses the object.
 *
 * GC-managed strings inside GC-managed containers are themselves
 * tracked by the GC, so we must NOT free them here — the sweep
 * will handle them independently.
 */
static void gc_cleanup_list(EPLList *l) {
    if (!l) return;
    /* Only free non-GC string data; GC-managed strings are swept separately */
    /* NOTE: strings in GC-managed lists may be GC-managed themselves; skip freeing */
    free(l->tags);
    free(l->data);
    /* Do NOT free(l) — embedded in GC header block */
}

static void gc_cleanup_map(EPLMap *m) {
    if (!m) return;
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            EPLMapEntry *next = e->next;
            if (e->key) free(e->key);
            /* Do NOT free e->data strings — may be GC-managed */
            free(e);
            e = next;
        }
    }
    free(m->buckets);
    /* Do NOT free(m) — embedded in GC header block */
}

static void gc_cleanup_object(EPLObject *o) {
    if (!o) return;
    if (o->class_name) free(o->class_name);
    for (int i = 0; i < o->prop_count; i++) {
        if (o->prop_names[i]) free(o->prop_names[i]);
        /* Do NOT free prop_data strings — may be GC-managed */
    }
    free(o->prop_names);
    free(o->prop_tags);
    free(o->prop_data);
    /* Do NOT free(o) — embedded in GC header block */
}

/* ════════════════════════════════════════════════════
 * Mark-and-Sweep Garbage Collector (v5.0)
 *
 * Every heap-allocated collection (list, map, object)
 * and dynamically-created string is wrapped with an
 * EPLGCHeader that lives just before the user pointer.
 *
 * A shadow-stack of GC roots is maintained by the
 * compiler: each local variable that may hold a heap
 * pointer is pushed on entry and popped on scope exit.
 *
 * Collection is triggered automatically when the
 * allocation count crosses a dynamic threshold.
 * ═══════════════════════════════════════════════════ */

/* ── GC object header (prepended to every managed alloc) ── */
typedef struct EPLGCHeader {
    uint8_t  marked;       /* 0 = white (garbage), 1 = grey/black (live) */
    int8_t   tag;          /* TAG_STRING / TAG_LIST / TAG_MAP / TAG_OBJECT */
    struct EPLGCHeader *gc_next;   /* intrusive linked-list of all objects */
} EPLGCHeader;

/* ── Global GC state ── */
static EPLGCHeader *gc_all_objects  = NULL;  /* head of all-objects list */
static int          gc_object_count = 0;
static int          gc_threshold    = 256;   /* first collection after 256 allocs */

/* ── Shadow stack (root set — dynamically growable) ── */
#define GC_ROOT_STACK_INITIAL 8192
static void **gc_root_stack = NULL;
static int    gc_root_top = 0;
static int    gc_root_capacity = 0;

static void gc_root_stack_init(void) {
    if (!gc_root_stack) {
        gc_root_capacity = GC_ROOT_STACK_INITIAL;
        gc_root_stack = (void**)malloc(sizeof(void*) * gc_root_capacity);
        if (!gc_root_stack) { fprintf(stderr, "EPL GC: root stack alloc failed\n"); exit(1); }
    }
}

/* Push a root pointer (called by compiled code on every heap-var store) */
void epl_gc_root_push(void *ptr) {
    gc_lock();
    gc_root_stack_init();
    if (gc_root_top >= gc_root_capacity) {
        gc_root_capacity *= 2;
        void **new_stack = (void**)realloc(gc_root_stack, sizeof(void*) * gc_root_capacity);
        if (!new_stack) { fprintf(stderr, "EPL GC: root stack realloc failed\n"); gc_unlock(); exit(1); }
        gc_root_stack = new_stack;
    }
    gc_root_stack[gc_root_top++] = ptr;
    gc_unlock();
}

/* Pop N roots (called on scope / function exit) */
void epl_gc_root_pop(int32_t n) {
    gc_lock();
    gc_root_top -= n;
    if (gc_root_top < 0) gc_root_top = 0;
    gc_unlock();
}

/* Reset root stack to a saved depth (safer scope-based cleanup) */
void epl_gc_root_pop_to(int32_t depth) {
    gc_lock();
    if (depth >= 0 && depth <= gc_root_top) {
        gc_root_top = depth;
    }
    gc_unlock();
}

/* Get current root stack depth (for save/restore pattern) */
int32_t epl_gc_root_depth(void) {
    gc_lock();
    int32_t d = gc_root_top;
    gc_unlock();
    return d;
}

/* ── Forward declarations for mark helpers ── */
static void gc_mark_object(void *ptr, int8_t tag);

/* ── Allocator ── */
static EPLGCHeader* epl_gc_header(void *ptr) {
    return ((EPLGCHeader*)ptr) - 1;
}

void* epl_gc_alloc(size_t size, int8_t tag) {
    gc_lock();
    EPLGCHeader *hdr = (EPLGCHeader*)malloc(sizeof(EPLGCHeader) + size);
    if (!hdr) { gc_unlock(); fprintf(stderr, "EPL GC: out of memory\n"); exit(1); }
    hdr->marked  = 0;
    hdr->tag     = tag;
    hdr->gc_next = gc_all_objects;
    gc_all_objects = hdr;
    gc_object_count++;
    gc_unlock();
    return (void*)(hdr + 1);   /* user pointer past header */
}

/* ── Mark phase ── */

/* Mark a single GC-managed pointer as live (+ recurse into children) */
static void gc_mark(void *ptr) {
    if (!ptr) return;
    EPLGCHeader *hdr = epl_gc_header(ptr);
    if (hdr->marked) return;        /* already visited */
    hdr->marked = 1;
    gc_mark_object(ptr, hdr->tag);  /* recurse into children */
}

/* Recursively mark children of a container */
static void gc_mark_object(void *ptr, int8_t tag) {
    switch (tag) {
        case TAG_LIST: {
            EPLList *l = (EPLList*)ptr;
            for (int i = 0; i < l->count; i++) {
                if (l->tags[i] == TAG_LIST || l->tags[i] == TAG_MAP ||
                    l->tags[i] == TAG_OBJECT || l->tags[i] == TAG_STRING) {
                    void *child = (void*)(intptr_t)l->data[i];
                    if (child) gc_mark(child);
                }
            }
            break;
        }
        case TAG_MAP: {
            EPLMap *m = (EPLMap*)ptr;
            for (int i = 0; i < m->bucket_count; i++) {
                EPLMapEntry *e = m->buckets[i];
                while (e) {
                    if (e->tag == TAG_LIST || e->tag == TAG_MAP ||
                        e->tag == TAG_OBJECT || e->tag == TAG_STRING) {
                        void *child = (void*)(intptr_t)e->data;
                        if (child) gc_mark(child);
                    }
                    e = e->next;
                }
            }
            break;
        }
        case TAG_OBJECT: {
            EPLObject *o = (EPLObject*)ptr;
            for (int i = 0; i < o->prop_count; i++) {
                if (o->prop_tags[i] == TAG_LIST || o->prop_tags[i] == TAG_MAP ||
                    o->prop_tags[i] == TAG_OBJECT || o->prop_tags[i] == TAG_STRING) {
                    void *child = (void*)(intptr_t)o->prop_data[i];
                    if (child) gc_mark(child);
                }
            }
            break;
        }
        case TAG_STRING:
            /* leaf; no children */
            break;
    }
}

/* ── Sweep phase ── */
static void gc_sweep(void) {
    EPLGCHeader **pp = &gc_all_objects;
    while (*pp) {
        EPLGCHeader *hdr = *pp;
        if (!hdr->marked) {
            /* Dead object – unlink and destroy */
            *pp = hdr->gc_next;
            gc_object_count--;
            void *ptr = (void*)(hdr + 1);
            switch (hdr->tag) {
                case TAG_STRING: /* string data follows header inline */ break;
                case TAG_LIST:   gc_cleanup_list((EPLList*)ptr);     break;
                case TAG_MAP:    gc_cleanup_map((EPLMap*)ptr);       break;
                case TAG_OBJECT: gc_cleanup_object((EPLObject*)ptr); break;
            }
            free(hdr);   /* frees header + embedded struct in one block */
        } else {
            hdr->marked = 0;   /* reset for next cycle */
            pp = &hdr->gc_next;
        }
    }
}

/* ── Public API ── */

void epl_gc_collect(void) {
    gc_lock();
    gc_root_stack_init();
    /* Phase 1: Mark from shadow-stack roots */
    for (int i = 0; i < gc_root_top; i++) {
        void *root = gc_root_stack[i];
        if (root) gc_mark(root);
    }
    /* Phase 2: Sweep unmarked */
    gc_sweep();
    gc_unlock();
}

void epl_gc_collect_if_needed(void) {
    gc_lock();
    if (gc_object_count >= gc_threshold) {
        gc_root_stack_init();
        /* Mark */
        for (int i = 0; i < gc_root_top; i++) {
            void *root = gc_root_stack[i];
            if (root) gc_mark(root);
        }
        /* Sweep */
        gc_sweep();
        /* Dynamic threshold: grow if many objects survive, keep floor of 256 */
        if (gc_object_count > gc_threshold / 2) {
            gc_threshold = gc_object_count * 2;
        }
        if (gc_threshold < 256) gc_threshold = 256;
    }
    gc_unlock();
}

int epl_gc_object_count(void) {
    return gc_object_count;
}

void epl_gc_shutdown(void) {
    gc_lock();
    /* Free ALL tracked objects regardless of mark state */
    EPLGCHeader *hdr = gc_all_objects;
    while (hdr) {
        EPLGCHeader *next = hdr->gc_next;
        void *ptr = (void*)(hdr + 1);
        switch (hdr->tag) {
            case TAG_STRING: break;
            case TAG_LIST:   gc_cleanup_list((EPLList*)ptr);     break;
            case TAG_MAP:    gc_cleanup_map((EPLMap*)ptr);       break;
            case TAG_OBJECT: gc_cleanup_object((EPLObject*)ptr); break;
        }
        free(hdr);   /* frees header + embedded struct in one block */
        hdr = next;
    }
    gc_all_objects = NULL;
    gc_object_count = 0;
    gc_root_top = 0;
    /* Free dynamic root stack */
    if (gc_root_stack) { free(gc_root_stack); gc_root_stack = NULL; gc_root_capacity = 0; }
    gc_unlock();

    /* Also reset arena */
    epl_arena_reset();
}

/* Legacy ref-count API — now thin wrappers for backward compat */
void epl_gc_retain(void *ptr) {
    /* With mark-and-sweep, retain is a no-op;
       liveness is determined by reachability from roots. */
    (void)ptr;
}

void epl_gc_release(void *ptr) {
    /* With mark-and-sweep, release is a no-op. */
    (void)ptr;
}

/* ── GC-aware allocation wrappers for collections ── */

EPLList* epl_gc_new_list(void) {
    EPLList *l = (EPLList*)epl_gc_alloc(sizeof(EPLList), TAG_LIST);
    l->capacity = 16;
    l->count = 0;
    l->tags = (int32_t*)malloc(sizeof(int32_t) * l->capacity);
    l->data = (int64_t*)malloc(sizeof(int64_t) * l->capacity);
    if (!l->tags || !l->data) { fprintf(stderr, "EPL: list alloc out of memory\n"); exit(1); }
    return l;
}

EPLMap* epl_gc_new_map(void) {
    EPLMap *m = (EPLMap*)epl_gc_alloc(sizeof(EPLMap), TAG_MAP);
    m->bucket_count = MAP_INITIAL_BUCKETS;
    m->entry_count = 0;
    m->buckets = (EPLMapEntry**)calloc(m->bucket_count, sizeof(EPLMapEntry*));
    if (!m->buckets) { fprintf(stderr, "EPL: map alloc out of memory\n"); exit(1); }
    return m;
}

EPLObject* epl_gc_new_object(const char *class_name) {
    EPLObject *o = (EPLObject*)epl_gc_alloc(sizeof(EPLObject), TAG_OBJECT);
    memset(o, 0, sizeof(EPLObject));
    o->class_name = strdup(class_name);
    o->prop_capacity = OBJ_INITIAL_PROPS;
    o->prop_count = 0;
    o->prop_names = (char**)calloc(o->prop_capacity, sizeof(char*));
    o->prop_tags  = (int32_t*)calloc(o->prop_capacity, sizeof(int32_t));
    o->prop_data  = (int64_t*)calloc(o->prop_capacity, sizeof(int64_t));
    if (!o->prop_names || !o->prop_tags || !o->prop_data) {
        fprintf(stderr, "EPL: object alloc out of memory\n"); exit(1);
    }
    return o;
}

char* epl_gc_new_string(const char *src) {
    if (!src) return NULL;
    size_t len = strlen(src);
    char *s = (char*)epl_gc_alloc(len + 1, TAG_STRING);
    memcpy(s, src, len + 1);
    return s;
}

char* epl_gc_str_concat(const char *a, const char *b) {
    if (!a) a = "";
    if (!b) b = "";
    size_t la = strlen(a), lb = strlen(b);
    char *s = (char*)epl_gc_alloc(la + lb + 1, TAG_STRING);
    memcpy(s, a, la);
    memcpy(s + la, b, lb + 1);
    return s;
}

/* ════════════════════════════════════════════════════
 * List Operations
 * ═══════════════════════════════════════════════════ */
EPLList* epl_list_new(void) {
    EPLList *l = (EPLList*)malloc(sizeof(EPLList));
    if (!l) { fprintf(stderr, "EPL: list alloc out of memory\n"); exit(1); }
    l->capacity = 16;
    l->count = 0;
    l->tags = (int32_t*)malloc(sizeof(int32_t) * l->capacity);
    l->data = (int64_t*)malloc(sizeof(int64_t) * l->capacity);
    if (!l->tags || !l->data) { fprintf(stderr, "EPL: list alloc out of memory\n"); exit(1); }
    return l;
}

void epl_list_push_raw(EPLList *l, int32_t tag, int64_t data) {
    if (l->count >= l->capacity) {
        l->capacity *= 2;
        int32_t *new_tags = (int32_t*)realloc(l->tags, sizeof(int32_t) * l->capacity);
        int64_t *new_data = (int64_t*)realloc(l->data, sizeof(int64_t) * l->capacity);
        if (!new_tags || !new_data) { fprintf(stderr, "EPL: list push out of memory\n"); exit(1); }
        l->tags = new_tags;
        l->data = new_data;
    }
    l->tags[l->count] = tag;
    l->data[l->count] = data;
    l->count++;
}

int64_t epl_list_get_int(EPLList *l, int64_t idx) {
    if (idx < 0 || idx >= l->count) return 0;
    return l->data[idx];
}

int32_t epl_list_get_tag(EPLList *l, int64_t idx) {
    if (idx < 0 || idx >= l->count) return TAG_NONE;
    return l->tags[idx];
}

char* epl_list_get_str(EPLList *l, int64_t idx) {
    if (idx < 0 || idx >= l->count) return "";
    if (l->tags[idx] == TAG_STRING) return (char*)(l->data[idx]);
    return "";
}

void epl_list_set_int(EPLList *l, int64_t idx, int64_t val) {
    if (idx >= 0 && idx < l->count) {
        l->data[idx] = val;
    }
}

int32_t epl_list_length(EPLList *l) {
    return l ? l->count : 0;
}

void epl_list_remove_raw(EPLList *l, int64_t idx) {
    if (idx < 0 || idx >= l->count) return;
    for (int i = (int)idx; i < l->count - 1; i++) {
        l->tags[i] = l->tags[i + 1];
        l->data[i] = l->data[i + 1];
    }
    l->count--;
}

int32_t epl_list_contains_int(EPLList *l, int64_t val) {
    for (int i = 0; i < l->count; i++) {
        if (l->data[i] == val) return 1;
    }
    return 0;
}

EPLList* epl_list_slice(EPLList *l, int64_t start, int64_t end, int64_t step) {
    EPLList *r = epl_list_new();
    if (step == 0) step = 1;
    if (start < 0) start = 0;
    if (end > l->count) end = l->count;
    if (step > 0) {
        for (int64_t i = start; i < end; i += step) {
            epl_list_push_raw(r, l->tags[i], l->data[i]);
        }
    } else {
        /* Negative step: iterate backward */
        if (start >= l->count) start = l->count - 1;
        if (end < -1) end = -1;
        for (int64_t i = start; i > end; i += step) {
            if (i >= 0 && i < l->count)
                epl_list_push_raw(r, l->tags[i], l->data[i]);
        }
    }
    return r;
}

void epl_list_print(EPLList *l) {
    printf("[");
    for (int i = 0; i < l->count; i++) {
        if (i > 0) printf(", ");
        switch (l->tags[i]) {
            case TAG_INT:    printf("%lld", (long long)l->data[i]); break;
            case TAG_FLOAT:  { double d; memcpy(&d, &l->data[i], sizeof(double)); printf("%g", d); break; }
            case TAG_BOOL:   printf(l->data[i] ? "true" : "false"); break;
            case TAG_STRING: printf("\"%s\"", (char*)l->data[i]); break;
            case TAG_NONE:   printf("nothing"); break;
            default:         printf("?"); break;
        }
    }
    printf("]\n");
}

/* ════════════════════════════════════════════════════
 * Map Operations
 * ═══════════════════════════════════════════════════ */
static unsigned int map_hash_raw(const char *key) {
    if (!key) return 0;
    unsigned int h = 5381;
    while (*key) h = ((h << 5) + h) + (unsigned char)*key++;
    return h;
}

static unsigned int map_hash(const char *key, int bucket_count) {
    return map_hash_raw(key) % (unsigned int)bucket_count;
}

EPLMap* epl_map_new(void) {
    EPLMap *m = (EPLMap*)calloc(1, sizeof(EPLMap));
    m->bucket_count = MAP_INITIAL_BUCKETS;
    m->entry_count = 0;
    m->buckets = (EPLMapEntry**)calloc(m->bucket_count, sizeof(EPLMapEntry*));
    return m;
}

static EPLMapEntry* map_find(EPLMap *m, const char *key) {
    unsigned int h = map_hash(key, m->bucket_count);
    EPLMapEntry *e = m->buckets[h];
    while (e) { if (strcmp(e->key, key) == 0) return e; e = e->next; }
    return NULL;
}

/* Resize the hash map when load factor exceeded */
static void map_resize(EPLMap *m) {
    int new_count = m->bucket_count * 2;
    EPLMapEntry **new_buckets = (EPLMapEntry**)calloc(new_count, sizeof(EPLMapEntry*));
    if (!new_buckets) return;  /* silently keep old size on OOM */
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            EPLMapEntry *next = e->next;
            unsigned int h = map_hash_raw(e->key) % (unsigned int)new_count;
            e->next = new_buckets[h];
            new_buckets[h] = e;
            e = next;
        }
    }
    free(m->buckets);
    m->buckets = new_buckets;
    m->bucket_count = new_count;
}

static EPLMapEntry* map_insert(EPLMap *m, const char *key) {
    EPLMapEntry *e = map_find(m, key);
    if (e) return e;
    /* Check load factor and resize if needed */
    if (m->entry_count * MAP_LOAD_FACTOR_DEN > m->bucket_count * MAP_LOAD_FACTOR_NUM) {
        map_resize(m);
    }
    unsigned int h = map_hash(key, m->bucket_count);
    e = (EPLMapEntry*)malloc(sizeof(EPLMapEntry));
    e->key = strdup(key);
    e->tag = TAG_NONE;
    e->data = 0;
    e->next = m->buckets[h];
    m->buckets[h] = e;
    m->entry_count++;
    return e;
}

void epl_map_set_int(EPLMap *m, const char *key, int64_t val) {
    EPLMapEntry *e = map_insert(m, key);
    e->tag = TAG_INT;
    e->data = val;
}

void epl_map_set_str(EPLMap *m, const char *key, const char *val) {
    EPLMapEntry *e = map_insert(m, key);
    /* Free old string value if overwriting */
    if (e->tag == TAG_STRING && e->data) free((char*)(intptr_t)e->data);
    e->tag = TAG_STRING;
    e->data = (int64_t)(intptr_t)strdup(val);
}

int64_t epl_map_get_int(EPLMap *m, const char *key) {
    EPLMapEntry *e = map_find(m, key);
    return e ? e->data : 0;
}

char* epl_map_get_str(EPLMap *m, const char *key) {
    EPLMapEntry *e = map_find(m, key);
    if (e && e->tag == TAG_STRING) return (char*)(intptr_t)e->data;
    return "";
}

/* ════════════════════════════════════════════════════
 * Object Operations
 * ═══════════════════════════════════════════════════ */
EPLObject* epl_object_new(const char *class_name) {
    EPLObject *o = (EPLObject*)calloc(1, sizeof(EPLObject));
    o->class_name = strdup(class_name);
    o->prop_count = 0;
    o->prop_capacity = OBJ_INITIAL_PROPS;
    o->prop_names = (char**)calloc(o->prop_capacity, sizeof(char*));
    o->prop_tags  = (int32_t*)calloc(o->prop_capacity, sizeof(int32_t));
    o->prop_data  = (int64_t*)calloc(o->prop_capacity, sizeof(int64_t));
    return o;
}

static int obj_find_prop(EPLObject *o, const char *name) {
    for (int i = 0; i < o->prop_count; i++)
        if (strcmp(o->prop_names[i], name) == 0) return i;
    return -1;
}

static void obj_grow(EPLObject *o) {
    o->prop_capacity *= 2;
    o->prop_names = (char**)realloc(o->prop_names, sizeof(char*) * o->prop_capacity);
    o->prop_tags  = (int32_t*)realloc(o->prop_tags,  sizeof(int32_t) * o->prop_capacity);
    o->prop_data  = (int64_t*)realloc(o->prop_data,  sizeof(int64_t) * o->prop_capacity);
    if (!o->prop_names || !o->prop_tags || !o->prop_data) {
        fprintf(stderr, "EPL: Object property grow out of memory\n"); exit(1);
    }
}

void epl_object_set_int(EPLObject *o, const char *name, int64_t val) {
    int i = obj_find_prop(o, name);
    if (i < 0) {
        if (o->prop_count >= o->prop_capacity) obj_grow(o);
        i = o->prop_count++;
        o->prop_names[i] = strdup(name);
    }
    o->prop_tags[i] = TAG_INT;
    o->prop_data[i] = val;
}

void epl_object_set_str(EPLObject *o, const char *name, const char *val) {
    int i = obj_find_prop(o, name);
    if (i < 0) {
        if (o->prop_count >= o->prop_capacity) obj_grow(o);
        i = o->prop_count++;
        o->prop_names[i] = strdup(name);
    } else {
        /* Free old string value if overwriting */
        if (o->prop_tags[i] == TAG_STRING && o->prop_data[i])
            free((char*)(intptr_t)o->prop_data[i]);
    }
    o->prop_tags[i] = TAG_STRING;
    o->prop_data[i] = (int64_t)(intptr_t)strdup(val);
}

int64_t epl_object_get_int(EPLObject *o, const char *name) {
    int i = obj_find_prop(o, name);
    return (i >= 0) ? o->prop_data[i] : 0;
}

char* epl_object_get_str(EPLObject *o, const char *name) {
    int i = obj_find_prop(o, name);
    if (i >= 0 && o->prop_tags[i] == TAG_STRING) return (char*)(intptr_t)o->prop_data[i];
    return "";
}

/* ════════════════════════════════════════════════════
 * String Operations
 * ═══════════════════════════════════════════════════ */
int64_t epl_string_length(const char *s) {
    return s ? (int64_t)strlen(s) : 0;
}

char* epl_string_index(const char *s, int64_t idx) {
    if (!s) return strdup("");
    int64_t len = (int64_t)strlen(s);
    if (idx < 0 || idx >= len) { char *r = (char*)malloc(1); r[0] = '\0'; return r; }
    char *r = (char*)malloc(2);
    r[0] = s[idx]; r[1] = '\0';
    return r;
}

char* epl_string_upper(const char *s) {
    if (!s) return strdup("");
    int64_t len = (int64_t)strlen(s);
    char *r = (char*)malloc(len + 1);
    for (int64_t i = 0; i < len; i++) r[i] = (char)toupper((unsigned char)s[i]);
    r[len] = '\0';
    return r;
}

char* epl_string_lower(const char *s) {
    if (!s) return strdup("");
    int64_t len = (int64_t)strlen(s);
    char *r = (char*)malloc(len + 1);
    for (int64_t i = 0; i < len; i++) r[i] = (char)tolower((unsigned char)s[i]);
    r[len] = '\0';
    return r;
}

int32_t epl_string_contains(const char *haystack, const char *needle) {
    if (!haystack || !needle) return 0;
    return strstr(haystack, needle) != NULL ? 1 : 0;
}

char* epl_string_substring(const char *s, int64_t start, int64_t end) {
    int64_t len = (int64_t)strlen(s);
    if (start < 0) start = 0;
    if (end > len) end = len;
    if (start >= end) { char *r = (char*)malloc(1); r[0] = '\0'; return r; }
    int64_t sub_len = end - start;
    char *r = (char*)malloc(sub_len + 1);
    memcpy(r, s + start, sub_len);
    r[sub_len] = '\0';
    return r;
}

char* epl_string_replace(const char *s, const char *old_s, const char *new_s) {
    if (!s || !old_s || !new_s) return strdup(s ? s : "");
    size_t old_len = strlen(old_s);
    size_t new_len = strlen(new_s);
    if (old_len == 0) return strdup(s);
    /* Count occurrences */
    int count = 0;
    const char *p = s;
    while ((p = strstr(p, old_s)) != NULL) { count++; p += old_len; }
    size_t slen = strlen(s);
    size_t result_len;
    if (new_len >= old_len) {
        result_len = slen + (size_t)count * (new_len - old_len);
    } else {
        size_t shrink = (size_t)count * (old_len - new_len);
        result_len = (shrink > slen) ? 0 : slen - shrink;
    }
    char *r = (char*)malloc(result_len + 1);
    if (!r) return strdup("");
    char *wp = r;
    p = s;
    while (*p) {
        if (strncmp(p, old_s, old_len) == 0) {
            memcpy(wp, new_s, new_len);
            wp += new_len;
            p += old_len;
        } else {
            *wp++ = *p++;
        }
    }
    *wp = '\0';
    return r;
}

char* epl_string_trim(const char *s) {
    if (!s) return strdup("");
    while (*s && isspace((unsigned char)*s)) s++;
    size_t len = strlen(s);
    while (len > 0 && isspace((unsigned char)s[len - 1])) len--;
    char *r = (char*)malloc(len + 1);
    memcpy(r, s, len);
    r[len] = '\0';
    return r;
}

int32_t epl_string_starts_with(const char *s, const char *prefix) {
    if (!s || !prefix) return 0;
    return strncmp(s, prefix, strlen(prefix)) == 0 ? 1 : 0;
}

int32_t epl_string_ends_with(const char *s, const char *suffix) {
    if (!s || !suffix) return 0;
    size_t slen = strlen(s);
    size_t plen = strlen(suffix);
    if (plen > slen) return 0;
    return strcmp(s + slen - plen, suffix) == 0 ? 1 : 0;
}

EPLList* epl_string_split(const char *s, const char *delim) {
    EPLList *list = epl_list_new();
    if (!s || !delim || strlen(delim) == 0) {
        epl_list_push_raw(list, TAG_STRING, (int64_t)(intptr_t)strdup(s ? s : ""));
        return list;
    }
    char *copy = strdup(s);
    size_t dlen = strlen(delim);
    char *p = copy;
    while (1) {
        char *found = strstr(p, delim);
        if (!found) {
            epl_list_push_raw(list, TAG_STRING, (int64_t)(intptr_t)strdup(p));
            break;
        }
        *found = '\0';
        epl_list_push_raw(list, TAG_STRING, (int64_t)(intptr_t)strdup(p));
        p = found + dlen;
    }
    free(copy);
    return list;
}

char* epl_string_reverse(const char *s) {
    if (!s) return strdup("");
    size_t len = strlen(s);
    char *r = (char*)malloc(len + 1);
    for (size_t i = 0; i < len; i++) r[i] = s[len - 1 - i];
    r[len] = '\0';
    return r;
}

/* ════════════════════════════════════════════════════
 * Conversion Helpers
 * ═══════════════════════════════════════════════════ */
char* epl_int_to_string(int64_t val) {
    char *buf = (char*)malloc(32);
    snprintf(buf, 32, "%lld", (long long)val);
    return buf;
}

char* epl_float_to_string(double val) {
    char *buf = (char*)malloc(64);
    snprintf(buf, 64, "%g", val);
    return buf;
}

int64_t epl_string_to_int(const char *s) {
    return s ? atoll(s) : 0;
}

double epl_string_to_float(const char *s) {
    return s ? atof(s) : 0.0;
}

/* ════════════════════════════════════════════════════
 * Math Functions
 * ═══════════════════════════════════════════════════ */
double epl_power(double base, double exp) { return pow(base, exp); }
double epl_floor(double x) { return floor(x); }
double epl_ceil(double x)  { return ceil(x); }
double epl_sqrt(double x)  { return sqrt(x); }
double epl_log(double x)   { return log(x); }
double epl_sin(double x)   { return sin(x); }
double epl_cos(double x)   { return cos(x); }
double epl_fabs(double x)  { return fabs(x); }

/* ════════════════════════════════════════════════════
 * Input / Output
 * ═══════════════════════════════════════════════════ */
char* epl_input(const char *prompt) {
    if (prompt && *prompt) printf("%s", prompt);
    fflush(stdout);
    /* Dynamic input: start with 256 bytes, grow as needed */
    size_t capacity = 256;
    size_t len = 0;
    char *buf = (char*)malloc(capacity);
    if (!buf) { return strdup(""); }
    int c;
    while ((c = fgetc(stdin)) != EOF && c != '\n') {
        if (len + 1 >= capacity) {
            capacity *= 2;
            char *tmp = (char*)realloc(buf, capacity);
            if (!tmp) { buf[len] = '\0'; return buf; }
            buf = tmp;
        }
        buf[len++] = (char)c;
    }
    buf[len] = '\0';
    return buf;
}

char* epl_input_no_prompt(void) {
    return epl_input("");
}

/* ════════════════════════════════════════════════════
 * File I/O 
 * ═══════════════════════════════════════════════════ */
char* epl_file_read(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return strdup("");
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    if (sz < 0) { fclose(f); return strdup(""); }
    fseek(f, 0, SEEK_SET);
    char *buf = (char*)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); return strdup(""); }
    size_t read = fread(buf, 1, (size_t)sz, f);
    buf[read] = '\0';
    fclose(f);
    return buf;
}

int32_t epl_file_write(const char *path, const char *content) {
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    size_t len = strlen(content);
    size_t written = fwrite(content, 1, len, f);
    fclose(f);
    return written == len ? 1 : 0;
}

int32_t epl_file_append(const char *path, const char *content) {
    FILE *f = fopen(path, "ab");
    if (!f) return 0;
    size_t len = strlen(content);
    size_t written = fwrite(content, 1, len, f);
    fclose(f);
    return written == len ? 1 : 0;
}

int32_t epl_file_exists(const char *path) {
    FILE *f = fopen(path, "r");
    if (f) { fclose(f); return 1; }
    return 0;
}

int32_t epl_file_delete(const char *path) {
    return remove(path) == 0 ? 1 : 0;
}

/* ════════════════════════════════════════════════════
 * Environment Variables
 * ═══════════════════════════════════════════════════ */
char* epl_env_get(const char *name) {
    const char *val = getenv(name);
    return strdup(val ? val : "");
}

/* ════════════════════════════════════════════════════
 * Random Number Generation (xorshift64* — production quality)
 * Features: rejection sampling (no modulo bias), strong seeding,
 * thread-safe via platform mutex, user-accessible seed function.
 * ═══════════════════════════════════════════════════ */
static uint64_t epl_rng_state = 0;
static int epl_rand_seeded = 0;

#ifdef _WIN32
static CRITICAL_SECTION rng_mutex;
static int rng_mutex_init = 0;
static void rng_lock(void)   { if (!rng_mutex_init) { InitializeCriticalSection(&rng_mutex); rng_mutex_init = 1; } EnterCriticalSection(&rng_mutex); }
static void rng_unlock(void) { LeaveCriticalSection(&rng_mutex); }
#else
static pthread_mutex_t rng_mutex = PTHREAD_MUTEX_INITIALIZER;
static void rng_lock(void)   { pthread_mutex_lock(&rng_mutex); }
static void rng_unlock(void) { pthread_mutex_unlock(&rng_mutex); }
#endif

static void epl_rng_auto_seed(void) {
    /* Seed from multiple entropy sources for better randomness */
    uint64_t seed = 0;
#ifdef _WIN32
    LARGE_INTEGER pc;
    QueryPerformanceCounter(&pc);
    seed = (uint64_t)pc.QuadPart;
    seed ^= (uint64_t)GetCurrentProcessId() * 6364136223846793005ULL;
    seed ^= (uint64_t)GetTickCount64() << 17;
#else
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) == 0) {
        seed = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
    } else {
        seed = (uint64_t)time(NULL);
    }
    seed ^= (uint64_t)getpid() * 6364136223846793005ULL;
#endif
    seed ^= (uint64_t)(uintptr_t)&epl_rng_state;
    if (seed == 0) seed = 1;
    epl_rng_state = seed;
    epl_rand_seeded = 1;
}

void epl_random_seed(int64_t user_seed) {
    /* User-accessible deterministic seeding for reproducibility */
    rng_lock();
    epl_rng_state = (uint64_t)user_seed;
    if (epl_rng_state == 0) epl_rng_state = 1;
    epl_rand_seeded = 1;
    rng_unlock();
}

static uint64_t epl_rng_next(void) {
    if (!epl_rand_seeded) epl_rng_auto_seed();
    uint64_t x = epl_rng_state;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    epl_rng_state = x;
    return x * 0x2545F4914F6CDD1DULL;
}

int64_t epl_random_int(int64_t min_val, int64_t max_val) {
    if (min_val >= max_val) return min_val;
    rng_lock();
    uint64_t range = (uint64_t)(max_val - min_val + 1);
    /* Rejection sampling to eliminate modulo bias */
    uint64_t limit = UINT64_MAX - (UINT64_MAX % range);
    uint64_t r;
    do {
        r = epl_rng_next();
    } while (r >= limit);
    int64_t result = min_val + (int64_t)(r % range);
    rng_unlock();
    return result;
}

double epl_random_float(void) {
    rng_lock();
    double result = (double)(epl_rng_next() >> 11) / (double)(1ULL << 53);
    rng_unlock();
    return result;
}

/* ════════════════════════════════════════════════════
 * Time Functions
 * ═══════════════════════════════════════════════════ */
double epl_time_now(void) {
    return (double)time(NULL);
}

int64_t epl_time_ms(void) {
    /* Milliseconds since epoch (approximate via clock) */
    return (int64_t)time(NULL) * 1000LL;
}

void epl_sleep_ms(int64_t ms) {
#ifdef _WIN32
    Sleep((DWORD)ms);
#else
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
#endif
}

/* ════════════════════════════════════════════════════
 * List Sort (introsort — quicksort with fallback to insertion sort)
 * ═══════════════════════════════════════════════════ */
static void list_swap(EPLList *l, int i, int j) {
    int32_t tmp_tag = l->tags[i]; l->tags[i] = l->tags[j]; l->tags[j] = tmp_tag;
    int64_t tmp_data = l->data[i]; l->data[i] = l->data[j]; l->data[j] = tmp_data;
}

static void list_insertion_sort(EPLList *l, int lo, int hi) {
    for (int i = lo + 1; i <= hi; i++) {
        int32_t key_tag = l->tags[i];
        int64_t key_data = l->data[i];
        int j = i - 1;
        while (j >= lo && l->data[j] > key_data) {
            l->tags[j + 1] = l->tags[j];
            l->data[j + 1] = l->data[j];
            j--;
        }
        l->tags[j + 1] = key_tag;
        l->data[j + 1] = key_data;
    }
}

static int list_partition(EPLList *l, int lo, int hi) {
    /* Median-of-three pivot selection */
    int mid = lo + (hi - lo) / 2;
    if (l->data[lo] > l->data[mid]) list_swap(l, lo, mid);
    if (l->data[lo] > l->data[hi])  list_swap(l, lo, hi);
    if (l->data[mid] > l->data[hi]) list_swap(l, mid, hi);
    list_swap(l, mid, hi - 1);  /* pivot at hi-1 */
    int64_t pivot = l->data[hi - 1];
    int i = lo, j = hi - 1;
    while (1) {
        while (l->data[++i] < pivot);
        while (l->data[--j] > pivot);
        if (i >= j) break;
        list_swap(l, i, j);
    }
    list_swap(l, i, hi - 1);
    return i;
}

static void list_introsort_impl(EPLList *l, int lo, int hi, int depth_limit) {
    if (hi - lo < 16) {
        list_insertion_sort(l, lo, hi);
        return;
    }
    if (depth_limit == 0) {
        /* Fallback: insertion sort for remaining partition (heap sort would be ideal,
           but insertion on small partitions after quicksort is acceptable) */
        list_insertion_sort(l, lo, hi);
        return;
    }
    int p = list_partition(l, lo, hi);
    list_introsort_impl(l, lo, p - 1, depth_limit - 1);
    list_introsort_impl(l, p + 1, hi, depth_limit - 1);
}

static int log2_int(int n) {
    int r = 0;
    while (n > 1) { n >>= 1; r++; }
    return r;
}

EPLList* epl_list_sorted(EPLList *l) {
    EPLList *r = epl_list_new();
    for (int i = 0; i < l->count; i++) {
        epl_list_push_raw(r, l->tags[i], l->data[i]);
    }
    if (r->count > 1) {
        int depth_limit = 2 * log2_int(r->count);
        list_introsort_impl(r, 0, r->count - 1, depth_limit);
    }
    return r;
}

EPLList* epl_list_reversed(EPLList *l) {
    EPLList *r = epl_list_new();
    for (int i = l->count - 1; i >= 0; i--) {
        epl_list_push_raw(r, l->tags[i], l->data[i]);
    }
    return r;
}

int64_t epl_list_sum(EPLList *l) {
    int64_t total = 0;
    for (int i = 0; i < l->count; i++) {
        if (l->tags[i] == TAG_INT) total += l->data[i];
        else if (l->tags[i] == TAG_FLOAT) {
            double d;
            memcpy(&d, &l->data[i], sizeof(double));
            total += (int64_t)d;
        }
    }
    return total;
}

int64_t epl_list_index_of(EPLList *l, int64_t val) {
    for (int i = 0; i < l->count; i++) {
        if (l->data[i] == val) return i;
    }
    return -1;
}

EPLList* epl_list_concat(EPLList *a, EPLList *b) {
    EPLList *r = epl_list_new();
    for (int i = 0; i < a->count; i++)
        epl_list_push_raw(r, a->tags[i], a->data[i]);
    for (int i = 0; i < b->count; i++)
        epl_list_push_raw(r, b->tags[i], b->data[i]);
    return r;
}

/* ════════════════════════════════════════════════════
 * Map Extended Operations
 * ═══════════════════════════════════════════════════ */
int32_t epl_map_has_key(EPLMap *m, const char *key) {
    return map_find(m, key) != NULL ? 1 : 0;
}

void epl_map_remove(EPLMap *m, const char *key) {
    unsigned int h = map_hash(key, m->bucket_count);
    EPLMapEntry **pp = &m->buckets[h];
    while (*pp) {
        if (strcmp((*pp)->key, key) == 0) {
            EPLMapEntry *doomed = *pp;
            *pp = doomed->next;
            if (doomed->key) free(doomed->key);
            if (doomed->tag == TAG_STRING && doomed->data)
                free((char*)(intptr_t)doomed->data);
            free(doomed);
            m->entry_count--;
            return;
        }
        pp = &(*pp)->next;
    }
}

EPLList* epl_map_keys(EPLMap *m) {
    EPLList *keys = epl_list_new();
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            epl_list_push_raw(keys, TAG_STRING, (int64_t)(intptr_t)strdup(e->key));
            e = e->next;
        }
    }
    return keys;
}

EPLList* epl_map_values(EPLMap *m) {
    EPLList *vals = epl_list_new();
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            epl_list_push_raw(vals, e->tag, e->data);
            e = e->next;
        }
    }
    return vals;
}

int32_t epl_map_size(EPLMap *m) {
    return m ? m->entry_count : 0;
}

/* ════════════════════════════════════════════════════
 * String Builder (for efficient concatenation)
 * ═══════════════════════════════════════════════════ */
typedef struct {
    char *data;
    size_t len;
    size_t capacity;
} EPLStringBuilder;

EPLStringBuilder* epl_sb_new(void) {
    EPLStringBuilder *sb = (EPLStringBuilder*)malloc(sizeof(EPLStringBuilder));
    sb->capacity = 256;
    sb->data = (char*)malloc(sb->capacity);
    sb->data[0] = '\0';
    sb->len = 0;
    return sb;
}

void epl_sb_append(EPLStringBuilder *sb, const char *s) {
    size_t slen = strlen(s);
    while (sb->len + slen + 1 > sb->capacity) {
        sb->capacity *= 2;
        sb->data = (char*)realloc(sb->data, sb->capacity);
    }
    memcpy(sb->data + sb->len, s, slen);
    sb->len += slen;
    sb->data[sb->len] = '\0';
}

char* epl_sb_build(EPLStringBuilder *sb) {
    char *result = strdup(sb->data);
    free(sb->data);
    free(sb);
    return result;
}

/* ════════════════════════════════════════════════════
 * Simple JSON Serialization
 * ═══════════════════════════════════════════════════ */
char* epl_json_serialize_list(EPLList *l) {
    EPLStringBuilder *sb = epl_sb_new();
    epl_sb_append(sb, "[");
    for (int i = 0; i < l->count; i++) {
        if (i > 0) epl_sb_append(sb, ", ");
        char buf[64];
        switch (l->tags[i]) {
            case TAG_INT:
                snprintf(buf, sizeof(buf), "%lld", (long long)l->data[i]);
                epl_sb_append(sb, buf);
                break;
            case TAG_FLOAT: {
                double d;
                memcpy(&d, &l->data[i], sizeof(double));
                snprintf(buf, sizeof(buf), "%g", d);
                epl_sb_append(sb, buf);
                break;
            }
            case TAG_BOOL:
                epl_sb_append(sb, l->data[i] ? "true" : "false");
                break;
            case TAG_STRING:
                epl_sb_append(sb, "\"");
                epl_sb_append(sb, (char*)(intptr_t)l->data[i]);
                epl_sb_append(sb, "\"");
                break;
            case TAG_NONE:
                epl_sb_append(sb, "null");
                break;
            default:
                epl_sb_append(sb, "null");
                break;
        }
    }
    epl_sb_append(sb, "]");
    return epl_sb_build(sb);
}

char* epl_json_serialize_map(EPLMap *m) {
    EPLStringBuilder *sb = epl_sb_new();
    epl_sb_append(sb, "{");
    int first = 1;
    for (int i = 0; i < m->bucket_count; i++) {
        EPLMapEntry *e = m->buckets[i];
        while (e) {
            if (!first) epl_sb_append(sb, ", ");
            first = 0;
            epl_sb_append(sb, "\"");
            epl_sb_append(sb, e->key);
            epl_sb_append(sb, "\": ");
            char buf[64];
            switch (e->tag) {
                case TAG_INT:
                    snprintf(buf, sizeof(buf), "%lld", (long long)e->data);
                    epl_sb_append(sb, buf);
                    break;
                case TAG_FLOAT: {
                    double d;
                    memcpy(&d, &e->data, sizeof(double));
                    snprintf(buf, sizeof(buf), "%g", d);
                    epl_sb_append(sb, buf);
                    break;
                }
                case TAG_BOOL:
                    epl_sb_append(sb, e->data ? "true" : "false");
                    break;
                case TAG_STRING:
                    epl_sb_append(sb, "\"");
                    epl_sb_append(sb, (char*)(intptr_t)e->data);
                    epl_sb_append(sb, "\"");
                    break;
                default:
                    epl_sb_append(sb, "null");
                    break;
            }
            e = e->next;
        }
    }
    epl_sb_append(sb, "}");
    return epl_sb_build(sb);
}

/* ════════════════════════════════════════════════════
 * Type Checking
 * ═══════════════════════════════════════════════════ */
const char* epl_type_name(int32_t tag) {
    switch (tag) {
        case TAG_INT:    return "Integer";
        case TAG_FLOAT:  return "Decimal";
        case TAG_BOOL:   return "Boolean";
        case TAG_STRING: return "String";
        case TAG_NONE:   return "Nothing";
        case TAG_LIST:   return "List";
        case TAG_MAP:    return "Map";
        case TAG_OBJECT: return "Object";
        default:         return "Unknown";
    }
}

/* ════════════════════════════════════════════════════
 * String Join
 * ═══════════════════════════════════════════════════ */
char* epl_string_join(EPLList *parts, const char *sep) {
    if (!parts || parts->count == 0) return strdup("");
    EPLStringBuilder *sb = epl_sb_new();
    for (int i = 0; i < parts->count; i++) {
        if (i > 0 && sep) epl_sb_append(sb, sep);
        if (parts->tags[i] == TAG_STRING) {
            epl_sb_append(sb, (char*)(intptr_t)parts->data[i]);
        } else {
            char buf[64];
            snprintf(buf, sizeof(buf), "%lld", (long long)parts->data[i]);
            epl_sb_append(sb, buf);
        }
    }
    return epl_sb_build(sb);
}

/* ════════════════════════════════════════════════════
 * String Repeat
 * ═══════════════════════════════════════════════════ */
char* epl_string_repeat(const char *s, int64_t count) {
    if (!s || count <= 0) return strdup("");
    size_t slen = strlen(s);
    if (slen > 0 && (size_t)count > SIZE_MAX / slen) {
        fprintf(stderr, "EPL: string repeat overflow\n");
        return strdup("");
    }
    size_t total = slen * (size_t)count;
    char *r = (char*)malloc(total + 1);
    if (!r) { fprintf(stderr, "EPL: string repeat out of memory\n"); return strdup(""); }
    for (int64_t i = 0; i < count; i++) {
        memcpy(r + i * slen, s, slen);
    }
    r[total] = '\0';
    return r;
}

/* ════════════════════════════════════════════════════
 * String Index Of
 * ═══════════════════════════════════════════════════ */
int64_t epl_string_index_of(const char *haystack, const char *needle) {
    if (!haystack || !needle) return -1;
    const char *found = strstr(haystack, needle);
    if (!found) return -1;
    return (int64_t)(found - haystack);
}

/* ════════════════════════════════════════════════════
 * String Format (simple {} replacement)
 * ═══════════════════════════════════════════════════ */
char* epl_string_format(const char *template_str, EPLList *args) {
    EPLStringBuilder *sb = epl_sb_new();
    int arg_idx = 0;
    const char *p = template_str;
    while (*p) {
        if (*p == '{' && *(p + 1) == '}') {
            if (args && arg_idx < args->count) {
                char buf[64];
                switch (args->tags[arg_idx]) {
                    case TAG_INT:
                        snprintf(buf, sizeof(buf), "%lld", (long long)args->data[arg_idx]);
                        epl_sb_append(sb, buf);
                        break;
                    case TAG_FLOAT: {
                        double d;
                        memcpy(&d, &args->data[arg_idx], sizeof(double));
                        snprintf(buf, sizeof(buf), "%g", d);
                        epl_sb_append(sb, buf);
                        break;
                    }
                    case TAG_STRING:
                        epl_sb_append(sb, (char*)(intptr_t)args->data[arg_idx]);
                        break;
                    case TAG_BOOL:
                        epl_sb_append(sb, args->data[arg_idx] ? "true" : "false");
                        break;
                    default:
                        epl_sb_append(sb, "null");
                        break;
                }
                arg_idx++;
            }
            p += 2;
        } else {
            char c[2] = {*p, '\0'};
            epl_sb_append(sb, c);
            p++;
        }
    }
    return epl_sb_build(sb);
}

/* ════════════════════════════════════════════════════
 * Math Extended
 * ═══════════════════════════════════════════════════ */
double epl_tan(double x)  { return tan(x); }
double epl_asin(double x) { return asin(x); }
double epl_acos(double x) { return acos(x); }
double epl_atan(double x) { return atan(x); }
double epl_atan2(double y, double x) { return atan2(y, x); }
double epl_exp(double x)  { return exp(x); }
double epl_log10(double x) { return log10(x); }
double epl_log2_val(double x)  { return log(x) / log(2.0); }
double epl_fmod(double x, double y) { return fmod(x, y); }
double epl_round(double x) { return round(x); }
int64_t epl_min_int(int64_t a, int64_t b) { return a < b ? a : b; }
int64_t epl_max_int(int64_t a, int64_t b) { return a > b ? a : b; }
int64_t epl_abs_int(int64_t x) {
    if (x == INT64_MIN) return INT64_MAX;  /* avoid UB: -INT64_MIN overflows */
    return x < 0 ? -x : x;
}
int64_t epl_sign(int64_t x) { return x > 0 ? 1 : (x < 0 ? -1 : 0); }
int64_t epl_clamp(int64_t val, int64_t lo, int64_t hi) {
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

/* ════════════════════════════════════════════════════
 * String Char Operations
 * ═══════════════════════════════════════════════════ */
int64_t epl_char_code(const char *s) {
    return (s && *s) ? (int64_t)(unsigned char)s[0] : 0;
}

char* epl_from_char_code(int64_t code) {
    char *r = (char*)epl_gc_alloc(2, TAG_STRING);
    r[0] = (char)(unsigned char)code;
    r[1] = '\0';
    return r;
}

/* ════════════════════════════════════════════════════
 * Process / System
 * ═══════════════════════════════════════════════════ */
int32_t epl_system(const char *command) {
#if defined(__EMSCRIPTEN__) || defined(__wasi__) || defined(__wasm__)
    (void)command;
    return -1;  /* system() not available in WASM */
#else
    return (int32_t)system(command);
#endif
}

void epl_exit(int32_t code) {
    exit(code);
}

/* ════════════════════════════════════════════════════
 * Assertions
 * ═══════════════════════════════════════════════════ */
void epl_assert(int32_t condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "EPL Assertion Failed: %s\n", message ? message : "");
        exit(1);
    }
}

void epl_assert_equal_int(int64_t a, int64_t b, const char *message) {
    if (a != b) {
        fprintf(stderr, "EPL Assertion Failed: expected %lld == %lld. %s\n",
                (long long)a, (long long)b, message ? message : "");
        exit(1);
    }
}

void epl_assert_equal_str(const char *a, const char *b, const char *message) {
    if (strcmp(a ? a : "", b ? b : "") != 0) {
        fprintf(stderr, "EPL Assertion Failed: expected \"%s\" == \"%s\". %s\n",
                a ? a : "(null)", b ? b : "(null)", message ? message : "");
        exit(1);
    }
}

/* ════════════════════════════════════════════════════
 * Closure Support
 * ═══════════════════════════════════════════════════ */
typedef struct {
    int64_t *values;
    int32_t *tags;
    int      count;
    int      capacity;
} EPLClosure;

EPLClosure* epl_closure_new(int32_t count) {
    EPLClosure *c = (EPLClosure*)malloc(sizeof(EPLClosure));
    c->count = count;
    c->capacity = count > 0 ? count : 4;
    c->values = (int64_t*)calloc(c->capacity, sizeof(int64_t));
    c->tags = (int32_t*)calloc(c->capacity, sizeof(int32_t));
    return c;
}

void epl_closure_set(EPLClosure *c, int32_t idx, int32_t tag, int64_t val) {
    if (!c || idx < 0 || idx >= c->capacity) return;
    c->tags[idx] = tag;
    c->values[idx] = val;
}

int64_t epl_closure_get(EPLClosure *c, int32_t idx) {
    if (!c || idx < 0 || idx >= c->capacity) return 0;
    return c->values[idx];
}

int32_t epl_closure_get_tag(EPLClosure *c, int32_t idx) {
    if (!c || idx < 0 || idx >= c->capacity) return TAG_NONE;
    return c->tags[idx];
}

void epl_closure_free(EPLClosure *c) {
    if (!c) return;
    free(c->values);
    free(c->tags);
    free(c);
}

/* ════════════════════════════════════════════════════
 * Object Inheritance / Vtable Support
 * ═══════════════════════════════════════════════════ */
#define MAX_CLASSES 256
#define MAX_METHODS_PER_CLASS 64

typedef struct {
    char *class_name;
    char *parent_name;
    char *method_names[MAX_METHODS_PER_CLASS];
    void *method_ptrs[MAX_METHODS_PER_CLASS];
    int   method_count;
} EPLClassInfo;

static EPLClassInfo epl_class_registry[MAX_CLASSES];
static int epl_class_count = 0;

EPLClassInfo* epl_class_register(const char *name, const char *parent) {
    if (epl_class_count >= MAX_CLASSES) return NULL;
    EPLClassInfo *ci = &epl_class_registry[epl_class_count++];
    ci->class_name = strdup(name);
    ci->parent_name = parent ? strdup(parent) : NULL;
    ci->method_count = 0;
    return ci;
}

void epl_class_add_method(const char *class_name, const char *method_name, void *func_ptr) {
    for (int i = 0; i < epl_class_count; i++) {
        if (strcmp(epl_class_registry[i].class_name, class_name) == 0) {
            EPLClassInfo *ci = &epl_class_registry[i];
            if (ci->method_count < MAX_METHODS_PER_CLASS) {
                ci->method_names[ci->method_count] = strdup(method_name);
                ci->method_ptrs[ci->method_count] = func_ptr;
                ci->method_count++;
            }
            return;
        }
    }
}

void* epl_class_lookup_method(const char *class_name, const char *method_name) {
    /* Walk up the inheritance chain */
    const char *current = class_name;
    while (current) {
        for (int i = 0; i < epl_class_count; i++) {
            if (strcmp(epl_class_registry[i].class_name, current) == 0) {
                EPLClassInfo *ci = &epl_class_registry[i];
                for (int j = 0; j < ci->method_count; j++) {
                    if (strcmp(ci->method_names[j], method_name) == 0) {
                        return ci->method_ptrs[j];
                    }
                }
                current = ci->parent_name;
                break;
            }
        }
        /* If class not found in registry, stop */
        break;
    }
    return NULL;
}

const char* epl_object_get_class(EPLObject *o) {
    return o ? o->class_name : "";
}

/* Copy parent properties to child object */
void epl_object_inherit(EPLObject *child, const char *parent_class) {
    /* For each registered class that matches parent_class, the properties
       are set during object creation by the compiler; this function is a
       hook for runtime inheritance of default values if needed. */
    (void)child;
    (void)parent_class;
}

/* ════════════════════════════════════════════════════
 * Legacy Reference Counting API (v4.0 compat)
 * Now delegates to the mark-and-sweep GC above.
 * ═══════════════════════════════════════════════════ */

void* epl_rc_alloc(size_t size, int32_t type_tag) {
    /* Delegate to GC allocator */
    return epl_gc_alloc(size, (int8_t)type_tag);
}

int32_t epl_rc_count(void *ptr) {
    /* With mark-and-sweep, ref counts are not tracked.
       Return 1 for any live (non-NULL) pointer. */
    return ptr ? 1 : 0;
}

/* ════════════════════════════════════════════════════
 * v5.2 Phase 1: Threading (Spawn / Parallel)
 * ═══════════════════════════════════════════════════ */

typedef void (*epl_void_fn)(void);

#if defined(__EMSCRIPTEN__) || defined(__wasi__) || defined(__wasm__)
/* WASM: no real threading — run task synchronously */
int64_t epl_spawn_task(void *func_ptr) {
    if (func_ptr) ((epl_void_fn)func_ptr)();
    return 1;
}
void epl_spawn_wait(int64_t handle) { (void)handle; }
void epl_spawn_wait_all(int64_t *handles, int32_t count) { (void)handles; (void)count; }
void epl_sleep_ms(int32_t ms) { (void)ms; }
#else

typedef struct {
    epl_void_fn func;
} EPLTaskArg;

#ifdef _WIN32
static DWORD WINAPI epl_thread_runner(LPVOID p) {
    EPLTaskArg *ta = (EPLTaskArg*)p;
    ta->func();
    free(ta);
    return 0;
}
#else
static void* epl_thread_runner(void* p) {
    EPLTaskArg *ta = (EPLTaskArg*)p;
    ta->func();
    free(ta);
    return NULL;
}
#endif

/* Spawn a void(*)(void) function on a new OS thread. Returns handle. */
int64_t epl_spawn_task(void *func_ptr) {
    EPLTaskArg *ta = (EPLTaskArg*)malloc(sizeof(EPLTaskArg));
    if (!ta) return 0;
    ta->func = (epl_void_fn)func_ptr;
#ifdef _WIN32
    HANDLE h = CreateThread(NULL, 0, epl_thread_runner, ta, 0, NULL);
    return (int64_t)(uintptr_t)h;
#else
    pthread_t t;
    if (pthread_create(&t, NULL, epl_thread_runner, ta) != 0) {
        free(ta);
        return 0;
    }
    return (int64_t)t;
#endif
}

/* Wait for a spawned task to complete. */
void epl_spawn_wait(int64_t handle) {
    if (handle == 0) return;
#ifdef _WIN32
    WaitForSingleObject((HANDLE)(uintptr_t)handle, INFINITE);
    CloseHandle((HANDLE)(uintptr_t)handle);
#else
    pthread_join((pthread_t)handle, NULL);
#endif
}

/* Wait for an array of N task handles. */
void epl_spawn_wait_all(int64_t *handles, int32_t count) {
    for (int32_t i = 0; i < count; i++) {
        epl_spawn_wait(handles[i]);
    }
}

/* Sleep current thread for `ms` milliseconds. */
void epl_sleep_ms(int32_t ms) {
#ifdef _WIN32
    Sleep((DWORD)ms);
#else
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
#endif
}
#endif /* !WASM */

/* ════════════════════════════════════════════════════
 * v5.2 Phase 1: Dynamic Library Loading (FFI)
 * ═══════════════════════════════════════════════════ */

#if defined(__EMSCRIPTEN__) || defined(__wasi__) || defined(__wasm__)
/* WASM: no dynamic library loading */
void* epl_dlopen(const char *path) { (void)path; return NULL; }
void* epl_dlsym(void *handle, const char *symbol) { (void)handle; (void)symbol; return NULL; }
void epl_dlclose(void *handle) { (void)handle; }
#elif defined(_WIN32)
/* Windows: LoadLibraryA / GetProcAddress / FreeLibrary */
void* epl_dlopen(const char *path) {
    if (!path || !*path) return NULL;
    HMODULE h = LoadLibraryA(path);
    return (void*)h;
}
void* epl_dlsym(void *handle, const char *symbol) {
    if (!handle || !symbol) return NULL;
    return (void*)GetProcAddress((HMODULE)handle, symbol);
}
void epl_dlclose(void *handle) {
    if (handle) FreeLibrary((HMODULE)handle);
}
#else
#include <dlfcn.h>
void* epl_dlopen(const char *path) {
    if (!path || !*path) return NULL;
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
}
void* epl_dlsym(void *handle, const char *symbol) {
    if (!handle || !symbol) return NULL;
    return dlsym(handle, symbol);
}
void epl_dlclose(void *handle) {
    if (handle) dlclose(handle);
}
#endif

/* Call a foreign function with i64 return through a resolved function pointer.
   args: array of int64_t (each arg cast to int64_t), argc: count.
   Supports up to 8 arguments for ABI simplicity. */
int64_t epl_ffi_call_i64(void *func_ptr, int64_t *args, int32_t argc) {
    if (!func_ptr) return 0;
    typedef int64_t (*fn0)(void);
    typedef int64_t (*fn1)(int64_t);
    typedef int64_t (*fn2)(int64_t, int64_t);
    typedef int64_t (*fn3)(int64_t, int64_t, int64_t);
    typedef int64_t (*fn4)(int64_t, int64_t, int64_t, int64_t);
    typedef int64_t (*fn5)(int64_t, int64_t, int64_t, int64_t, int64_t);
    typedef int64_t (*fn6)(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
    typedef int64_t (*fn7)(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
    typedef int64_t (*fn8)(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
    switch (argc) {
        case 0: return ((fn0)func_ptr)();
        case 1: return ((fn1)func_ptr)(args[0]);
        case 2: return ((fn2)func_ptr)(args[0], args[1]);
        case 3: return ((fn3)func_ptr)(args[0], args[1], args[2]);
        case 4: return ((fn4)func_ptr)(args[0], args[1], args[2], args[3]);
        case 5: return ((fn5)func_ptr)(args[0], args[1], args[2], args[3], args[4]);
        case 6: return ((fn6)func_ptr)(args[0], args[1], args[2], args[3], args[4], args[5]);
        case 7: return ((fn7)func_ptr)(args[0], args[1], args[2], args[3], args[4], args[5], args[6]);
        case 8: return ((fn8)func_ptr)(args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7]);
        default: return 0;
    }
}

/* Call a foreign function that returns double. */
double epl_ffi_call_double(void *func_ptr, double *args, int32_t argc) {
    if (!func_ptr) return 0.0;
    typedef double (*fn0)(void);
    typedef double (*fn1)(double);
    typedef double (*fn2)(double, double);
    typedef double (*fn3)(double, double, double);
    typedef double (*fn4)(double, double, double, double);
    switch (argc) {
        case 0: return ((fn0)func_ptr)();
        case 1: return ((fn1)func_ptr)(args[0]);
        case 2: return ((fn2)func_ptr)(args[0], args[1]);
        case 3: return ((fn3)func_ptr)(args[0], args[1], args[2]);
        case 4: return ((fn4)func_ptr)(args[0], args[1], args[2], args[3]);
        default: return 0.0;
    }
}

/* Call a foreign function that returns a pointer (char*). */
void* epl_ffi_call_ptr(void *func_ptr, int64_t *args, int32_t argc) {
    if (!func_ptr) return NULL;
    typedef void* (*fn0)(void);
    typedef void* (*fn1)(int64_t);
    typedef void* (*fn2)(int64_t, int64_t);
    typedef void* (*fn3)(int64_t, int64_t, int64_t);
    typedef void* (*fn4)(int64_t, int64_t, int64_t, int64_t);
    switch (argc) {
        case 0: return ((fn0)func_ptr)();
        case 1: return ((fn1)func_ptr)(args[0]);
        case 2: return ((fn2)func_ptr)(args[0], args[1]);
        case 3: return ((fn3)func_ptr)(args[0], args[1], args[2]);
        case 4: return ((fn4)func_ptr)(args[0], args[1], args[2], args[3]);
        default: return NULL;
    }
}

/* Call a void foreign function. */
void epl_ffi_call_void(void *func_ptr, int64_t *args, int32_t argc) {
    if (!func_ptr) return;
    typedef void (*fn0)(void);
    typedef void (*fn1)(int64_t);
    typedef void (*fn2)(int64_t, int64_t);
    typedef void (*fn3)(int64_t, int64_t, int64_t);
    typedef void (*fn4)(int64_t, int64_t, int64_t, int64_t);
    switch (argc) {
        case 0: ((fn0)func_ptr)(); break;
        case 1: ((fn1)func_ptr)(args[0]); break;
        case 2: ((fn2)func_ptr)(args[0], args[1]); break;
        case 3: ((fn3)func_ptr)(args[0], args[1], args[2]); break;
        case 4: ((fn4)func_ptr)(args[0], args[1], args[2], args[3]); break;
    }
}

/* ════════════════════════════════════════════════════
 * v5.2 Phase 1: Debug Trap
 * ═══════════════════════════════════════════════════ */

void epl_debug_trap(void) {
#if defined(_MSC_VER)
    __debugbreak();
#elif defined(__GNUC__) || defined(__clang__)
    __builtin_trap();
#else
    /* Fallback: raise SIGTRAP */
    raise(5);  /* SIGTRAP = 5 on most platforms */
#endif
}

/* ═══════════════════════════════════════════════════════════
 *  Phase 2: Standard Library C Runtime Bindings
 * ═══════════════════════════════════════════════════════════ */

/* ── Math (extended) ── */
double epl_math_log2(double x) { return log2(x); }
double epl_math_log10(double x) { return log10(x); }
double epl_math_exp(double x) { return exp(x); }
double epl_math_hypot(double x, double y) { return hypot(x, y); }
double epl_math_sinh(double x) { return sinh(x); }
double epl_math_cosh(double x) { return cosh(x); }
double epl_math_tanh(double x) { return tanh(x); }
double epl_math_asinh(double x) { return asinh(x); }
double epl_math_acosh(double x) { return acosh(x); }
double epl_math_atanh(double x) { return atanh(x); }
double epl_math_fmod(double x, double y) { return fmod(x, y); }
double epl_math_copysign(double x, double y) { return copysign(x, y); }

int64_t epl_math_factorial(int64_t n) {
    if (n < 0) return 0;
    int64_t r = 1;
    for (int64_t i = 2; i <= n; i++) r *= i;
    return r;
}

int64_t epl_math_gcd(int64_t a, int64_t b) {
    if (a < 0) a = -a;
    if (b < 0) b = -b;
    while (b) { int64_t t = b; b = a % b; a = t; }
    return a;
}

int64_t epl_math_lcm(int64_t a, int64_t b) {
    if (a == 0 || b == 0) return 0;
    int64_t g = epl_math_gcd(a, b);
    return (a / g) * b;
}

int64_t epl_math_permutations(int64_t n, int64_t r) {
    if (r > n || r < 0) return 0;
    int64_t result = 1;
    for (int64_t i = n; i > n - r; i--) result *= i;
    return result;
}

int64_t epl_math_combinations(int64_t n, int64_t r) {
    if (r > n || r < 0) return 0;
    if (r > n - r) r = n - r;
    int64_t result = 1;
    for (int64_t i = 0; i < r; i++) {
        result = result * (n - i) / (i + 1);
    }
    return result;
}

/* ── Crypto (hashing) ── */
/* Simple SHA-256 implementation for compiled code */
static void epl_sha256_block(uint32_t* state, const uint8_t* block);

/* We provide hash wrappers that call the C runtime's standard functions if available */
/* For compiled executables, these are linked against the system's crypto libs */

/* ── OS helpers ── */
const char* epl_os_platform(void) {
#if defined(_WIN32)
    return "windows";
#elif defined(__APPLE__)
    return "darwin";
#elif defined(__linux__)
    return "linux";
#else
    return "unknown";
#endif
}

const char* epl_os_arch(void) {
#if defined(__x86_64__) || defined(_M_X64)
    return "x64";
#elif defined(__i386__) || defined(_M_IX86)
    return "x86";
#elif defined(__aarch64__) || defined(_M_ARM64)
    return "arm64";
#elif defined(__arm__) || defined(_M_ARM)
    return "arm";
#else
    return "unknown";
#endif
}

int32_t epl_os_pid(void) {
#if defined(_WIN32)
    return (int32_t)GetCurrentProcessId();
#else
    return (int32_t)getpid();
#endif
}

const char* epl_os_env_get(const char* name) {
    return getenv(name);
}

int32_t epl_os_env_set(const char* name, const char* value) {
#if defined(_WIN32)
    char buf[4096];
    snprintf(buf, sizeof(buf), "%s=%s", name, value);
    return _putenv(buf) == 0 ? 1 : 0;
#else
    return setenv(name, value, 1) == 0 ? 1 : 0;
#endif
}

/* ── DateTime helpers ── */
double epl_time_now(void) {
    struct timespec ts;
#if defined(_WIN32)
    /* Windows: use clock_gettime if available, else fallback */
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    /* Convert from 100ns intervals since 1601 to seconds since 1970 */
    t -= 116444736000000000ULL;
    return (double)t / 10000000.0;
#else
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
#endif
}

/* ── Encoding helpers ── */
static const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

char* epl_base64_encode(const char* input, int32_t len) {
    int out_len = 4 * ((len + 2) / 3);
    char* out = (char*)malloc(out_len + 1);
    if (!out) return NULL;
    int j = 0;
    for (int i = 0; i < len; i += 3) {
        uint32_t triple = ((uint32_t)(uint8_t)input[i]) << 16;
        if (i + 1 < len) triple |= ((uint32_t)(uint8_t)input[i+1]) << 8;
        if (i + 2 < len) triple |= (uint8_t)input[i+2];
        out[j++] = b64_table[(triple >> 18) & 0x3F];
        out[j++] = b64_table[(triple >> 12) & 0x3F];
        out[j++] = (i + 1 < len) ? b64_table[(triple >> 6) & 0x3F] : '=';
        out[j++] = (i + 2 < len) ? b64_table[triple & 0x3F] : '=';
    }
    out[j] = '\0';
    return out;
}

static int b64_decode_char(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

char* epl_base64_decode(const char* input, int32_t* out_len) {
    int len = (int)strlen(input);
    int pad = 0;
    if (len > 0 && input[len-1] == '=') pad++;
    if (len > 1 && input[len-2] == '=') pad++;
    *out_len = (len / 4) * 3 - pad;
    char* out = (char*)malloc(*out_len + 1);
    if (!out) return NULL;
    int j = 0;
    for (int i = 0; i < len; i += 4) {
        uint32_t triple = 0;
        for (int k = 0; k < 4 && i+k < len; k++) {
            int v = b64_decode_char(input[i+k]);
            if (v >= 0) triple = (triple << 6) | v;
            else triple <<= 6;
        }
        if (j < *out_len) out[j++] = (triple >> 16) & 0xFF;
        if (j < *out_len) out[j++] = (triple >> 8) & 0xFF;
        if (j < *out_len) out[j++] = triple & 0xFF;
    }
    out[*out_len] = '\0';
    return out;
}

char* epl_hex_encode(const char* input, int32_t len) {
    char* out = (char*)malloc(len * 2 + 1);
    if (!out) return NULL;
    for (int i = 0; i < len; i++) {
        sprintf(out + i * 2, "%02x", (uint8_t)input[i]);
    }
    out[len * 2] = '\0';
    return out;
}

/* ── File I/O helpers ── */
char* epl_file_read(const char* path) {
    FILE* f = fopen(path, "r");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* buf = (char*)malloc(sz + 1);
    if (!buf) { fclose(f); return NULL; }
    fread(buf, 1, sz, f);
    buf[sz] = '\0';
    fclose(f);
    return buf;
}

int32_t epl_file_write(const char* path, const char* data) {
    FILE* f = fopen(path, "w");
    if (!f) return 0;
    fputs(data, f);
    fclose(f);
    return 1;
}

int32_t epl_file_append(const char* path, const char* data) {
    FILE* f = fopen(path, "a");
    if (!f) return 0;
    fputs(data, f);
    fclose(f);
    return 1;
}

int32_t epl_file_exists(const char* path) {
    FILE* f = fopen(path, "r");
    if (f) { fclose(f); return 1; }
    return 0;
}

int32_t epl_file_delete(const char* path) {
    return remove(path) == 0 ? 1 : 0;
}

int64_t epl_file_size(const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    int64_t sz = ftell(f);
    fclose(f);
    return sz;
}

/* ── Regex helpers (POSIX) ── */
#if !defined(_WIN32)
#include <regex.h>
int32_t epl_regex_test(const char* pattern, const char* text) {
    regex_t rx;
    if (regcomp(&rx, pattern, REG_EXTENDED | REG_NOSUB) != 0) return 0;
    int result = regexec(&rx, text, 0, NULL, 0) == 0 ? 1 : 0;
    regfree(&rx);
    return result;
}
#endif
