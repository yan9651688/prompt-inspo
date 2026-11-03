#!/usr/bin/env python3
"""灵感图鉴 · 定时同步「如水如画」公开数据

从 https://wangningashui-netizen.github.io/ai-prompts/ 的公开 JSON
（data/index.json → data/YYYY-MM-DD.json）拉取新条目，按 id / 原帖链接 / 提示词去重，
下载缩略图后原子写入本站 data/ 日文件并重建 data/index.json。不需要任何密钥。

用法: python3 scripts/sync_source.py [--root /srv/prompt-inspo] [--days 7]
"""
import argparse, json, os, re, sys, tempfile, urllib.request
from datetime import datetime, timezone

SRC = "https://wangningashui-netizen.github.io/ai-prompts/"
SRC_NAME = "如水如画"
UA = {"User-Agent": "Mozilla/5.0 (prompt-inspo sync)"}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def get(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def get_json(url):
    return json.loads(get(url).decode("utf-8"))


def atomic_write(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def dump(obj, indent=1):
    return json.dumps(obj, ensure_ascii=False, indent=indent).encode("utf-8")


def norm_prompt(p):
    return re.sub(r"\s+", " ", (p or "")).strip().lower()



def make_local_thumb(src_abs):
    """生成同目录 .thumb.webp；无 Pillow 时跳过。"""
    base, _ = os.path.splitext(src_abs)
    dest = base + ".thumb.webp"
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(src_abs):
        return dest
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(src_abs) as im:
            im = im.convert("RGB")
            im.thumbnail((360, 360 * 3))
            im.save(dest, "WEBP", quality=72, method=4)
        return dest
    except Exception as ex:
        log("  ! 缩略图失败", src_abs, ex)
        return None


def convert(e, date, root):
    author = e.get("author") or ""
    pid = str(e.get("id") or "")
    url = e.get("url") or (f"https://x.com/{author}/status/{pid}" if author and pid else "")
    created = date + "T00:00:00"
    m = re.match(r"(\d{2})-(\d{2}) (\d{2}):(\d{2})", e.get("time") or "")
    if m:
        y = int(date[:4])
        if m.group(1) == "12" and date[5:7] == "01":
            y -= 1
        created = f"{y}-{m.group(1)}-{m.group(2)}T{m.group(3)}:{m.group(4)}:00"
    locs, remotes, thumbs = [], [], []
    for im in e.get("images") or []:
        if isinstance(im, str):
            im = {"remote": im}
        remote = im.get("remote") or ""
        local = im.get("local") or ""
        path = ""
        if local:
            dest = os.path.join(root, "images", date, os.path.basename(local))
            rel = f"images/{date}/{os.path.basename(local)}"
            if os.path.exists(dest):
                path = rel
            else:
                try:
                    atomic_write(dest, get(SRC + local))
                    path = rel
                except Exception as ex:
                    log("  ! 图片下载失败", local, ex)
        path = path or remote
        thumb_rel = ""
        if path and not path.startswith("http"):
            t_abs = make_local_thumb(os.path.join(root, path))
            if t_abs:
                thumb_rel = os.path.relpath(t_abs, root).replace("\\", "/")
        if path:
            locs.append(path); remotes.append(remote or path)
            thumbs.append(thumb_rel or path)
    item = {
        "id": pid, "author": author, "author_name": e.get("author_name") or author, "url": url,
        "created_at": created, "models": [e.get("model") or e.get("group") or "未注明"],
        "title": e.get("title") or "", "note": e.get("note") or "", "prompt": e.get("prompt") or "",
        "images": locs, "thumbs": thumbs, "remote_images": remotes, "likes": int(e.get("likes") or 0), "source": SRC_NAME,
    }
    if not item["note"]:
        del item["note"]
    return item


def load_day(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d if isinstance(d, list) else []
    except FileNotFoundError:
        return []


def rebuild_index(data_dir):
    days = []
    for f in sorted(os.listdir(data_dir), reverse=True):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f):
            continue
        items = load_day(os.path.join(data_dir, f))
        if not items:
            continue
        models = sorted({m for i in items for m in i.get("models") or []})
        days.append({"date": f[:-5], "count": len(items), "models": models})
    idx = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "days": days}
    atomic_write(os.path.join(data_dir, "index.json"), dump(idx))
    return sum(d["count"] for d in days)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--days", type=int, default=7, help="只检查源站最近 N 天（0=全部）")
    a = ap.parse_args()
    data_dir = os.path.join(a.root, "data")

    # 现有数据的去重键
    seen_id, seen_url, seen_prompt = set(), set(), set()
    for f in os.listdir(data_dir):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f):
            for i in load_day(os.path.join(data_dir, f)):
                seen_id.add(str(i.get("id"))); seen_url.add(i.get("url")); seen_prompt.add(norm_prompt(i.get("prompt")))
    seen_url.discard(None); seen_url.discard(""); seen_prompt.discard("")

    src_idx = get_json(SRC + "data/index.json")
    dates = src_idx.get("dates") or []
    if a.days:
        dates = dates[: a.days]
    added = 0
    for d in dates:
        date, rel = d["date"], d.get("file") or f"data/{d['date']}.json"
        try:
            src = get_json(SRC + rel)
        except Exception as ex:
            log("! 拉取失败", rel, ex); continue
        new = []
        for e in src.get("entries") or []:
            pid = str(e.get("id") or "")
            prompt = norm_prompt(e.get("prompt"))
            if not pid or not prompt or pid in seen_id or prompt in seen_prompt:
                continue
            item = convert(e, date, a.root)
            if item["url"] in seen_url:
                continue
            seen_id.add(pid); seen_url.add(item["url"]); seen_prompt.add(prompt)
            new.append(item)
        if new:
            path = os.path.join(data_dir, f"{date}.json")
            items = load_day(path) + new
            items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
            atomic_write(path, dump(items))
            log(f"{date}: +{len(new)}")
            added += len(new)
    total = rebuild_index(data_dir)
    log(f"完成：新增 {added} 条，共 {total} 条")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        log("ERROR", repr(ex)); sys.exit(1)
