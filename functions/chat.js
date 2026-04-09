export async function onRequestPost({ request, env }) {
    // 1. Handle CORS (Crucial for the web playground to communicate with this worker securely)
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
        const messages = body.messages || [];

        // SECURITY: Keys must be injected via Cloudflare Pages Environment Variables!
        // Do NOT hardcode your keys here, GitHub's Secret Scanner will correctly block the push!
        const GROQ_KEY = env.GROQ_KEY;
        const GEMINI_KEY = env.GEMINI_KEY;

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
            const geminiContents = messages.map(msg => ({
                role: msg.role === 'assistant' ? 'model' : 'user',
                parts: [{ text: msg.content }]
            }));

            const geminiResponse = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ contents: geminiContents })
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
