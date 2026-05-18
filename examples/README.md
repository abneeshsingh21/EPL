<div align="center">

# 📚 EPL Examples

Real-world programs demonstrating the power of the **English Programming Language**.

</div>

---

## Quick Start

```bash
pip install eplang
epl run examples/hello.epl
```

---

## Examples by Category

### 🟢 Beginner

| File | Description | Key Concepts |
|------|-------------|--------------|
| [`hello.epl`](hello.epl) | Hello World | `Print`, basic output |
| [`variables.epl`](variables.epl) | Variable declarations | `Create`, `Set`, types |
| [`strings.epl`](strings.epl) | String operations | Interpolation, methods |
| [`conditions.epl`](conditions.epl) | If/Otherwise logic | Control flow, comparisons |
| [`loops.epl`](loops.epl) | For, While, Repeat | Iteration patterns |
| [`functions.epl`](functions.epl) | Function definitions | `Function`, `Return`, params |
| [`builtins.epl`](builtins.epl) | Built-in functions | `length`, `sorted`, `random` |

### 🟡 Intermediate

| File | Description | Key Concepts |
|------|-------------|--------------|
| [`classes.epl`](classes.epl) | Object-oriented programming | `Class`, inheritance, methods |
| [`error_handling.epl`](error_handling.epl) | Try/Catch patterns | Exception handling, `Throw` |
| [`files.epl`](files.epl) | File I/O operations | `Read`, `Write`, `Append` |
| [`maps.epl`](maps.epl) | Dictionary/Map usage | `Map with`, key-value data |
| [`lambdas.epl`](lambdas.epl) | Lambda expressions | Functional programming |
| [`enums.epl`](enums.epl) | Enumeration types | `Enum`, pattern matching |
| [`imports.epl`](imports.epl) | Module system | `Import`, `Use python` |
| [`regex_demo.epl`](regex_demo.epl) | Regular expressions | Pattern matching, validation |
| [`slicing.epl`](slicing.epl) | List/string slicing | Index operations, ranges |

### 🔴 Advanced

| File | Description | Key Concepts |
|------|-------------|--------------|
| [`advanced.epl`](advanced.epl) | Advanced language features | Generics, decorators, closures |
| [`webapp.epl`](webapp.epl) | Full web application | `WebApp`, routes, templates |
| [`todo_api.epl`](todo_api.epl) | REST API with SQLite | CRUD, database, JSON |
| [`database_app.epl`](database_app.epl) | Database operations | SQLite ORM, queries |
| [`rest_api_jwt.epl`](rest_api_jwt.epl) | JWT authentication API | Auth, tokens, middleware |
| [`portfolio.epl`](portfolio.epl) | Portfolio website | Web pages, styling, routes |
| [`blog_engine.epl`](blog_engine.epl) | Blog platform | Templates, CRUD, sessions |
| [`discord_bot.epl`](discord_bot.epl) | Discord bot | API integration, commands |
| [`data_pipeline.epl`](data_pipeline.epl) | Data processing | CSV, transforms, aggregation |
| [`js_bridge_demo.epl`](js_bridge_demo.epl) | JavaScript interop | `Use javascript`, NPM bridge |

### 🚀 Starter Projects

| Directory | Description | Run Command |
|-----------|-------------|-------------|
| [`todo_app/`](todo_app/) | Full-stack TODO app | `epl serve examples/todo_app/main.epl` |
| [`official_starters/`](official_starters/) | Project templates | `epl new --template <name>` |
| [`k8s_deploy/`](k8s_deploy/) | Kubernetes deployment | `epl deploy k8s --image myapp:1.0` |

---

## Running Examples

```bash
# Run any example
epl run examples/<filename>.epl

# Run a web app with production server
epl serve examples/webapp.epl

# Run in development mode with hot-reload
epl serve examples/webapp.epl --dev

# Transpile to JavaScript
epl transpile examples/hello.epl --target js
```

---

<div align="center">

**[Full Documentation](https://abneeshsingh21.github.io/EPL/)** · **[Language Reference](https://abneeshsingh21.github.io/EPL/language-reference/)**

</div>
