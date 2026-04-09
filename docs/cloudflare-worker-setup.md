# High-Performance EPL AI Backend Deployment (Cloudflare Worker Setup)

Because it is **highly dangerous** to embed private API keys (like Groq or Gemini) directly into your public `playground.html` file (as anyone can steal them and exhaust your quota), we will deploy a secure **Cloudflare Worker**.

This Edge Server acts as an invisible, high-speed middleman. The playground talks to the Worker, and the Worker (which securely holds your keys) talks to Groq and Gemini.

### Why this architecture?
We have configured this specific Cloudflare Worker script to implement an **Intelligent Fallback Architecture**:
1. **Tier 1:** It instantly hits **Groq (Llama-3)** for lightning-fast generations.
2. **Tier 2:** If Groq hits a rate limit or goes offline, it automatically & seamlessly falls back to your **Google Gemini 1.5** key.

---

## 1. Create the Cloudflare Worker
1. Log into your [Cloudflare Dashboard](https://dash.cloudflare.com/) (Sign up for a free account if you don't have one).
2. Go to **Workers & Pages** -> **Create Application** -> **Create Worker**.
3. Name it `epl-gateway` and hit **Deploy**.
4. Click **Edit Code**.
5. Delete the default code and **paste the entirety of the following script** into the editor:

```javascript
/**
 * EPL Copilot Edge Proxy (Cloudflare Worker)
 * Securely proxies browser requests to Groq (Tier 1) and Google Gemini (Tier 2).
 */

export default {
  async fetch(request, env, ctx) {
    // 1. Handle CORS (Crucial for the web playground to communicate with this worker securely)
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*", // You can lock this to "https://abneeshsingh21.github.io" later 
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      const body = await request.json();
      const messages = body.messages || [];

      // SECURITY: Keys are retrieved securely from Cloudflare Settings -> Variables.
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
                  "Authorization": \`Bearer \${GROQ_KEY}\`
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
          
          // Map standard OpenAI message format to Gemini schema dynamically
          const geminiContents = messages.map(msg => ({
              role: msg.role === 'assistant' ? 'model' : 'user',
              parts: [{ text: msg.content }]
          }));

          const geminiResponse = await fetch(\`https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=\${GEMINI_KEY}\`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ contents: geminiContents })
          });
          
          if (!geminiResponse.ok) throw new Error("Gemini failed");
          const data = await geminiResponse.json();
          const replyText = data.candidates?.[0]?.content?.parts?.[0]?.text || "Error processing Gemini output";
          
          // Format Gemini back to standard OpenAI schema
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
};
```

6. Click **Deploy** in the top right corner.

---

## 2. Connect Your Playground to the Secure Gateway

Now that your Cloudflare Worker is humming, you need to point your Playground to it.

1. Cloudflare will give you a unique URL for your worker. It will look like:
   `https://epl-gateway.<your-cloudflare-username>.workers.dev`
2. Copy that URL.
3. Open `docs/playground.html`.
4. Go to **Line 796** (inside the `try { ... fetch(...) }` block).
5. **REPLACE** the old Pollinations URL with your securely deployed proxy:

**BEFORE:**
```javascript
const response = await fetch("https://text.pollinations.ai/openai", {
    method: "POST",
```

**AFTER:**
```javascript
const response = await fetch("https://epl-gateway.<your-cloudflare-username>.workers.dev", {
    method: "POST",
```

**That's it!** You now have a hyper-scalable, double-fallback AI Architecture that secures your API keys perfectly!
