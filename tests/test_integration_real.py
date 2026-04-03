"""
Real HTTP Integration Tests for EPL Web + Deploy

Tests with ACTUAL HTTP requests — not mocks.
Starts a real server, makes real network calls,
and validates real responses over the wire.

Tests EPL routes (page, json, action, parameterized, store/fetch, redirect)
through the WSGI adapter with a real wsgiref server.
"""
import sys, os, json, threading, time, io
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wsgiref.simple_server import make_server
from urllib.request import urlopen, Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from epl import ast_nodes as ast
from epl.web import EPLWebApp, store_add, _data_store
from epl.deploy import WSGIAdapter

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS: {name}")
    else:
        FAILED += 1
        print(f"  FAIL: {name} {detail}")



check.__test__ = False

# ═══════════════════════════════════════════════════════════
# Setup: EPL app with REAL routes (using AST nodes)
# ═══════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    app = EPLWebApp("IntegrationTest")
    app.rate_limit = 100
    app.cors_enabled = True
    app.cors_origins = "*"
    
    # Route 1: GET "/" — page with heading + text
    app.add_route("/", "page", [
        ast.PageDef("Home", [
            ast.HtmlElement("heading", ast.Literal("Welcome to EPL")),
            ast.HtmlElement("text", ast.Literal("This is a real page.")),
        ])
    ], method='GET')
    
    # Route 2: GET "/api/status" — JSON endpoint (FetchStatement)
    app.add_route("/api/status", "json", [
        ast.FetchStatement("items")
    ], method='GET')
    
    # Route 3: POST "/api/add" — action that stores form data
    app.add_route("/api/add", "action", [
        ast.StoreStatement("items", field_name="value"),
    ], method='POST')
    
    # Route 4: GET "/users/:id" — parameterized route
    app.add_route("/users/:id", "json", [], method='GET')
    
    # Route 5: GET "/greet" — another page route
    app.add_route("/greet", "page", [
        ast.PageDef("Greet", [
            ast.HtmlElement("heading", ast.Literal("Hello, World!")),
        ])
    ], method='GET')
    
    # Route 6: POST "/submit" — action with store + redirect
    app.add_route("/submit", "action", [
        ast.StoreStatement("submissions", field_name="name"),
        ast.SendResponse("redirect", ast.Literal("/thanks")),
    ], method='POST')
    
    # Route 7: GET "/thanks" — redirect target
    app.add_route("/thanks", "page", [
        ast.PageDef("Thanks", [
            ast.HtmlElement("heading", ast.Literal("Thank you!")),
        ])
    ], method='GET')
    
    adapter = WSGIAdapter(app)
    
    # ═══════════════════════════════════════════════════════════
    # Start real WSGI server
    # ═══════════════════════════════════════════════════════════
    server = make_server("127.0.0.1", 0, adapter)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    
    BASE = f"http://127.0.0.1:{server.server_port}"
    
    # No-redirect opener for testing 303
    class _NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise HTTPError(newurl, code, msg, headers, fp)
    
    no_redir_opener = build_opener(_NoRedirect)
    
    print("\n=== Real HTTP Integration Tests ===\n")
    
    # ━━━ 1. Health Check ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("--- Health Check ---")
    try:
        resp = urlopen(f"{BASE}/_health", timeout=5)
        data = json.loads(resp.read())
        check("Health returns 200", resp.status == 200)
        check("Status is healthy", data["status"] == "healthy")
        check("Has wsgi flag", data.get("wsgi") is True)
        check("Has uptime", "uptime_seconds" in data)
        check("Version is 7.0.0", data.get("version") == "7.0.0")
    except Exception as e:
        check("Health check", False, str(e))
    
    # ━━━ 2. Page Routes (real HTML generation) ━━━━━━━━━━━━━
    print("\n--- Page Routes ---")
    try:
        resp = urlopen(f"{BASE}/", timeout=5)
        html = resp.read().decode("utf-8")
        check("Home page returns 200", resp.status == 200)
        check("Home has text/html Content-Type", "text/html" in resp.headers.get("Content-Type", ""))
        check("Home contains heading text", "Welcome to EPL" in html, f"got: {html[:200]}")
        check("Home contains paragraph text", "real page" in html, f"got: {html[:200]}")
    except Exception as e:
        check("Home page", False, str(e))
    
    try:
        resp = urlopen(f"{BASE}/greet", timeout=5)
        html = resp.read().decode("utf-8")
        check("Greet page returns 200", resp.status == 200)
        check("Greet has heading", "Hello, World!" in html, f"got: {html[:200]}")
    except Exception as e:
        check("Greet page", False, str(e))
    
    # ━━━ 3. JSON Routes ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- JSON Routes ---")
    try:
        _data_store.clear()  # clean state
        resp = urlopen(f"{BASE}/api/status", timeout=5)
        data = json.loads(resp.read())
        check("JSON route returns 200", resp.status == 200)
        check("JSON Content-Type", "application/json" in resp.headers.get("Content-Type", ""))
        check("JSON has collection field", "collection" in data)
        check("Empty store returns count 0", data.get("count") == 0)
    except Exception as e:
        check("JSON route", False, str(e))
    
    # ━━━ 4. Action Routes + Data Store (POST form data) ━━━━
    print("\n--- Action Routes + Data Store ---")
    _data_store.clear()
    try:
        body = urllib.parse.urlencode({"value": "apple"}).encode()
        req = Request(f"{BASE}/api/add", data=body, method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = urlopen(req, timeout=5)
        check("POST add apple returns 200", resp.status == 200)
    
        body = urllib.parse.urlencode({"value": "banana"}).encode()
        req = Request(f"{BASE}/api/add", data=body, method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = urlopen(req, timeout=5)
        check("POST add banana returns 200", resp.status == 200)
    
        # Verify via JSON endpoint
        resp = urlopen(f"{BASE}/api/status", timeout=5)
        data = json.loads(resp.read())
        check("Store has 2 items", data.get("count") == 2, f"got: {data}")
        check("Items are apple,banana", data.get("items") == ["apple", "banana"], f"got: {data}")
    except Exception as e:
        check("Action + store", False, str(e))
    
    # JSON POST
    try:
        _data_store.clear()
        body = json.dumps({"value": "cherry"}).encode()
        req = Request(f"{BASE}/api/add", data=body, method="POST",
                      headers={"Content-Type": "application/json"})
        resp = urlopen(req, timeout=5)
        check("JSON POST returns 200", resp.status == 200)
        resp = urlopen(f"{BASE}/api/status", timeout=5)
        data = json.loads(resp.read())
        check("JSON POST stored cherry", "cherry" in str(data.get("items", [])), f"got: {data}")
    except Exception as e:
        check("JSON POST", False, str(e))
    
    # ━━━ 5. Parameterized Routes ━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Parameterized Routes ---")
    try:
        resp = urlopen(f"{BASE}/users/42", timeout=5)
        data = json.loads(resp.read())
        check("/users/42 returns 200", resp.status == 200)
        check("/users/42 is JSON", "application/json" in resp.headers.get("Content-Type", ""))
    except Exception as e:
        check("Param route /users/42", False, str(e))
    
    try:
        resp = urlopen(f"{BASE}/users/abc-def", timeout=5)
        check("/users/abc-def returns 200", resp.status == 200)
    except Exception as e:
        check("Param route /users/abc-def", False, str(e))
    
    # ━━━ 6. Redirect (303) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Redirect ---")
    try:
        body = urllib.parse.urlencode({"name": "Alice"}).encode()
        req = Request(f"{BASE}/submit", data=body, method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        no_redir_opener.open(req, timeout=5)
        check("Redirect returns 303", False, "should have raised")
    except HTTPError as e:
        check("Redirect returns 303", e.code == 303, f"got: {e.code}")
        check("Redirect Location is /thanks", e.headers.get("Location") == "/thanks",
              f"got: {e.headers.get('Location')}")
    except Exception as e:
        check("Redirect test", False, str(e))
    
    # ━━━ 7. CORS Preflight ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- CORS ---")
    try:
        req = Request(f"{BASE}/any-path", method="OPTIONS")
        resp = urlopen(req, timeout=5)
        check("OPTIONS returns 200", resp.status == 200)
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        check("CORS Allow-Origin is *", acao == "*", f"got: {acao}")
        acam = resp.headers.get("Access-Control-Allow-Methods", "")
        check("CORS Allow-Methods has GET", "GET" in acam)
        acah = resp.headers.get("Access-Control-Allow-Headers", "")
        check("CORS Allow-Headers has Content-Type", "Content-Type" in acah)
    except Exception as e:
        check("CORS preflight", False, str(e))
    
    # ━━━ 8. Security Headers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Security Headers ---")
    try:
        resp = urlopen(f"{BASE}/_health", timeout=5)
        resp.read()
        check("X-Content-Type-Options: nosniff", resp.headers.get("X-Content-Type-Options") == "nosniff")
        check("X-Frame-Options: SAMEORIGIN", resp.headers.get("X-Frame-Options") == "SAMEORIGIN")
        check("Referrer-Policy present", resp.headers.get("Referrer-Policy") is not None)
        check("Permissions-Policy present", resp.headers.get("Permissions-Policy") is not None)
    except Exception as e:
        check("Security headers", False, str(e))
    
    # ━━━ 9. Error Handling ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Error Handling ---")
    try:
        urlopen(f"{BASE}/does-not-exist", timeout=5)
        check("404 for unknown GET", False, "should have raised")
    except HTTPError as e:
        check("404 for unknown GET", e.code == 404)
        body = e.read().decode()
        check("404 body is styled HTML", "<!DOCTYPE html>" in body and "404" in body)
    
    try:
        body = b"x=1"
        req = Request(f"{BASE}/unknown-post", data=body, method="POST",
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        urlopen(req, timeout=5)
        check("404 for unknown POST", False)
    except HTTPError as e:
        check("404 for unknown POST", e.code == 404)
    
    # ━━━ 10. Concurrent Load (50 requests to page route) ━━
    print("\n--- Concurrent Load ---")
    try:
        def fetch_home(_):
            resp = urlopen(f"{BASE}/", timeout=5)
            resp.read()
            return resp.status
        with ThreadPoolExecutor(max_workers=25) as ex:
            results = list(ex.map(fetch_home, range(50)))
        ok = sum(1 for r in results if r == 200)
        check(f"50 concurrent page requests ({ok}/50)", ok == 50)
    except Exception as e:
        check("Concurrent load", False, str(e))
    
    # ━━━ 11. Large Body Rejection ━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Body Size Limit ---")
    try:
        req = Request(f"{BASE}/upload", method="POST",
                      headers={"Content-Length": str(20 * 1024 * 1024),
                               "Content-Type": "text/plain"})
        urlopen(req, timeout=5)
        check("Large body rejected (413)", False)
    except HTTPError as e:
        check("Large body rejected (413)", e.code == 413, f"got: {e.code}")
    except Exception:
        check("Large body rejected (413)", True, "(connection error = acceptable)")
    
    # ━━━ 12. Path Traversal ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Path Traversal ---")
    try:
        urlopen(f"{BASE}/static/../../etc/passwd", timeout=5)
        check("Path traversal blocked (403)", False)
    except HTTPError as e:
        check("Path traversal blocked (403)", e.code in (403, 404))
    
    # ━━━ 13. Content-Length Accuracy ━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Content-Length Accuracy ---")
    try:
        resp = urlopen(f"{BASE}/", timeout=5)
        body = resp.read()
        cl = int(resp.headers.get("Content-Length", -1))
        check("Content-Length matches body", cl == len(body), f"header={cl}, actual={len(body)}")
    except Exception as e:
        check("Content-Length accuracy", False, str(e))
    
    # ━━━ 14. Query String Handling ━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n--- Query Strings ---")
    try:
        resp = urlopen(f"{BASE}/_health?verbose=true", timeout=5)
        data = json.loads(resp.read())
        check("Query string doesn't break health", data["status"] == "healthy")
    except Exception as e:
        check("Query string handling", False, str(e))
    
    try:
        resp = urlopen(f"{BASE}/?page=1&sort=asc", timeout=5)
        html = resp.read().decode("utf-8")
        check("Query string doesn't break page route", "Welcome to EPL" in html)
    except Exception as e:
        check("Query string on page", False, str(e))
    
    # ━━━ 15. Thanks page (redirect target) works ━━━━━━━━━━
    print("\n--- Redirect Target ---")
    try:
        resp = urlopen(f"{BASE}/thanks", timeout=5)
        html = resp.read().decode("utf-8")
        check("/thanks page returns 200", resp.status == 200)
        check("/thanks has heading", "Thank you!" in html, f"got: {html[:200]}")
    except Exception as e:
        check("Redirect target", False, str(e))
    
    # ━━━ Cleanup ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    server.shutdown()
    
    # ━━━ Summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n{'='*50}")
    print(f"  Real HTTP Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    if FAILED == 0:
        print("  All tests passed!")
    else:
        print(f"  {FAILED} test(s) FAILED")
    print(f"{'='*50}\n")
    return FAILED == 0


def test_integration_real_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
