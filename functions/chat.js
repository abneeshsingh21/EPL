// ── Authoritative EPL syntax reference (derived from parser source) ──
const EPL_SYNTAX_REFERENCE = `
COMMENTS: Single-line comments use the Note: prefix or #.
  Note: This line is ignored
  # This line is also ignored

VARIABLES AND CONSTANTS: Use Create, Set, shorthand assignment, Remember, or Constant.
  Create name = "Ada"
  Create count as 3
  Set count to count + 1
  total = 10
  Remember welcome as "Hello"
  Constant PI = 3.14159
  Increase count by 1
  Decrease count by 1

OUTPUT AND INPUT: Say, Display, Print, Show, Ask, and Input.
  Say "Hello"
  Display "Total: " + total
  Ask "What is your name?" and store in name
  Input age with prompt "Age: "

CONTROL FLOW: If/Otherwise, While, Repeat, For, Match/When. Close with End.
  If score >= 90 Then / Otherwise / Otherwise If / End
  While retries > 0 / End
  Repeat 3 times / End
  For each item in items / End
  For i from 1 to 10 step 2 / End
  Match grade / When "A" / When "B" or "C" / Default / End

FUNCTIONS AND LAMBDAS: English and parenthesized forms. Arrow lambdas.
  Function greet takes name / Return "Hello, " + name / End
  Function add(a, b) / Return a + b / End
  Define Function buildApi with host and port / End
  Call greet with "Ada"  OR  greet("Ada")
  Create square = lambda x -> x * x

COLLECTIONS:
  Create items = [1, 2, 3]
  Create user = Map with name = "Ada" and role = "admin"
  Add "orange" to items

ERROR HANDLING: Try/Catch/Finally, Throw, Assert.
  Try / Catch error / Finally / End
  Throw "Something went wrong"
  Assert count > 0

FILE I/O:
  Write "Hello" to file "output.txt"
  Set data to Read file "output.txt"
  Append "more" to file "output.txt"

IMPORTS AND PYTHON BRIDGE:
  Import "helpers.epl" as Helpers
  Use python "json" as json_mod

CLASSES: Class User / Set name to "Anon" / Function greet / End / End
  Create user = new User()

ENUMS AND TERNARY:
  Enum Color Red, Green, Blue
  Set label = "big" if x > 10 otherwise "small"

WEB APPS:
  Create WebApp called myApp
  Route "/" shows / Page "Home" / Heading "Hi" / End / End
  Route "/api" responds with / Send json Map with ok = true / End
  Start myApp on port 8080

ASYNC: Async Function / Await / Spawn / Parallel For each
GUI: Window "Demo" 800 by 600 / Column / Label / Button / End / End
MISC: Wait 2 seconds / Exit / length(items) / keys(map) / type_of(42)
Built-ins need parens: length(items), keys(map), to_text(42)
`.trim();


export async function onRequestPost({ request, env }) {
    // 1. Handle CORS preflight
    if (request.method === "OPTIONS") {
        return new Response(null, {
            headers: {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        });
    }

    try {
        const body = await request.json();
        let messages = body.messages || [];

        // SECURITY: Keys must be injected via Cloudflare Pages Environment Variables!
        const GROQ_KEY = env.GROQ_KEY;
        const GEMINI_KEY = env.GEMINI_KEY;

        // ── Server-side syntax injection ─────────────────────────
        // Ensure the system message includes the authoritative syntax
        // reference so the AI always uses parser-valid EPL forms,
        // even if the client prompt drifts or is tampered with.
        if (messages.length > 0 && messages[0].role === 'system') {
            const existing = messages[0].content || '';
            if (!existing.includes('PARSER-GROUNDED')) {
                messages = [
                    {
                        role: 'system',
                        content: existing +
                            '\n\n--- AUTHORITATIVE EPL SYNTAX REFERENCE (PARSER-GROUNDED, SERVER-INJECTED) ---\n' +
                            EPL_SYNTAX_REFERENCE
                    },
                    ...messages.slice(1)
                ];
            }
        }

        let upstreamResponse;

        try {
            // ==============================
            // TIER 1: GROQ (Llama 3 8B)
            // ==============================
            const groqResponse = await fetch("https://api.groq.com/openai/v1/chat/completions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${GROQ_KEY}`
                },
                body: JSON.stringify({
                    messages: messages,
                    model: "llama3-8b-8192",
                    temperature: 0.2
                })
            });

            if (!groqResponse.ok) throw new Error("Groq failed");
            upstreamResponse = await groqResponse.json();

        } catch (groqError) {
            // ==============================
            // TIER 2: GEMINI (Fallback)
            // ==============================
            let systemInstruction = null;
            const geminiContents = [];
            
            for (const msg of messages) {
                if (msg.role === 'system') {
                    systemInstruction = { parts: [{ text: msg.content }] };
                } else {
                    const role = msg.role === 'assistant' ? 'model' : 'user';
                    // Gemini requires strictly alternating roles and no consecutive same roles
                    if (geminiContents.length > 0 && geminiContents[geminiContents.length - 1].role === role) {
                        geminiContents[geminiContents.length - 1].parts[0].text += "\\n\\n" + msg.content;
                    } else {
                        geminiContents.push({
                            role: role,
                            parts: [{ text: msg.content }]
                        });
                    }
                }
            }

            const geminiPayload = { contents: geminiContents };
            if (systemInstruction) {
                geminiPayload.system_instruction = systemInstruction;
            }

            const geminiResponse = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(geminiPayload)
            });

            if (!geminiResponse.ok) throw new Error("Gemini failed");
            const data = await geminiResponse.json();
            const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text || "Error processing Gemini output";

            upstreamResponse = {
                choices: [{ message: { content: replyText } }]
            };
        }

        return new Response(JSON.stringify(upstreamResponse), {
            headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        });

    } catch (error) {
        return new Response(JSON.stringify({ error: error.message || "All APIs Exhausted" }), {
            status: 500,
            headers: { "Access-Control-Allow-Origin": "*" }
        });
    }
}
