#!/usr/bin/env bash
# 学校机(SEEWO-PC,经 free.svipss.top:11538 隧道)上线后自动重部署 + 验证。
# 背景:v0.1.5 的 server 角色在 Windows exe 下必挂(pypinyin 词典未入包),
# v0.1.6 修复。学校机早晨开机时间不定 → 本脚本守株待兔。
# 用法: scripts/deploy/watch_school.sh <version>   (如 0.1.6)
# 日志: /tmp/school-deploy-<version>.log
set -u
V="${1:?usage: watch_school.sh <version>}"
LOG="/tmp/school-deploy-${V}.log"
SSH_OPTS="-i $HOME/.ssh/id_ed25519 -p 11538 -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
SCHOOL="hht@free.svipss.top"
EXE_LOCAL="/tmp/call-center-${V}-x64.exe"
SHA_LOCAL=""

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── 1. 等 Release 资产就绪并下载 ────────────────────────────────
log "waiting for release asset v${V} ..."
for i in $(seq 1 40); do
  if gh release download "v${V}" -p "call-center-${V}-x64.exe" -D /tmp --clobber 2>>"$LOG"; then
    break
  fi
  sleep 60
  [ "$i" = 40 ] && { log "FATAL: release asset never appeared"; exit 1; }
done
SHA_LOCAL=$(sha256sum "$EXE_LOCAL" | cut -d' ' -f1)
log "downloaded: $(basename "$EXE_LOCAL") sha256=${SHA_LOCAL:0:16}… size=$(stat -c%s "$EXE_LOCAL")"

# ── 2. 等学校机上线 ─────────────────────────────────────────────
log "waiting for school PC to come online ..."
while true; do
  if timeout 12 ssh $SSH_OPTS "$SCHOOL" "cmd.exe /c 'echo ONLINE'" 2>/dev/null | grep -q ONLINE; then
    break
  fi
  sleep 60
done
log "school PC is ONLINE"

# ── 3. 停旧进程(0.1.5 server 挂在错误窗,display 在跑)─────────
timeout 20 ssh $SSH_OPTS "$SCHOOL" "cmd.exe /c 'taskkill /f /im call-center.exe'" 2>&1 | tee -a "$LOG"
sleep 3

# ── 4. 直传最终路径(Temp 目录会吃文件,不走它)───────────────────
log "uploading exe ..."
scp -i "$HOME/.ssh/id_ed25519" -P 11538 -o StrictHostKeyChecking=accept-new \
    "$EXE_LOCAL" "$SCHOOL:C:/CallCenter/cc-new.exe" >>"$LOG" 2>&1 \
  && log "upload ok" || { log "FATAL: upload failed"; exit 1; }

# ── 5. 替换 + 哈希核验 ──────────────────────────────────────────
timeout 20 ssh $SSH_OPTS "$SCHOOL" "cmd.exe /c 'copy /Y C:\CallCenter\cc-new.exe C:\CallCenter\call-center.exe'" >>"$LOG" 2>&1
timeout 20 ssh $SSH_OPTS "$SCHOOL" "cmd.exe /c 'certutil -hashfile C:\CallCenter\call-center.exe SHA256'" 2>/dev/null | grep -iE '^[0-9a-f]{64}$' > /tmp/school-sha.txt
SHA_REMOTE=$(grep -ioE '^[0-9a-f]{64}$' /tmp/school-sha.txt | head -1 | tr 'A-F' 'a-f')
if [ "$SHA_REMOTE" != "$SHA_LOCAL" ]; then
  log "FATAL: hash mismatch local=$SHA_LOCAL remote=$SHA_REMOTE"; exit 1
fi
log "hash verified: ${SHA_REMOTE:0:16}…"

# ── 6. 装支援密钥(学校→家里的反向隧道用)────────────────────────
timeout 20 ssh $SSH_OPTS "$SCHOOL" "cmd.exe /c 'if not exist C:\Users\hht\.ssh mkdir C:\Users\hht\.ssh'" >>"$LOG" 2>&1
scp -i "$HOME/.ssh/id_ed25519" -P 11538 -o StrictHostKeyChecking=accept-new \
    "$HOME/.ssh/id_school_support" "$SCHOOL:C:/Users/hht/.ssh/id_support" >>"$LOG" 2>&1 \
  && log "support key installed" || log "WARN: support key install failed (non-fatal)"

# ── 7. 起服务(Interactive 计划任务,GUI 进程不随 ssh 会话死)────
cat > /tmp/cc-start-server.ps1 <<'PS1'
$a = New-ScheduledTaskAction -Execute "C:\CallCenter\call-center.exe" -Argument "--role server"
$p = New-ScheduledTaskPrincipal -UserId "hht" -LogonType Interactive
Register-ScheduledTask -TaskName "CC-Server-Now" -Action $a -Principal $p -Force | Out-Null
Start-ScheduledTask -TaskName "CC-Server-Now"
Write-Output "SERVER-STARTED"
PS1
cat > /tmp/cc-start-display.ps1 <<'PS1'
$a = New-ScheduledTaskAction -Execute "C:\CallCenter\call-center.exe" -Argument "--role display"
$p = New-ScheduledTaskPrincipal -UserId "hht" -LogonType Interactive
Register-ScheduledTask -TaskName "CC-Display-Now" -Action $a -Principal $p -Force | Out-Null
Start-ScheduledTask -TaskName "CC-Display-Now"
Write-Output "DISPLAY-STARTED"
PS1
scp -i "$HOME/.ssh/id_ed25519" -P 11538 -o StrictHostKeyChecking=accept-new \
    /tmp/cc-start-server.ps1 /tmp/cc-start-display.ps1 "$SCHOOL:C:/CallCenter/" >>"$LOG" 2>&1
timeout 30 ssh $SSH_OPTS "$SCHOOL" "powershell -ExecutionPolicy Bypass -File C:\CallCenter\cc-start-server.ps1" 2>&1 | grep -a STARTED | tee -a "$LOG"
timeout 30 ssh $SSH_OPTS "$SCHOOL" "powershell -ExecutionPolicy Bypass -File C:\CallCenter\cc-start-display.ps1" 2>&1 | grep -a STARTED | tee -a "$LOG"

# ── 8. 远端直测 8800(curl 跑在学校机上,不经本机转发)──────────
log "verifying 8800 on school PC ..."
OK=""
for i in $(seq 1 6); do
  sleep 5
  R=$(timeout 15 ssh $SSH_OPTS "$SCHOOL" \
        "cmd.exe /c 'curl -s -m 5 http://127.0.0.1:8800/api/bootstrap/status'" 2>/dev/null)
  log "attempt $i: $R"
  echo "$R" | grep -q '"version"' && OK=1 && break
done
if [ -n "$OK" ] && echo "$R" | grep -q "\"${V}\""; then
  log "SUCCESS: server role v${V} listening on 8800"
  exit 0
elif [ -n "$OK" ]; then
  log "PARTIAL: 8800 responds but version mismatch: $R"
  exit 2
else
  log "FAIL: 8800 never responded"
  exit 3
fi
