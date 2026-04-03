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
Call create_table(conn, "notes", {"title": "text", "body": "text"})
Call insert(conn, "notes", {"title": "Hello", "body": "World"})
Print query(conn, "select * from notes")
Call close(conn)
```

## Included Surface

- open and close helpers
- execute and query helpers
- CRUD helpers
- schema helpers
- transaction helpers
