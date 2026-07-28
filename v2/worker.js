// Cloudflare Worker（方案 B / 仓库版）：跨用户「已领数量」计数服务
// 不依赖 KV，直接用 GitHub API 把计数写回仓库里的 claims.json。
// GitHub Token 以「Worker 秘密 GH_TOKEN」形式注入，绝不出现在公开前端。
//
// 接口（与前端的约定保持一致）：
//   GET  /counts        -> { id: 已领数量 }   （读实时计数）
//   POST /claim  {id}   -> { id, claimed }    （该条 +1 并写回仓库）
//   GET  /             -> 健康检查
//
// 环境变量 / 秘密：
//   env.GH_TOKEN     GitHub PAT（Contents: write），用 `wrangler secret put GH_TOKEN` 设置
//   env.REPO_OWNER   仓库所有者，例如 MeetYou3311
//   env.REPO_NAME    仓库名，例如 ID.-ERA-9X
//   env.CLAIMS_PATH  计数文件名，例如 claims.json

const API = "https://api.github.com";

// 生产环境建议把 "*" 换成你的 GitHub Pages 源站，例如 "https://meetyou3311.github.io"
const ALLOW_ORIGIN = "*";

function cors(extra) {
  return Object.assign({
    "Access-Control-Allow-Origin": ALLOW_ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  }, extra || {});
}

// UTF-8 安全的 base64（GitHub 内容需 base64）
function b64encodeUtf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach(function (b) { bin += String.fromCharCode(b); });
  return btoa(bin);
}
function b64decodeUtf8(b64) {
  const bin = atob(b64);
  const bytes = Uint8Array.from(bin, function (c) { return c.charCodeAt(0); });
  return new TextDecoder().decode(bytes);
}

function ghHeaders(token) {
  return { "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json" };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors() });
    }

    const headers = { "Content-Type": "application/json; charset=utf-8" };
    const repoPath = "/repos/" + env.REPO_OWNER + "/" + env.REPO_NAME + "/contents/" + env.CLAIMS_PATH;
    const auth = ghHeaders(env.GH_TOKEN);

    // ---- GET /counts：返回实时计数 ----
    if (request.method === "GET" && url.pathname === "/counts") {
      try {
        const r = await fetch(API + repoPath, { headers: auth });
        if (r.status === 404) return new Response("{}", { headers: cors(headers) });
        if (!r.ok) throw new Error("github " + r.status);
        const j = await r.json();
        const text = b64decodeUtf8(j.content);
        return new Response(text, { headers: cors(headers) });
      } catch (e) {
        return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors(headers) });
      }
    }

    // ---- POST /claim：该条 +1 并写回仓库 ----
    if (request.method === "POST" && url.pathname === "/claim") {
      let id = null;
      try { const b = await request.json(); id = b && b.id; } catch (e) {}
      if (!id) {
        return new Response(JSON.stringify({ error: "missing id" }), { status: 400, headers: cors(headers) });
      }

      // 读取当前计数（带 sha，用于并发安全写回）
      const getR = await fetch(API + repoPath, { headers: auth });
      let claims = {};
      let sha = null;
      if (getR.ok) {
        const j = await getR.json();
        sha = j.sha;
        try { claims = JSON.parse(b64decodeUtf8(j.content)); } catch (e) {}
      } else if (getR.status !== 404) {
        return new Response(JSON.stringify({ error: "read failed " + getR.status }), { status: 500, headers: cors(headers) });
      }

      const next = (claims[id] || 0) + 1;
      claims[id] = next;

      const body = {
        message: "更新领取计数（跨用户）: " + id,
        content: b64encodeUtf8(JSON.stringify(claims, null, 2)),
      };
      if (sha) body.sha = sha;

      const putR = await fetch(API + repoPath, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, auth),
        body: JSON.stringify(body),
      });
      if (!putR.ok) {
        return new Response(JSON.stringify({ error: "write failed " + putR.status }), { status: 500, headers: cors(headers) });
      }
      return new Response(JSON.stringify({ id: String(id), claimed: next }), { headers: cors(headers) });
    }

    // ---- GET /：健康检查 ----
    if (request.method === "GET" && url.pathname === "/") {
      return new Response(JSON.stringify({ ok: true }), { headers: cors(headers) });
    }

    return new Response(JSON.stringify({ error: "not found" }), { status: 404, headers: cors(headers) });
  }
};
