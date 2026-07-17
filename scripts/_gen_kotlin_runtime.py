"""One-shot generator: emit epl/kotlin_runtime.py from the extracted runtime
regions. Run once; the produced module is the checked-in source of truth.

The Android region strings are copied verbatim from the current, verified
runtime (via /tmp/_kt_regions.json), so the Android target renders byte-identical.
The console slots are JVM-native equivalents defined here.
"""

import json

R = json.load(open('/tmp/_kt_regions.json'))

CONSOLE_BASE64 = (
    "    fun base64Encode(text: String): String =\n"
    "        java.util.Base64.getEncoder().encodeToString(text.toByteArray(Charsets.UTF_8))\n"
    "    fun base64Decode(text: String): String =\n"
    "        String(java.util.Base64.getDecoder().decode(text), Charsets.UTF_8)"
)

CONSOLE_JSON = (
    "    fun jsonParse(s: Any?): Any? = JsonMini.parse(s as String)\n"
    "    fun jsonStringify(v: Any?): String = JsonMini.stringify(v)"
)

CONSOLE_DB = (
    "    // ─── SQLite bridge (db_* builtins) — unsupported on the console/JVM target ───\n"
    "    // The Android target backs these with android.database.sqlite; a bare JVM has no\n"
    "    // equivalent bundled. Fail loudly so db-backed EPL is caught, never silently wrong.\n"
    "    private fun noDb(): Nothing =\n"
    "        throw RuntimeException(\"Database builtins (db_*) are not supported on the console/JVM target; use the Android target or a server backend.\")\n"
    "    fun dbOpen(name: String): Any? = noDb()\n"
    "    fun dbExecute(db: Any?, sql: String, params: List<Any?> = emptyList<Any?>()): Unit = noDb()\n"
    "    fun dbQuery(db: Any?, sql: String, params: List<Any?> = emptyList<Any?>()): MutableList<Map<String, Any?>> = noDb()\n"
    "    fun dbQueryOne(db: Any?, sql: String, params: List<Any?> = emptyList<Any?>()): Map<String, Any?>? = noDb()\n"
    "    fun dbCount(db: Any?, table: String): Long = noDb()\n"
    "    fun dbCreateTable(db: Any?, table: String, columns: Any?): Boolean = noDb()\n"
    "    fun dbTables(db: Any?): MutableList<String> = noDb()\n"
    "    fun dbClose(db: Any?): Unit = noDb()"
)

CONSOLE_FILE = (
    "    // ─── File bridge (file_* builtins) — resolves against the working directory ───\n"
    "    private fun resolveFile(path: String): java.io.File = java.io.File(path)\n"
    "\n"
    "    fun fileExists(path: String): Boolean = resolveFile(path).exists()\n"
    "    fun fileDelete(path: String): Boolean = resolveFile(path).let { if (it.exists()) it.delete() else false }\n"
    "    fun fileRead(path: String): String = resolveFile(path).readText()\n"
    "    fun fileWrite(path: String, content: Any?): Boolean {\n"
    "        resolveFile(path).writeText(content?.toString() ?: \"\")\n"
    "        return true\n"
    "    }\n"
    "    fun fileAppend(path: String, content: Any?): Boolean {\n"
    "        resolveFile(path).appendText(content?.toString() ?: \"\")\n"
    "        return true\n"
    "    }\n"
    "    fun fileSize(path: String): Long = resolveFile(path).let { if (it.exists()) it.length() else 0L }"
)

# Hand-rolled JSON for the console target (no org.json on a bare JVM classpath).
# Emitted as a sibling object after EPLRuntime. Uses  for form-feed to keep
# this generator free of literal control characters.
CONSOLE_JSON_HELPER = (
    "\n"
    "/** Minimal JSON reader/writer for the console target (no external deps). */\n"
    "object JsonMini {\n"
    "    fun parse(s: String): Any? = Parser(s).parseValue()\n"
    "    private class Parser(val s: String) {\n"
    "        var i = 0\n"
    "        fun parseValue(): Any? {\n"
    "            skipWs()\n"
    "            return when (s[i]) {\n"
    "                '{' -> obj()\n"
    "                '[' -> arr()\n"
    "                '\"' -> str()\n"
    "                't' -> { expect(\"true\"); true }\n"
    "                'f' -> { expect(\"false\"); false }\n"
    "                'n' -> { expect(\"null\"); null }\n"
    "                else -> num()\n"
    "            }\n"
    "        }\n"
    "        fun obj(): LinkedHashMap<String, Any?> {\n"
    "            val m = LinkedHashMap<String, Any?>(); i++; skipWs()\n"
    "            if (s[i] == '}') { i++; return m }\n"
    "            while (true) {\n"
    "                skipWs(); val k = str(); skipWs(); i++\n"
    "                m[k] = parseValue(); skipWs()\n"
    "                if (s[i] == ',') { i++; continue }\n"
    "                i++; break\n"
    "            }\n"
    "            return m\n"
    "        }\n"
    "        fun arr(): ArrayList<Any?> {\n"
    "            val a = ArrayList<Any?>(); i++; skipWs()\n"
    "            if (s[i] == ']') { i++; return a }\n"
    "            while (true) {\n"
    "                a.add(parseValue()); skipWs()\n"
    "                if (s[i] == ',') { i++; continue }\n"
    "                i++; break\n"
    "            }\n"
    "            return a\n"
    "        }\n"
    "        fun str(): String {\n"
    "            val sb = StringBuilder(); i++\n"
    "            while (s[i] != '\"') {\n"
    "                if (s[i] == '\\\\') {\n"
    "                    i++\n"
    "                    when (s[i]) {\n"
    "                        'n' -> sb.append('\\n')\n"
    "                        't' -> sb.append('\\t')\n"
    "                        'r' -> sb.append('\\r')\n"
    "                        'b' -> sb.append('\\b')\n"
    "                        'f' -> sb.append('\\u000c')\n"
    "                        '/' -> sb.append('/')\n"
    "                        '\"' -> sb.append('\"')\n"
    "                        '\\\\' -> sb.append('\\\\')\n"
    "                        'u' -> { sb.append(s.substring(i + 1, i + 5).toInt(16).toChar()); i += 4 }\n"
    "                        else -> sb.append(s[i])\n"
    "                    }\n"
    "                } else sb.append(s[i])\n"
    "                i++\n"
    "            }\n"
    "            i++\n"
    "            return sb.toString()\n"
    "        }\n"
    "        fun num(): Any {\n"
    "            val start = i\n"
    "            while (i < s.length && (s[i].isDigit() || s[i] in \"+-.eE\")) i++\n"
    "            val t = s.substring(start, i)\n"
    "            return if (t.any { it in \".eE\" }) t.toDouble()\n"
    "                   else t.toLong().let { if (it in Int.MIN_VALUE..Int.MAX_VALUE) it.toInt() else it }\n"
    "        }\n"
    "        fun expect(w: String) { require(s.regionMatches(i, w, 0, w.length)); i += w.length }\n"
    "        fun skipWs() { while (i < s.length && s[i].isWhitespace()) i++ }\n"
    "    }\n"
    "    fun stringify(v: Any?): String {\n"
    "        val sb = StringBuilder(); write(v, sb); return sb.toString()\n"
    "    }\n"
    "    private fun write(v: Any?, sb: StringBuilder) {\n"
    "        when (v) {\n"
    "            null -> sb.append(\"null\")\n"
    "            is Boolean -> sb.append(v)\n"
    "            is Number -> sb.append(v.toString())\n"
    "            is CharSequence -> quote(v.toString(), sb)\n"
    "            is Map<*, *> -> {\n"
    "                sb.append('{'); var first = true\n"
    "                for ((k, vv) in v) {\n"
    "                    if (!first) sb.append(','); first = false\n"
    "                    quote(k.toString(), sb); sb.append(':'); write(vv, sb)\n"
    "                }\n"
    "                sb.append('}')\n"
    "            }\n"
    "            is Collection<*> -> {\n"
    "                sb.append('['); var first = true\n"
    "                for (it in v) { if (!first) sb.append(','); first = false; write(it, sb) }\n"
    "                sb.append(']')\n"
    "            }\n"
    "            else -> quote(v.toString(), sb)\n"
    "        }\n"
    "    }\n"
    "    private fun quote(s: String, sb: StringBuilder) {\n"
    "        sb.append('\"')\n"
    "        for (c in s) when (c) {\n"
    "            '\"' -> sb.append(\"\\\\\\\"\")\n"
    "            '\\\\' -> sb.append(\"\\\\\\\\\")\n"
    "            '\\n' -> sb.append(\"\\\\n\")\n"
    "            '\\r' -> sb.append(\"\\\\r\")\n"
    "            '\\t' -> sb.append(\"\\\\t\")\n"
    "            else -> sb.append(c)\n"
    "        }\n"
    "        sb.append('\"')\n"
    "    }\n"
    "}\n"
)


def pyquote(s):
    """Render a string as a Python triple-quoted literal safely."""
    # Use repr to guarantee round-trip fidelity, then wrap for readability.
    return repr(s)


TEMPLATE = '''"""Shared Kotlin EPLRuntime shim, assembled per target.

The runtime is one semantic core plus four platform-specific slots (base64,
json, db, file). The Android target fills them with android.* / org.json code
(byte-identical to the historically verified APK runtime); the console/JVM
target fills them with plain-JVM equivalents so transpiled Kotlin compiles and
runs with only kotlin-stdlib on the classpath.

Regenerate via scripts/_gen_kotlin_runtime.py if the extracted regions change.
"""

# ─── Shared semantic core (identical on every target) ───
_CORE_1 = {core1!r}

_CORE_2A = {core2a!r}

_CORE_2B = {core2b!r}

_MID = {mid!r}

_FOOTER = {footer!r}

# ─── Android platform slots (verbatim from the verified APK runtime) ───
_ANDROID_JSON = {a_json!r}

_ANDROID_BASE64 = {a_base64!r}

_ANDROID_DB = {a_db!r}

_ANDROID_FILE = {a_file!r}

# ─── Console/JVM platform slots ───
_CONSOLE_JSON = {c_json!r}

_CONSOLE_BASE64 = {c_base64!r}

_CONSOLE_DB = {c_db!r}

_CONSOLE_FILE = {c_file!r}

_CONSOLE_JSON_HELPER = {c_helper!r}


def _assemble(package, json_r, base64_r, db_r, file_r):
    header = (
        f"package {{package}}\\n\\n"
        "/**\\n"
        " * EPL Runtime Support for Android\\n"
        " * Generated by EPL Kotlin Generator v2.0\\n"
        " */\\n"
        "object EPLRuntime {{"
    )
    return "\\n".join(
        [header, _CORE_1, json_r, _CORE_2A, base64_r, _CORE_2B, db_r, _MID, file_r, _FOOTER]
    )


def android_runtime(package):
    """Byte-identical to the historically verified Android EPLRuntime."""
    return _assemble(package, _ANDROID_JSON, _ANDROID_BASE64, _ANDROID_DB, _ANDROID_FILE)


def console_runtime(package):
    """EPLRuntime for the console/JVM target (plain-JVM slots + JsonMini helper)."""
    body = _assemble(package, _CONSOLE_JSON, _CONSOLE_BASE64, _CONSOLE_DB, _CONSOLE_FILE)
    return body + "\\n" + _CONSOLE_JSON_HELPER
'''

out = TEMPLATE.format(
    core1=R['CORE_1'],
    core2a=R['CORE_2A'],
    core2b=R['CORE_2B'],
    mid=R['MID'],
    footer=R['FOOTER'],
    a_json=R['JSON'],
    a_base64=R['BASE64'],
    a_db=R['DB'],
    a_file=R['FILE'],
    c_json=CONSOLE_JSON,
    c_base64=CONSOLE_BASE64,
    c_db=CONSOLE_DB,
    c_file=CONSOLE_FILE,
    c_helper=CONSOLE_JSON_HELPER,
)

with open('epl/kotlin_runtime.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(out)
print('wrote epl/kotlin_runtime.py', len(out), 'chars')
