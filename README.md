# 易拓灵感 · AI 生图提示词

每日从 X（Twitter）精选公开分享的 AI 生图提示词：缩略图预览、按模型筛选（Midjourney / Nano Banana / GPT Image / Grok Imagine / Seedream / Flux …）、全文搜索、一键复制提示词、按日期无限滚动。

纯静态站点，无需构建：

```
index.html  app.js  styles.css
data/index.json            # 日期索引
data/YYYY-MM-DD.json       # 每日条目
images/YYYY-MM-DD/*.jpg    # ~480px 缩略图（同时保留原图远程地址 remote_images）
scripts/collect.py         # 采集脚本
```

每条数据：作者、原帖链接、模型、标题、原文提示词、本地缩略图、原图地址。只收录正文中**确实包含提示词**的帖子，并署名、链接原帖；版权归原作者。

## 本地预览

```bash
python3 -m http.server 8000   # 打开 http://localhost:8000
```

## 每日采集 / 新增一天

需要 X API v2 Bearer Token（recent search 权限）：

```bash
pip install pillow
export X_BEARER_TOKEN=你的token
python3 scripts/collect.py --api --since 2026-11-03     # 采集该日期(UTC)至今
```

也可以离线导入：把 X API 搜索结果原始 JSON 存进 `raw/`，然后

```bash
python3 scripts/collect.py --raw 'raw/*.txt'                    # 自动筛选
python3 scripts/collect.py --raw 'raw/*.txt' --ids 123,456      # 只收录人工精选的帖子
```

脚本按帖子 id 去重并合并到 `data/YYYY-MM-DD.json`，自动重建 `data/index.json`。建议自动筛选后人工过一遍再发布。

## 部署

把整个目录 rsync 到服务器静态目录（如 `/srv/prompt-inspo`），nginx 指向它即可：

```bash
rsync -av --exclude raw --exclude .git ./ root@服务器:/srv/prompt-inspo/
```

可用 cron 每天跑一次 collect.py + rsync。
