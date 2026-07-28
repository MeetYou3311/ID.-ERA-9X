# ID. ERA 9X 软件升级分享 · 文案分享站（静态版）

一个纯静态的文案分享网站，部署在 GitHub Pages，**不依赖任何后端进程**，可长期稳定访问。

线上地址：
- 公开站（访客浏览 / 复制）：`https://meetyou3311.github.io/ID.-ERA-9X/`
- 管理后台：`https://meetyou3311.github.io/ID.-ERA-9X/admin.html`

## 架构

| 文件 | 作用 |
|------|------|
| `index.html` | 公开站页面。访客免登录，浏览 / 复制文案。**运行时通过 `fetch('data.json')` 读取数据**，不内嵌任何文案。 |
| `data.json` | 唯一的数据源（"数据库"）。包含 `COPY_DATA`（文案列表）和 `COPY_SETTINGS`（如低库存阈值）。 |
| `admin.html` | 独立管理后台。登录后通过 **GitHub Contents API 直接写回 `data.json`**，保存后 GitHub Pages 约 1–2 分钟自动重建，无需重新部署。 |

## 管理后台用法

1. 打开 `admin.html`。
2. 输入管理密码（见下方说明）+ 你的 GitHub Token（需对该仓库有 Contents 读写权限）。
3. 批量导入 / 单条添加 / 上传文件，设置低库存阈值，点「保存到 GitHub」即可实时更新线上文案。

> 管理密码：直接告知即可，**`admin123`**。
> GitHub Token 仅用于调用 GitHub API 写回数据，保存在你本机浏览器 `localStorage`，不会上传到任何第三方。

## 关于「复制即移除」

静态站点无法跨用户去重。复制后该条仅在**访客本机浏览器**（LocalStorage）隐藏，换设备 / 清缓存后仍会显示。若需严格跨用户去重，请用原 Flask 动态版（`app.py` + SQLite）。

## 安全提醒

- 管理后台使用 GitHub Token 写回数据，使用完毕后建议到 GitHub 撤销该 Token（Settings → Developer settings → Personal access tokens）。
- 公开站不含任何写接口，访客无法修改数据。
