# epl-db

Supported EPL database facade package.

## Install

```bash
epl install epl-db
```

## Use

```epl
Import "epl-db"

Create conn equal to open("app.db")
Call create_table(conn, "notes", Map with title = "TEXT" and body = "TEXT")
Call insert(conn, "notes", Map with title = "Hello" and body = "World")
Say query(conn, "SELECT * FROM notes")
Call close(conn)
```

## Included Surface

- open and close helpers
- execute and query helpers
- CRUD helpers
- schema helpers
- transaction helpers
