#!/usr/bin/env python3
"""灵感图鉴 · 每日采集脚本

从 X (Twitter) 搜索结果中挑出「真正附带提示词原文」的 AI 生图帖子，
下载缩略图并写入 data/YYYY-MM-DD.json 与 data/index.json。

两种输入方式：
  1) API 模式（推荐每日定时运行）：
       export X_BEARER_TOKEN=xxxx
       python3 scripts/collect.py --api --since 2026-11-02
  2) 离线模式：把 X API v2 搜索接口返回的原始 JSON（可多份，可带前缀杂讯）放进 raw/
       python3 scripts/collect.py --raw raw/*.txt [--ids id1,id2]

同一帖子按 id 去重，重复运行是安全的。
"""
import argparse, glob, io, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IMGS = os.path.join(ROOT, "images")

QUERIES = [
    '(prompt OR 提示词 OR プロンプト) ("nano banana" OR nanobanana OR midjourney OR seedream OR flux OR "grok imagine" OR "gpt image") has:images -is:retweet -is:reply',
    '("--ar" OR "--sref") has:images -is:retweet -is:reply',
    '("Prompt 👇" OR "Prompt below" OR "prompt:" OR "Prompt ⤵️") has:images -is:retweet -is:reply',
]

MODELS = [  # (显示名, 正则)
    ("Midjourney", r"midjourney|--sref|--ar \d|--v [78]|--stylize"),
    ("Nano Banana", r"nano ?banana|gemini"),
    ("GPT Image", r"gpt[- ]?image|chatgpt|gpt-?4o"),
    ("Grok Imagine", r"grok"),
    ("Seedream", r"seedream|即梦|豆包"),
    ("Flux", r"\bflux"),
    ("Qwen Image", r"qwen"),
    ("Ideogram", r"ideogram"),
]

MARKERS = [r"prompt below ?👇", r"prompt ?⤵️", r"prompt ?👇", r"本期 ?prompt", r"prompt ?[:：]", r"提示词 ?[:：]", r"プロンプト ?[:：]"]
TAIL = [r"\n\s*follow @\w+.*$", r"https://t\.co/\w+"]


def iter_json_blobs(text):
    dec = json.JSONDecoder(); i = text.find("{")
    while 0 <= i < len(text):
        try:
            obj, j = dec.raw_decode(text, i); yield obj; i = text.find("{", j)
        except ValueError:
            i = text.find("{", i + 1)


def full_text(p):
    return ((p.get("note_tweet") or {}).get("text") or p.get("text") or "").strip()


def extract_prompt(t):
    for m in MARKERS:
        mm = re.search(m, t, re.I)
        if mm:
            body = t[mm.end():]
            break
    else:
        if re.search(r"--(ar|sref|v|stylize)\b", t):
            body = t  # Midjourney 帖：整条就是 prompt
        else:
            return None
    for r in TAIL:
        body = re.sub(r, "", body, flags=re.I | re.S)
    body = body.strip(" \n|")
    if "…" in body[-3:]:
        return None  # 被截断
    return body if len(body) >= 40 else None


def detect_models(t):
    found = [n for n, r in MODELS if re.search(r, t, re.I)]
    return found or ["其他"]


def make_title(t, prompt):
    head = t.split(prompt[:30])[0] if prompt[:30] in t else ""
    line = next((l.strip() for l in (head or prompt).splitlines() if len(l.strip()) > 6), prompt)
    line = re.sub(r"https://t\.co/\w+|#\w+|@\w+", "", line).strip(" :：|-")
    return (line[:48] + "…") if len(line) > 48 else line


def thumb(url, dest):
    if os.path.exists(dest):
        return True
    try:
        from PIL import Image
        src = url + ("&" if "?" in url else "?") + "name=small" if "pbs.twimg.com" in url else url
        data = urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((480, 480 * 3))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
        return True
    except Exception as e:
        print("  ! 缩略图失败", url, e, file=sys.stderr)
        return False


def api_search(query, since):
    tok = os.environ["X_BEARER_TOKEN"]
    q = {"query": query, "max_results": 100, "start_time": since + "T00:00:00Z",
         "expansions": "attachments.media_keys,author_id", "media.fields": "url,preview_image_url,type",
         "user.fields": "username,name", "tweet.fields": "created_at,note_tweet,public_metrics"}
    url = "https://api.x.com/2/tweets/search/recent?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    return json.load(urllib.request.urlopen(req, timeout=60))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="*", default=[])
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--since", default=(datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"))
    ap.add_argument("--ids", default="", help="只收录这些帖子 id（逗号分隔，人工精选用）")
    ap.add_argument("--min-likes", type=int, default=0)
    a = ap.parse_args()

    blobs = []
    for f in [g for pat in a.raw for g in glob.glob(pat)]:
        blobs += list(iter_json_blobs(open(f, encoding="utf-8").read()))
    if a.api:
        for q in QUERIES:
            blobs.append(api_search(q, a.since))
    posts, media, users = {}, {}, {}
    for b in blobs:
        if not isinstance(b, dict):
            continue
        for p in b.get("data") or []:
            posts[p["id"]] = p
        inc = b.get("includes") or {}
        media.update({m["media_key"]: m for m in inc.get("media", [])})
        users.update({u["id"]: u for u in inc.get("users", [])})

    keep = set(filter(None, a.ids.split(",")))
    by_day = {}
    for p in posts.values():
        if keep and p["id"] not in keep:
            continue
        if (p.get("public_metrics") or {}).get("like_count", 0) < a.min_likes:
            continue
        t = full_text(p)
        prompt = extract_prompt(t)
        keys = (p.get("attachments") or {}).get("media_keys", [])
        imgs = [media[k].get("url") or media[k].get("preview_image_url") for k in keys if k in media]
        imgs = [u for u in imgs if u]
        if not prompt or not imgs:
            continue
        u = users.get(p.get("author_id"), {})
        handle = u.get("username", "unknown")
        day = p["created_at"][:10]
        local = []
        for n, url in enumerate(imgs[:4]):
            rel = f"images/{day}/{p['id']}_{n}.jpg"
            if thumb(url, os.path.join(ROOT, rel)):
                local.append(rel)
        if not local:
            continue
        by_day.setdefault(day, {})[p["id"]] = {
            "id": p["id"], "author": handle, "author_name": u.get("name", handle),
            "url": f"https://x.com/{handle}/status/{p['id']}", "created_at": p["created_at"],
            "models": detect_models(t), "title": make_title(t, prompt), "prompt": prompt,
            "images": local, "remote_images": imgs, "likes": (p.get("public_metrics") or {}).get("like_count", 0),
        }

    os.makedirs(DATA, exist_ok=True)
    for day, items in by_day.items():
        path = os.path.join(DATA, f"{day}.json")
        old = {e["id"]: e for e in json.load(open(path, encoding="utf-8"))} if os.path.exists(path) else {}
        old.update(items)
        out = sorted(old.values(), key=lambda e: e["created_at"], reverse=True)
        json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{day}: {len(out)} 条")
    days = []
    for f in sorted(glob.glob(os.path.join(DATA, "????-??-??.json")), reverse=True):
        es = json.load(open(f, encoding="utf-8"))
        days.append({"date": os.path.basename(f)[:10], "count": len(es),
                     "models": sorted({m for e in es for m in e["models"]})})
    json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "days": days},
              open(os.path.join(DATA, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("共", sum(d["count"] for d in days), "条 /", len(days), "天")


if __name__ == "__main__":
    main()
