# Database Guide

EPL v9.7.0 has two database layers:

- `db_*`: built-in SQLite helpers. This is the most directly supported local database workflow.
- `real_db_*`: additional adapters for PostgreSQL, MySQL, and SQLite when the required drivers and runtime environment are available.

For enterprise work, treat SQL schema management as an explicit migration concern. Use raw `CREATE TABLE` statements through `db_execute` or `real_db_execute`, keep values parameterized, and validate behavior in CI.

---

## Level 1: SQLite With Built-in `db_*`

```epl
db = db_open("myapp.db")

db_execute(db, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1)")

db_execute(db, "INSERT INTO users (name, email) VALUES (?, ?)", ["Alice", "alice@example.com"])

users = db_query(db, "SELECT id, name, email, active FROM users ORDER BY id")
Say users

db_close(db)
```

Why this is the recommended production pattern:

- SQL migrations stay explicit and reviewable.
- Complex constraints remain under SQLite's own SQL parser.
- Parameters are bound safely.
- The same pattern maps cleanly to `real_db_*`.

---

## Inserts And Updates

```epl
db = db_open("myapp.db")

db_execute(db, "UPDATE users SET active = ? WHERE email = ?", [False, "alice@example.com"])
db_execute(db, "DELETE FROM users WHERE active = ?", [False])

db_close(db)
```

Use `db_insert` only for simple table inserts where table and column names are controlled by your code:

```epl
db = db_open("myapp.db")
user_id = db_insert(db, "users", Map with name = "Bob" and email = "bob@example.com")
db_close(db)
```

---

## Queries

```epl
db = db_open("myapp.db")

rows = db_query(db, "SELECT id, name FROM users WHERE active = ?", [True])
first_user = db_query_one(db, "SELECT id, name FROM users WHERE email = ?", ["alice@example.com"])

If first_user == Nothing Then
    Say "No user"
Otherwise
    Say first_user.name
End

db_close(db)
```

---

## `db_create_table` Boundary

`db_create_table(db, name, columns)` validates table names, column names, and type components, then builds the `CREATE TABLE` for you. It now accepts standard SQL column constraints and parameterized types directly in the column map — `INTEGER PRIMARY KEY`, `TEXT NOT NULL`, `VARCHAR(255)`, `DECIMAL(10,2)`, and so on (allowed type words include `DECIMAL`, `FLOAT`, `DOUBLE`, `CHAR`, and `TIMESTAMP`). Identifiers are still validated and SQL injection is still rejected:

```epl
db = db_open(":memory:")
db_create_table(db, "users", Map with id = "INTEGER PRIMARY KEY" and name = "TEXT NOT NULL" and email = "VARCHAR(255)" and balance = "DECIMAL(10,2)")
Say db_tables(db)
db_close(db)
```

For richer schemas — foreign keys, composite or partial indexes, `DEFAULT` expressions, and `CHECK` clauses — prefer raw SQL migrations:

```epl
db_execute(db, "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
```

Rationale: standard column constraints are well supported by `db_create_table`, but foreign keys, indexes, and defaults are still easier to review and test as explicit, versioned SQL.

---

## Transactions

SQLite transactions can be expressed directly:

```epl
db = db_open("bank.db")

Try
    db_execute(db, "BEGIN")
    db_execute(db, "UPDATE accounts SET balance = balance - ? WHERE id = ?", [100, 1])
    db_execute(db, "UPDATE accounts SET balance = balance + ? WHERE id = ?", [100, 2])
    db_execute(db, "COMMIT")
Catch error
    db_execute(db, "ROLLBACK")
    Throw "Transfer failed: $error"
End

db_close(db)
```

---

## Indexes And Migrations

Keep migrations in functions so they can run during app startup and test setup.

```epl
Function migrate takes db
    db_execute(db, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)")
    db_execute(db, "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
End

db = db_open("auth.db")
migrate(db)
```

For larger systems, version migrations in separate `.epl` files and run them in order.

---

## Level 2: Additional Database Adapters

Use `real_db_*` helpers when the target driver and deployment environment are available.

```epl
db = real_db_connect("postgresql://user:pass@localhost:5432/mydb")
rows = real_db_query(db, "SELECT id, email FROM users WHERE active = ?", [True])
real_db_close(db)
```

SQLite with `real_db_*`:

```epl
db = real_db_connect("sqlite:///myapp.db")
real_db_execute(db, "CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, status TEXT NOT NULL)")
jobs = real_db_query(db, "SELECT * FROM jobs")
real_db_close(db)
```

Validate these adapters in CI with the same database engine and driver versions used in production.

---

## Level 3: ORM-Style Helpers

ORM helpers are available for scaffolding and application convenience. Treat them as a higher-level layer over SQL and validate generated schemas before production use.

```epl
db = orm_open("myapp.db")

orm_define_model(db, "User")
orm_add_field(db, "User", "name", "TEXT NOT NULL")
orm_add_field(db, "User", "email", "TEXT UNIQUE")
orm_migrate(db)

user = orm_create(db, "User", Map with name = "Alice" and email = "alice@example.com")
users = orm_find(db, "User")
```

---

## WebApp Integration

```epl
Create WebApp called app

db = db_open("notes.db")
db_execute(db, "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)")

Route "/api/notes" responds with
    notes = db_query(db, "SELECT id, title FROM notes ORDER BY id DESC")
    Send json Map with ok = True and notes = notes
End

Route "/api/notes/create" responds with
    title = trim(request_data.get("title", ""))

    If length(title) == 0 Then
        Send json Map with ok = False and error = "Title is required"
    Otherwise
        db_execute(db, "INSERT INTO notes (title) VALUES (?)", [title])
        Send json Map with ok = True
    End
End
```

---

## Security Checklist

- Never concatenate user input into SQL.
- Use placeholders (`?`) and parameter lists for all external values.
- Keep table and column names static in application code.
- Use raw SQL migrations for constraints, foreign keys, indexes, and defaults.
- Enable database backups before running migrations in production.
- Run migration tests against an empty database and a database with existing data.
- Close connections in scripts and tests.
- Treat adapter URLs and credentials as secrets.

---

## Function Reference

| Function | Description |
| --- | --- |
| `db_open(path)` | Open a SQLite database and return a connection ID |
| `db_close(db)` | Close a SQLite connection |
| `db_execute(db, sql[, params])` | Execute SQL and return affected row count |
| `db_query(db, sql[, params])` | Execute query and return all rows as maps |
| `db_query_one(db, sql[, params])` | Execute query and return one row or `Nothing` |
| `db_insert(db, table, map)` | Insert a simple record and return row ID |
| `db_create_table(db, table, columns)` | Create simple table from map of column names to type strings |
| `real_db_connect(url)` | Connect to PostgreSQL/MySQL/SQLite when supported |
| `real_db_execute(db, sql[, params])` | Execute SQL through an additional adapter |
| `real_db_query(db, sql[, params])` | Query through an additional adapter |
| `real_db_query_one(db, sql[, params])` | Query one row through an additional adapter |
| `real_db_close(db)` | Close an additional adapter connection |
