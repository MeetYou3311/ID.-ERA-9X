# ID. ERA 9X软件升级分享 · 文案分享站

一个轻量的内部文案分享网站：

- **访客免登录**：直接打开网站，浏览 / 搜索 / 分类筛选文案，一键复制。
- **复制即清除**：点击复制 → 弹窗确认 → 复制成功则该条文案从列表移除，避免他人重复领取。
- **文案不足提示**：剩余可用低于设定阈值时，前台自动显示告警横幅。
- **仅管理员可导入**：独立的管理入口（你独有），支持批量 / 单条导入、调节阈值、查看统计、恢复或删除文案。

技术栈：Python Flask + SQLite，零额外服务依赖，开箱即用。

---

## 快速开始

```bash
pip3 install -r requirements.txt
python3 app.py
```

启动后访问：

- 前台（访客）：http://127.0.0.1:5000
- 管理入口：http://127.0.0.1:5000/admin/login
  - 默认管理员账号：`admin` / `admin123`

> 首次启动会自动创建 `copybank.db` 数据库文件。

---

## 使用说明

### 访客（无需登录）
1. 打开前台首页，可输入关键词搜索，或点击分类标签筛选。
2. 找到需要的文案，点击「复制文案」按钮。
3. 弹出确认框「确定要复制这条文案吗？复制成功后该文案将从列表中移除」。
4. 确认后，文案内容写入剪贴板，该条文案即时从列表移除。
5. 当剩余可用文案低于阈值时，页面顶部出现「文案不足」提示。

### 管理员（导入文案）
1. 进入 `/admin/login` 登录。
2. **批量导入**：在文本框中每行粘贴一条文案；可指定统一分类；
   支持 `标题||内容` 格式（用 `||` 分隔）为每条单独命名。
3. **单条添加**：填写标题（可留空，自动截取内容前 20 字）、分类、内容。
4. **不足阈值**：设置「剩余 ≤ 该值」时前台提示不足（默认 10）。
5. **可用文案 / 已领取**：查看状态；可删除可用文案，或将已领取的恢复为可领取。
6. **修改密码**：更新管理员密码（重启后失效，建议用环境变量固化，见下）。

---

## 安全与部署建议

- **修改默认密码**：务必改掉 `admin123`。推荐用环境变量固化：
  ```bash
  export ADMIN_USERNAME=your_admin
  export ADMIN_PASSWORD=your_strong_pwd
  export SECRET_KEY=some-random-secret
  python3 app.py
  ```
- **生产环境**：当前使用 Flask 开发服务器，仅供内网/测试。正式部署请用 WSGI 服务器（如 gunicorn）：
  ```bash
  pip3 install gunicorn
  gunicorn -w 4 -b 0.0.0.0:5000 app:app
  ```
- **HTTPS**：浏览器的剪贴板 API 在 `https` 或 `localhost` 下才可用；非 localhost 的 http 环境会自动回退到 `execCommand` 复制方案。部署到公网请启用 HTTPS。
- 文案被领取后仅从前台列表移除（标记为 `taken`），管理员可在后台查看「已领取」记录并恢复，不会真正丢失数据。

---

## 方案 B：本机长期运行（无需任何云平台账号）

适合不想注册 GitHub / Render，又想让别人长期访问的场景。原理：在你的设备（电脑 / 小主机 / 树莓派）上常驻运行本应用，再用**免费隧道**把 `5000` 端口暴露到公网。

### 步骤
1. 在本机安装 Python 3.11+，并安装隧道客户端：
   - **cloudflared**（推荐，无需账号即可用临时隧道）：
     - Mac：`brew install cloudflared`
     - Windows：`winget install Cloudflare.cloudflared`
     - Linux：见 [官方文档](https://developers.cloudflare.com/cloudflared/get-started/)
   - 或 **ngrok**（免费账号可拿到固定子域名）：`winget install ngrok` / `brew install ngrok`，再 `ngrok config add-authtoken <你的token>`
2. 启动并开隧道（一键脚本，Mac/Linux）：
   ```bash
   bash start_with_tunnel.sh
   ```
   Windows 则分两步：先 `python app.py`，另开一个终端执行 `cloudflared tunnel --url http://localhost:5000`。
3. 终端会打印一个 `https://xxxx.trycloudflare.com` 的公网地址，把它发给别人即可访问。

### 关于「固定链接」
- **cloudflared 临时隧道**：每次重启 URL 都会变，需重新发送。
- **想要固定不变**：
  - cloudflared「命名隧道」（免费 Cloudflare 账号）：`cloudflared tunnel create <名>` → `cloudflared tunnel route dns <名> <子域>` → 用 `cloudflared tunnel run <名>` 常驻。
  - 或 ngrok 免费账号配置固定子域名：`ngrok http --url=你的名字.ngrok-free.app 5000`。
- 想完全自己掌控、URL 永不变：在路由器做端口转发 + 域名（DDNS），或用上面的云部署方案。

> 注意：本机方案依赖你的设备保持开机且网络连通；关机或断网时链接失效。若需「无人值守长期稳定」，优先选方案 A（云部署）。
