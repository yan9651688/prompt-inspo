#!/usr/bin/env python3
"""为本地 images/ 生成网格用 WebP 缩略图，并回填各日 JSON 的 thumbs 字段。

缩略图命名：images/YYYY-MM-DD/foo.jpg → images/YYYY-MM-DD/foo.thumb.webp
已有且足够新的 thumb 会跳过。可重复运行。
"""
import argparse, json, os, re, sys, tempfile
from datetime import datetime, timezone

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow：apt install python3-pil 或 pip install Pillow", file=sys.stderr)
    sys.exit(1)

THUMB_MAX = 360  # 长边
WEBP_Q = 72


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)


def atomic_write(path, data: bytes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def thumb_rel(src_rel: str) -> str:
    base, ext = os.path.splitext(src_rel)
    if base.endswith(".thumb"):
        return src_rel
    return base + ".thumb.webp"


def make_thumb(src_abs: str, dest_abs: str) -> bool:
    if os.path.exists(dest_abs) and os.path.getmtime(dest_abs) >= os.path.getmtime(src_abs):
        return False
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    with Image.open(src_abs) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_MAX, THUMB_MAX * 3), Image.Resampling.LANCZOS)
        im.save(dest_abs, "WEBP", quality=WEBP_Q, method=4)
    return True


def process_day(path, root, dry=False):
    items = json.load(open(path, encoding="utf-8"))
    if not isinstance(items, list):
        return 0, 0
    made = updated = 0
    for it in items:
        imgs = it.get("images") or []
        thumbs = list(it.get("thumbs") or [])
        while len(thumbs) < len(imgs):
            thumbs.append("")
        changed = False
        for i, src in enumerate(imgs):
            if not src or src.startswith("http"):
                continue
            rel = thumb_rel(src)
            abs_src = os.path.join(root, src)
            abs_dst = os.path.join(root, rel)
            if not os.path.exists(abs_src):
                continue
            if not dry:
                if make_thumb(abs_src, abs_dst):
                    made += 1
            if thumbs[i] != rel:
                thumbs[i] = rel
                changed = True
        if changed:
            it["thumbs"] = thumbs
            updated += 1
    if updated and not dry:
        atomic_write(path, json.dumps(items, ensure_ascii=False, indent=1).encode("utf-8"))
    return made, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    data = os.path.join(a.root, "data")
    total_m = total_u = 0
    for f in sorted(os.listdir(data)):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f):
            continue
        m, u = process_day(os.path.join(data, f), a.root, a.dry)
        if m or u:
            log(f"{f}: thumbs_made={m} days_updated={u}")
        total_m += m; total_u += u
    if total_u and not a.dry:
        idx_path = os.path.join(data, "index.json")
        try:
            idx = json.load(open(idx_path, encoding="utf-8"))
        except Exception:
            idx = {"days": []}
        idx["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        atomic_write(idx_path, json.dumps(idx, ensure_ascii=False, indent=1).encode("utf-8"))
        log("已刷新 index.json updated")
    log(f"完成：新建缩略图 {total_m}，更新日文件条目 {total_u}")


if __name__ == "__main__":
    main()
