#!/bin/sh
# 定时采集入口：加锁防重叠，日志写入 /var/log/prompt-inspo-collect.log
ROOT=${ROOT:-/srv/prompt-inspo}
LOG=/var/log/prompt-inspo-collect.log
exec >>"$LOG" 2>&1
exec flock -n /run/prompt-inspo-collect.lock python3 "$ROOT/scripts/sync_source.py" --root "$ROOT" --days 7 \
  || echo "$(date -u +%FT%TZ) 跳过/失败（可能已有任务在运行）"
