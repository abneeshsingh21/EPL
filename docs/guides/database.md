# Database & ORM Guide

EPL's most directly supported database workflow is built-in SQLite via the `db_*` functions. Additional adapters and ORM-style helpers are available, but non-SQLite production deployments should be validated in your own environment and against the current support boundary in the support matrix.

## Level 1: SQLite (Built-in)

```epl
db = db_open("myapp.db")

db_create_table(db, "users", Map with id = "INTEGER PRIMARY KEY AUTOINCREMENT" and name = "TEXT NOT NULL" and email = "TEXT UNIQUE")

db_insert(db, "users", Map with name = "Alice" and email = "alice@example.com")
users = db_query(db, "SELECT * FROM users")
Say users

db_close(db)
```

## Level 2: Additional Database Adapters

Connect to PostgreSQL, MySQL, or SQLite through the `real_db_*` helpers when the required driver/toolchain is available. These helpers are useful for integration work, but they are not the primary release-gated database contract.

```epl
Note: PostgreSQL
db = real_db_connect("postgresql://user:pass@localhost:5432/mydb")

Note: MySQL
db = real_db_connect("mysql://user:pass@localhost:3306/mydb")

Note: SQLite (also works)
db = real_db_connect("sqlite:///myapp.db")
```

### Queries

```epl
rows = real_db_query(db, "SELECT * FROM users WHERE active = ?", [True])
user = real_db_query_one(db, "SELECT * FROM users WHERE id = ?", [1])
count = real_db_count(db, "users")
```

### Transactions

```epl
real_db_begin(db)
real_db_execute(db, "UPDATE accounts SET balance = balance - 100 WHERE id = ?", [1])
real_db_execute(db, "UPDATE accounts SET balance = balance + 100 WHERE id = ?", [2])
real_db_commit(db)
```

## Level 3: ORM-Style Helpers

ORM helpers are available for convenience and local application scaffolding. Treat them as a higher-level layer over the core database surface, and validate migrations and query behavior against your target database before relying on them in production.

```epl
db = orm_open("myapp.db")

Note: Define models
orm_define_model(db, "User")
orm_add_field(db, "User", "name", "TEXT NOT NULL")
orm_add_field(db, "User", "email", "TEXT UNIQUE")
orm_add_field(db, "User", "age", "INTEGER")
orm_migrate(db)

Note: Create records
user = orm_create(db, "User", Map with name = "Alice" and email = "alice@example.com" and age = 30)

Note: Query
all_users = orm_find(db, "User")
alice = orm_find_by_id(db, "User", 1)

Note: Update
orm_update(db, "User", 1, Map with age = 31)

Note: Delete
orm_delete(db, "User", 1)
```

### Relationships

```epl
orm_has_many(db, "User", "posts", "Post", "user_id")
orm_belongs_to(db, "Post", "author", "User", "user_id")
user_with_posts = orm_with_related(db, "User", 1, "posts")
```

### Migrations

```epl
orm_migrate(db)  Note: Creates tables if they don't exist
orm_add_index(db, "User", "email")
```

## Function Reference

| Function | Description |
|----------|-------------|
| `db_open(path)` | Open SQLite database |
| `db_query(db, sql, params)` | Execute query, return rows |
| `db_execute(db, sql, params)` | Execute statement |
| `real_db_connect(url)` | Connect to PostgreSQL/MySQL/SQLite when the matching driver/toolchain is available |
| `orm_define_model(db, name)` | Define ORM model |
| `orm_migrate(db)` | Run migrations |
| `orm_create(db, model, data)` | Create record |
| `orm_find(db, model)` | Find all records |
