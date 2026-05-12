# Examples Gallery

Real-world examples demonstrating EPL's capabilities.

## 🌐 Hello Web — Minimal Web Server

A production-ready web server with HTML pages and JSON APIs.

```epl
Create WebApp called app

Page "/" renders
    Title "Welcome to EPL"
    Heading "Hello from EPL! 👋"
    Paragraph "This is a production-ready web server."
    Link "/about" shows "About this app"
End

Route "/api/health" responds with
    Return Map with status = "ok" and version = "1.0.0"
End

app.start(8000)
```

```bash
epl serve examples/hello_web/main.epl
```

---

## 📝 TODO API — REST API with Database

Full RESTful CRUD API with SQLite.

```epl
Create WebApp called app
db = db_open("todos.db")
db_create_table(db, "todos", Map with id = "INTEGER PRIMARY KEY" and title = "TEXT NOT NULL" and completed = "INT DEFAULT 0")

Route "/api/todos" responds with
    todos = db_query(db, "SELECT * FROM todos ORDER BY id DESC")
    Return Map with success = True and data = todos
End

Route "/api/todos" responds with
    body = request_body()
    db_execute(db, "INSERT INTO todos (title) VALUES (?)", [body.get("title")])
    Return Map with success = True and message = "Created"
End

app.start(8000)
```

```bash
epl serve examples/todo_api/main.epl

# Test:
curl http://localhost:8000/api/todos
curl -X POST http://localhost:8000/api/todos -d '{"title":"Buy groceries"End'
```

---

## 🧮 Calculator — CLI App

Interactive command-line calculator with history and math functions.

```epl
Say "EPL Calculator v1.0"
running = True
history = []

Repeat 3 times
    Say "Loop"
End

While running == true
    Ask "calc> " store in user_input
    If user_input == "quit" Then
        running = false
    Otherwise If user_input == "history" Then
        For each entry in history
            Say entry
        End
    Otherwise
        result = evaluate(user_input)
        Say "= " + to_string(result)
    End
End
```

```bash
epl run examples/calculator/main.epl
```

---

## 📊 Data Analysis

```epl
df = ds_read_csv("sales.csv")
Say ds_shape(df)
Say ds_describe(df)

total = ds_sum(df, "revenue")
Say "Total revenue: $" + to_string(total)

ds_bar_chart(df, "month", "revenue")
ds_save_plot("revenue_chart.png")
```

---

## 🤖 Machine Learning

```epl
data = ml_load_data("iris")
split = ml_split(data, 0.8)

model = ml_random_forest(get(split, "train"))
ml_train(model)

accuracy = ml_accuracy(model, get(split, "test"))
Say "Accuracy: " + to_string(accuracy * 100) + "%"

ml_save_model(model, "iris_model.pkl")
```

---

## 🎮 Game Development

```epl
game_create("Space Shooter", 800, 600)
game_set_bg("black")

player = game_sprite("player.png", 400, 500)
score = 0

game_on_key("left", Lambda -> game_move(player, -5, 0))
game_on_key("right", Lambda -> game_move(player, 5, 0))
game_on_update(Lambda -> game_update_text("Score: " + to_string(score)))

game_run()
```

---

## ☸️ Kubernetes Deployment

Generate production-ready K8s manifests from the command line:

```bash
epl deploy k8s myapp/main.epl \
  --app-name my-service \
  --image my-registry/my-service:1.2.0 \
  --port 8000 \
  --host my-service.example.com \
  --tls \
  --replicas 3
```

Generates: Namespace, ConfigMap, Deployment, Service, Ingress, and HPA YAML.

---

## 📊 Observability & Monitoring

```epl
Create WebApp called app

Import "epl.observability" As obs
obs.attach(app)

Route "/api/data" responds with
    obs.start_request()
    Note: ... your logic ...
    obs.record_request(0.042, nothing)
    Send json Map with result = "ok"
End

app.start(8000)
```

Automatically exposes:
- `/_health` — JSON health status with uptime
- `/_ready` — readiness probe (can be toggled)
- `/_metrics` — Prometheus-format metrics (requests, errors, latency)

---

## 🔌 JavaScript Bridge

Use NPM packages directly in EPL:

```epl
Use javascript "lodash" as _
Use javascript "dayjs" as dayjs

names = ["alice", "bob", "charlie"]
capitalized = _.map(names, _.capitalize)
Say capitalized

today = dayjs.format("YYYY-MM-DD")
Say "Today is " + today
```

---

## 🎨 Style & Layout

```epl
Style "card"
    background "#ffffff"
    border-radius "12px"
    padding "24px"
    box-shadow "0 2px 8px rgba(0,0,0,0.1)"
End

Layout responsive columns 3
    Text "Column 1"
    Text "Column 2"
    Text "Column 3"
End
```

---

## 🧊 3D Scene (WebGL)

```epl
Scene "demo" 800 by 600
    Box "floor" at 0 -1 0 size 10 0.2 10 color "#888888"
    Box "cube" at 0 1 0 size 2 2 2 color "#ff4500"
    Light "sun" at 5 10 5
    Camera at 0 5 10 look 0 0 0
End
```

---

## 🖌️ Canvas Drawing

```epl
Canvas "art" draw rect x 10 y 10 width 200 height 100 fill "#3498db"
Canvas "art" draw circle x 150 y 150 radius 50 fill "#e74c3c"
Canvas "art" draw text x 50 y 250 content "Hello Canvas!" fill "#2c3e50"
```

---

## More Examples

Browse the full examples directory on GitHub:
[github.com/abneeshsingh21/EPL/tree/main/examples](https://github.com/abneeshsingh21/EPL/tree/main/examples)
