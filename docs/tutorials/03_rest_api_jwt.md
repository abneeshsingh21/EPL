# Tutorial 3: Securing endpoints with simulated JWTs

Security is paramount. In this tutorial, we analyze the Showcase `rest_api_jwt.epl` to understand how to parse headers and block unauthorized traffic.

## Step 1: Receiving the Request Data

EPL automatically intercepts POST requests and parses their JSON payload into an easily accessible Map globally known as `request.body_json`!

```epl
Route "/api/login" responds with
    data = request.body_json
    username = data.get("username")
    password = data.get("password")
    
    auth_check = db_query(db, "SELECT count(*) as count FROM users WHERE username = '" + username + "' AND password = '" + password + "'")
    If auth_check.count == 0 Then
        Send json Map with success = false and error = "Invalid credentials"
    Otherwise
        Send json Map with success = true
    End
End
```

## Step 2: Creating the Token

Tokens can be created using the `base64_encode()` builtin. This represents a stateless authentication string you can send back to the client.

```epl
Route "/api/login" responds with
    username = request.body_json.get("username")
    token = base64_encode(username + "_authorized_" + timestamp())
    Send json Map with success = true and token = token
End
```

## Step 3: Protecting Endpoints

Use `request.get_header("Authorization")` to sniff traffic. If the token is empty or invalid, just route back the error. It's truly that straightforward!

```epl
Route "/api/posts/create" responds with
    token = request.get_header("Authorization")
    If token == "" Then
        Send json Map with success = false and error = "Unauthorized"
    Otherwise
        Note: User successfully authenticated. Execute secured logic.
        Send json Map with success = true
    End
End
```
