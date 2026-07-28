// Cloudflare Worker：跨用户「已领数量」计数服务
// 仅做 KV 计数读写，不含任何写仓库的权限；公开前端只调用 /counts 与 /claim。
// KV 绑定名：CLAIM_KV

const PREFIX = "claim:";

// 生产环境请把 "*" 换成你的 GitHub Pages 源站，例如 "https://meetyou3311.github.io"
const ALLOW_ORIGIN = "*";

function cors(extra) {
  return Object.assign({
    "Access-Control-Allow-Origin": ALLOW_ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  }, extra || {});
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 预检
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors() });
    }

    const headers = { "Content-Type": "application/json; charset=utf-8" };

    // GET /counts -> { id: 已领数量 }
    if (request.method === "GET" && url.pathname === "/counts") {
      const out = {};
      const list = await env.CLAIM_KV.list({ prefix: PREFIX });
      for (const key of list.keys) {
        const id = key.name.slice(PREFIX.length);
        const v = await env.CLAIM_KV.get(key.name);
        out[id] = v ? parseInt(v, 10) : 0;
      }
      return new Response(JSON.stringify(out), { headers: cors(headers) });
    }

    // POST /claim  body: { id } -> { id, claimed }
    if (request.method === "POST" && url.pathname === "/claim") {
      let id = null;
      try { const body = await request.json(); id = body && body.id; } catch (e) {}
      if (!id) {
        return new Response(JSON.stringify({ error: "missing id" }), { status: 400, headers: cors(headers) });
      }
      const key = PREFIX + String(id);
      const cur = parseInt(await env.CLAIM_KV.get(key) || "0", 10);
      const next = cur + 1;
      await env.CLAIM_KV.put(key, String(next));
      return new Response(JSON.stringify({ id: String(id), claimed: next }), { headers: cors(headers) });
    }

    // GET / -> 健康检查
    if (request.method === "GET" && url.pathname === "/") {
      return new Response(JSON.stringify({ ok: true }), { headers: cors(headers) });
    }

    return new Response(JSON.stringify({ error: "not found" }), { status: 404, headers: cors(headers) });
  }
};
