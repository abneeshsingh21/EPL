# Tutorial 1: Building a Web Server natively in EPL

EPL ships with a lightning-fast, highly scalable built-in Web Framework. You do not need to rely on external frameworks like Flask or Express.

## Step 1: The Skeleton

Create a new file called `website.epl`. We begin by initializing the framework using the descriptive `WebApp` keyword:

```epl
Create WebApp called mySite
```

## Step 2: Defining Routes & UIs

EPL abstracts away the need to manually write raw HTML strings by providing native UI keywords right inside your routes!

```epl
Route "/" shows
    Page "Welcome Home"
        Heading "Hello from EPL! 🚀"
        SubHeading "The easiest way to code."
        Text "This page was generated strictly through EPL code."
        
        Button "Click me!"
        Link "Visit the about page" to "/about"
    End
End
```

## Step 3: Starting the Server

Starting the server works exactly like you would phrase it in English:

```epl
Start mySite on port 8080
```

## Creating APIs

If you don't want to serve UI pages, but instead want to create an API backend, use the `responds with` syntax along with `Send json`.

```epl
Route "/api/status" responds with
    Send json Map with name = "EPL" and version = "7.0"
End
```

## Deployment!

Deploying EPL web apps on modern cloud providers (like **Railway**, **Render**, or **Fly.io**) can use standard Python container workflows. For supported production-hosting patterns, align the runtime setup with the [support matrix](../support-matrix.md) and validate the generated container, server entrypoint, and platform-specific configuration in your own environment.

```dockerfile
FROM python:3.12-slim
RUN pip install "eplang[server]"
COPY . /app
WORKDIR /app
CMD ["epl", "serve", "website.epl"]
```
