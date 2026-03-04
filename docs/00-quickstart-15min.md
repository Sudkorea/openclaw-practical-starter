# 00. OpenClaw Quickstart (30-45분)

> **사전 조건**: OpenClaw가 이미 설치되어 있어야 합니다.
> 설치가 아직 안 되어 있다면 [GCP 비용/환경 세팅 가이드](./01-gcp-cost-setup.md)와 [Tailscale + VSCode 설정](./02-tailscale-vscode.md)를 먼저 완료하세요.

이 가이드는 OpenClaw를 처음 사용하는 사람이 설치 직후 다음 상태에 도달하는 것을 목표로 합니다:

- OpenClaw gateway와 설정 파일 정상 확인
- 첫 번째 에이전트 workspace 구성
- 에이전트에 명령 보내서 응답 확인
- Airlock 루프 동작 확인
- Cron job 등록 및 상태 확인

**예상 소요 시간**: 30-45분 (환경에 따라 다름)

---

## 목차

1. [시스템 상태 확인](#1-시스템-상태-확인-약-5분)
2. [설정 파일 검증](#2-설정-파일-검증-약-5분)
3. [에이전트 Workspace 구성](#3-에이전트-workspace-구성-약-10분)
4. [첫 번째 에이전트 명령 실행](#4-첫-번째-에이전트-명령-실행-약-5분)
5. [Airlock 시스템 확인](#5-airlock-시스템-확인-약-10분)
6. [Cron job 확인](#6-cron-job-확인-약-5분)
7. [성공 기준 요약](#7-성공-기준-요약)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. 시스템 상태 확인 (약 5분)

### 1-1. Gateway service 상태 확인

```bash
systemctl --user is-active openclaw-gateway.service
```

**정상 출력:**
```
active
```

**비정상 출력 예시:**
```
inactive
failed
```

비정상이면 아래 명령으로 재시작합니다:

```bash
systemctl --user restart openclaw-gateway.service
systemctl --user status openclaw-gateway.service
```

`status` 결과에서 `Active: active (running)` 이 보이면 정상입니다.

---

### 1-2. OpenClaw CLI 확인

```bash
openclaw status
```

**정상 출력 (예시):**
```
OpenClaw v2026.2.12
Gateway: running (pid 12345)
Agents: 3 active
Cron: 5 jobs loaded
```

출력 형식은 버전마다 조금씩 다를 수 있습니다. 핵심은 `Gateway: running` 또는 그에 준하는 정상 상태 메시지가 보이는 것입니다.

---

### 1-3. OpenClaw 기본 경로 확인

OpenClaw의 모든 설정과 데이터는 `~/.openclaw/` 아래에 있습니다. 경로가 존재하는지 확인합니다:

```bash
ls ~/.openclaw/
```

**정상 출력 (주요 항목):**
```
agents/
cron/
openclaw.json
repos/
workspace/
workspace-cron-agent/
```

`openclaw.json`이 없으면 설치가 완료되지 않은 것입니다. [GCP 비용/환경 세팅 가이드](./01-gcp-cost-setup.md)를 다시 확인하세요.

---

## 2. 설정 파일 검증 (약 5분)

### 2-1. 메인 설정 파일 JSON 유효성 검사

```bash
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && echo "OK: openclaw.json is valid"
```

**정상 출력:**
```
OK: openclaw.json is valid
```

오류가 나면 JSON이 깨진 것입니다. 백업 파일로 복구합니다:

```bash
ls ~/.openclaw/openclaw.json.bak*
# 가장 최근 백업을 확인한 후:
cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json
```

---

### 2-2. Cron jobs 설정 파일 검사

```bash
python3 -m json.tool ~/.openclaw/cron/jobs.json > /dev/null && echo "OK: jobs.json is valid"
```

**정상 출력:**
```
OK: jobs.json is valid
```

---

### 2-3. 설정 파일 핵심 값 확인

`openclaw.json`에 API key와 기본 메타 정보가 있는지 확인합니다:

```bash
python3 - <<'EOF'
import json, sys

with open(__import__('os').path.expanduser("~/.openclaw/openclaw.json")) as f:
    d = json.load(f)

meta = d.get("meta", {})
env = d.get("env", {})

print("version :", meta.get("lastTouchedVersion", "MISSING"))
print("ANTHROPIC_API_KEY:", "SET" if env.get("ANTHROPIC_API_KEY") else "MISSING")
print("wizard lastRunCommand:", d.get("wizard", {}).get("lastRunCommand", "MISSING"))
EOF
```

**정상 출력 (예시):**
```
version : 2026.2.12
ANTHROPIC_API_KEY: SET
wizard lastRunCommand: onboard
```

`ANTHROPIC_API_KEY: MISSING`이면 `openclaw config set-key` 또는 OpenClaw wizard를 다시 실행해야 합니다.

---

## 3. 에이전트 Workspace 구성 (약 10분)

### 3-1. Workspace 디렉토리 구조 이해

OpenClaw에서 각 에이전트는 자신의 workspace 폴더를 가집니다:

```
~/.openclaw/
├── workspace-cron-agent/    # cron 스케줄러 에이전트
├── workspace-study-agent/   # 학습 관리 에이전트
├── workspace-caine-agent/   # 메인 실행 에이전트
└── workspace-{이름}/        # 직접 만든 에이전트
```

각 workspace 안에는 에이전트의 역할/규칙/정체성 파일이 있습니다:

```bash
ls ~/.openclaw/workspace-cron-agent/
```

**정상 출력 (예시):**
```
AGENTS.md
HEARTBEAT.md
IDENTITY.md
SOUL.md
TOOLS.md
USER.md
logs/
scripts/
```

---

### 3-2. 첫 번째 에이전트 workspace 만들기

이 가이드에서는 `my-first-agent`라는 이름의 간단한 에이전트를 만들어봅니다.

```bash
mkdir -p ~/.openclaw/workspace-my-first-agent
```

**AGENTS.md 생성** (에이전트 역할/행동 규칙):

```bash
cat > ~/.openclaw/workspace-my-first-agent/AGENTS.md << 'EOF'
# AGENTS - my-first-agent

## Role
- 테스트 및 학습용 에이전트.
- 간단한 정보 조회, 파일 읽기/쓰기, 명령 실행 담당.

## Execution Rules
- 작업 시작 전 scope 확인.
- 완료 후 결과를 간결하게 보고.
- 중요 산출물은 Airlock에 기록.

## Output Policy
- 성공/실패 여부를 명확히 구분해서 보고.
- 에러 발생 시 원인과 시도한 해결책을 포함.
EOF
```

**IDENTITY.md 생성** (에이전트 정체성):

```bash
cat > ~/.openclaw/workspace-my-first-agent/IDENTITY.md << 'EOF'
# Identity

my-first-agent: 첫 번째 OpenClaw 에이전트. 학습/테스트 목적.
EOF
```

**SOUL.md 생성** (말투/태도):

```bash
cat > ~/.openclaw/workspace-my-first-agent/SOUL.md << 'EOF'
# Soul

- 간결하고 명확하게 응답.
- 불확실한 것은 확인하고 진행.
- 결과는 구조화된 형식으로 보고.
EOF
```

---

### 3-3. Workspace 생성 확인

```bash
ls -la ~/.openclaw/workspace-my-first-agent/
```

**정상 출력:**
```
total 20
drwxr-xr-x  2 user user 4096 Feb 18 10:00 .
drwxr-xr-x 35 user user 4096 Feb 18 10:00 ..
-rw-r--r--  1 user user  312 Feb 18 10:00 AGENTS.md
-rw-r--r--  1 user user   76 Feb 18 10:00 IDENTITY.md
-rw-r--r--  1 user user  120 Feb 18 10:00 SOUL.md
```

---

## 4. 첫 번째 에이전트 명령 실행 (약 5분)

### 4-1. 에이전트 세션 시작

OpenClaw UI (또는 CLI)에서 에이전트를 열고, 아래 명령을 입력합니다. 이 가이드에서는 기존에 이미 설정된 에이전트(예: `cron-agent` 또는 `caine-agent`)를 사용해도 됩니다.

OpenClaw에서 에이전트에게 말을 걸 때는 해당 에이전트 세션을 열고 메시지를 입력합니다.

---

### 4-2. 상태 확인 명령 테스트

에이전트 세션에서 다음을 입력합니다:

```
시스템 상태를 간단히 확인해줘. openclaw.json의 version과 현재 시간을 알려줘.
```

**정상 응답 예시:**
```
openclaw.json version: 2026.2.12
현재 시간 (UTC): 2026-02-18T01:00:00Z
상태: 정상
```

---

### 4-3. 파일 쓰기/읽기 테스트

에이전트 세션에서:

```
~/.openclaw/workspace-my-first-agent/ 에 test-output.txt 파일을 만들고,
"Hello from my-first-agent at {현재시각}" 내용을 써줘.
그리고 파일 내용을 다시 읽어서 확인해줘.
```

**정상 응답 예시:**
```
파일 생성 완료: ~/.openclaw/workspace-my-first-agent/test-output.txt
내용: Hello from my-first-agent at 2026-02-18T01:00:00Z
검증: 파일 읽기 성공, 내용 일치.
```

CLI에서도 직접 확인할 수 있습니다:

```bash
cat ~/.openclaw/workspace-my-first-agent/test-output.txt
```

---

### 4-4. 에이전트 응답 확인 기준

에이전트가 정상적으로 동작한다면:
- 명령을 이해하고 실행
- 결과를 보고 (성공/실패 명확히)
- 에러 시 원인 설명

응답이 없거나 `NO_REPLY`만 오면 [트러블슈팅](#8-트러블슈팅)을 확인하세요.

---

## 5. Airlock 시스템 확인 (약 10분)

Airlock은 에이전트 작업 산출물을 기록하고 분류하는 핵심 시스템입니다.

### 5-1. Airlock 폴더 구조 확인

Airlock은 Obsidian vault 안에 있습니다. 기본 경로:

```bash
ls ~/obsidian-vault/airlock/ 2>/dev/null \
  || ls ~/.openclaw/repos/obsidian-vault/airlock/ 2>/dev/null \
  || echo "airlock 경로를 확인하세요 ([Airlock-first 운영 전략](./07-airlock-first-ops.md) 참고)"
```

**정상 출력 (예시):**
```
AGENT_EXTENSION_TEMPLATE.md
README.md
daily/
index/
logs/
study_queue/
topic-shifts/
```

---

### 5-2. Airlock orchestrator 수동 실행

`airlock_orchestrator.py`는 airlock 폴더의 기록을 분류하고 index/summary를 생성합니다. 수동으로 실행해서 동작을 확인합니다.

스크립트 경로 확인:

```bash
ls ~/.openclaw/workspace-cron-agent/scripts/airlock_orchestrator.py 2>/dev/null \
  && echo "found" || echo "not found"
```

스크립트가 있으면 실행합니다:

```bash
python3 ~/.openclaw/workspace-cron-agent/scripts/airlock_orchestrator.py \
  --hours 24 \
  --retention-days 30
```

**정상 출력 (예시 JSON):**
```json
{
  "date": "2026-02-18",
  "generated_at_utc": "2026-02-18T01:00:00.000000+00:00",
  "sanitizer": {
    "returncode": 0,
    "stdout_tail": "{\"copiedFiles\": 44, \"skippedFiles\": 29, \"redactionHits\": 10}"
  },
  "record_count": 5,
  "records": [
    {
      "relative": "caine_orchestration-update_2026-02-16.md",
      "bucket": "ops",
      "mtime_utc": "2026-02-16T20:09:29.500518+00:00"
    }
  ],
  "ok": true
}
```

핵심 확인 항목:
- `"ok": true` 존재
- `sanitizer.returncode` = 0
- `record_count` > 0 (airlock에 기록이 있을 경우)

---

### 5-3. Daily/Index 산출물 확인

orchestrator 실행 후 산출물이 생성됐는지 확인합니다:

```bash
AIRLOCK_BASE=~/.openclaw/repos/obsidian-vault/airlock
TODAY=$(date +%Y-%m-%d)

echo "=== Daily ==="
ls "$AIRLOCK_BASE/daily/$TODAY/" 2>/dev/null || echo "(오늘 daily 없음 - 기록이 없으면 정상)"

echo "=== Index ==="
ls "$AIRLOCK_BASE/index/" 2>/dev/null | tail -5
```

**정상 출력 예시:**
```
=== Daily ===
finance.md
journal_input.md
kpi_snapshot.json
ops.md
study.md

=== Index ===
2026-02-17.json
2026-02-18.json
```

---

### 5-4. Index JSON 내용 확인

가장 최근 index JSON을 열어봅니다:

```bash
AIRLOCK_BASE=~/.openclaw/repos/obsidian-vault/airlock
TODAY=$(date +%Y-%m-%d)

python3 -m json.tool "$AIRLOCK_BASE/index/$TODAY.json" 2>/dev/null \
  | head -40 \
  || echo "(오늘 index 파일 없음)"
```

**정상 출력 예시:**
```json
{
    "date": "2026-02-18",
    "generated_at_utc": "2026-02-18T01:00:00.000000+00:00",
    "sanitizer": {
        "returncode": 0
    },
    "record_count": 5,
    "records": [
        {
            "relative": "example_task_2026-02-18.md",
            "bucket": "ops",
            "mtime_utc": "2026-02-18T00:30:00.000000+00:00",
            "excerpt": "# Example Task\n## TL;DR\n..."
        }
    ],
    "ok": true
}
```

---

### 5-5. Airlock에 첫 기록 남기기

Airlock 기록 형식을 익히기 위해 템플릿을 복사하고 테스트 기록을 만들어봅니다:

```bash
AIRLOCK_BASE=~/.openclaw/repos/obsidian-vault/airlock
TODAY=$(date +%Y-%m-%d)
TEMPLATE="$AIRLOCK_BASE/AGENT_EXTENSION_TEMPLATE.md"

# 템플릿이 있으면 복사, 없으면 기본 형식으로 생성
if [ -f "$TEMPLATE" ]; then
    cp "$TEMPLATE" "$AIRLOCK_BASE/my-first-agent_quickstart-test_$TODAY.md"
else
    cat > "$AIRLOCK_BASE/my-first-agent_quickstart-test_$TODAY.md" << EOF
# my-first-agent Quickstart Test ($TODAY)

## 0) TL;DR
- 목표: Quickstart 가이드 따라하기
- 현재 상태: 완료
- 핵심 결과: OpenClaw 기본 동작 확인

## 1) 실행 로그
- openclaw status 확인: OK
- openclaw.json 검증: OK
- 에이전트 workspace 생성: OK
- airlock 구조 확인: OK

## 2) 변경 파일
- ~/.openclaw/workspace-my-first-agent/ (신규)

## 3) 검증 결과
- Gateway: active
- JSON 유효성: OK

## 4) 다음 액션
- [GCP 비용/환경 세팅](./01-gcp-cost-setup.md) 검토
- 실제 에이전트 역할 정의
EOF
fi

echo "Airlock 기록 생성: $AIRLOCK_BASE/my-first-agent_quickstart-test_$TODAY.md"
```

---

## 6. Cron job 확인 (약 5분)

### 6-1. 등록된 Cron job 목록 확인

```bash
python3 - << 'EOF'
import json, os

jobs_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
with open(jobs_path) as f:
    data = json.load(f)

jobs = data.get("jobs", [])
print(f"총 job 수: {len(jobs)}")
print()

for job in jobs:
    jid     = job.get("id", "?")[:8]
    name    = job.get("name", "?")
    agent   = job.get("agentId", "?")
    enabled = job.get("enabled", False)
    state   = job.get("state", {})
    last_status = state.get("lastStatus", "unknown")
    errors  = state.get("consecutiveErrors", 0)

    status_icon = "ON " if enabled else "OFF"
    print(f"[{status_icon}] {name}")
    print(f"      agent={agent}  last={last_status}  errors={errors}  id={jid}...")
    print()
EOF
```

**정상 출력 예시:**
```
총 job 수: 5

[ON ] SOXL monitor (5m) via log_bot
      agent=cron-agent  last=ok  errors=0  id=d6bc446b...

[OFF] obsidian-vault rag-safe sanitizer
      agent=cron-agent  last=ok  errors=0  id=beecf5e5...

[ON ] nightly airlock orchestrator
      agent=cron-agent  last=ok  errors=0  id=a1b2c3d4...
```

---

### 6-2. Cron job 상태 해석

각 job의 `state` 필드를 해석하는 방법:

```bash
python3 - << 'EOF'
import json, os, datetime

jobs_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
with open(jobs_path) as f:
    data = json.load(f)

jobs = data.get("jobs", [])
enabled_jobs = [j for j in jobs if j.get("enabled")]
print(f"활성 job 수: {len(enabled_jobs)} / 전체 {len(jobs)}")

problem_jobs = [j for j in jobs if j.get("state", {}).get("consecutiveErrors", 0) > 0]
if problem_jobs:
    print("\n[경고] 연속 에러가 있는 job:")
    for j in problem_jobs:
        print(f"  - {j.get('name')}: {j['state']['consecutiveErrors']}회")
else:
    print("\n모든 job 에러 없음 (OK)")
EOF
```

**정상 출력:**
```
활성 job 수: 3 / 전체 5

모든 job 에러 없음 (OK)
```

---

### 6-3. 최근 Cron 실행 로그 확인

```bash
ls ~/.openclaw/cron/runs/ 2>/dev/null | sort | tail -5 \
  || echo "(runs 폴더 없음 또는 실행 기록 없음)"
```

실행 로그가 있으면 가장 최근 것을 확인합니다:

```bash
LATEST=$(ls -t ~/.openclaw/cron/runs/ 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    cat ~/.openclaw/cron/runs/"$LATEST" | head -30
fi
```

---

## 7. 성공 기준 요약

모든 단계를 완료했으면 아래 체크리스트를 확인합니다:

```bash
python3 - << 'CHECKEOF'
import json, os, subprocess

checks = []

# 1. Gateway service
result = subprocess.run(
    ["systemctl", "--user", "is-active", "openclaw-gateway.service"],
    capture_output=True, text=True
)
ok = result.stdout.strip() == "active"
checks.append(("Gateway service active", ok))

# 2. openclaw.json 유효성
try:
    with open(os.path.expanduser("~/.openclaw/openclaw.json")) as f:
        json.load(f)
    checks.append(("openclaw.json valid JSON", True))
except Exception as e:
    checks.append(("openclaw.json valid JSON", False))

# 3. ANTHROPIC_API_KEY 설정
try:
    with open(os.path.expanduser("~/.openclaw/openclaw.json")) as f:
        d = json.load(f)
    key = d.get("env", {}).get("ANTHROPIC_API_KEY", "")
    checks.append(("ANTHROPIC_API_KEY set", bool(key)))
except Exception:
    checks.append(("ANTHROPIC_API_KEY set", False))

# 4. cron/jobs.json 유효성
try:
    with open(os.path.expanduser("~/.openclaw/cron/jobs.json")) as f:
        json.load(f)
    checks.append(("cron/jobs.json valid JSON", True))
except Exception:
    checks.append(("cron/jobs.json valid JSON", False))

# 5. workspace-my-first-agent 존재
path = os.path.expanduser("~/.openclaw/workspace-my-first-agent")
checks.append(("my-first-agent workspace created", os.path.isdir(path)))

# 출력
print("=" * 50)
print("OpenClaw Quickstart 성공 기준 체크")
print("=" * 50)
passed = 0
for name, ok in checks:
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name}")
    if ok:
        passed += 1

print()
print(f"결과: {passed}/{len(checks)} 항목 통과")
if passed == len(checks):
    print("모든 항목 통과! Quickstart 완료.")
else:
    print("일부 항목 실패. 아래 트러블슈팅을 참고하세요.")
CHECKEOF
```

**완전 성공 시 출력:**
```
==================================================
OpenClaw Quickstart 성공 기준 체크
==================================================
[PASS] Gateway service active
[PASS] openclaw.json valid JSON
[PASS] ANTHROPIC_API_KEY set
[PASS] cron/jobs.json valid JSON
[PASS] my-first-agent workspace created

결과: 5/5 항목 통과
모든 항목 통과! Quickstart 완료.
```

---

## 8. 트러블슈팅

### Gateway가 inactive/failed 상태일 때

```bash
# 로그 확인
journalctl --user -u openclaw-gateway.service -n 50

# 재시작 시도
systemctl --user restart openclaw-gateway.service

# 재시작 후 상태 확인 (5초 대기)
sleep 5 && systemctl --user is-active openclaw-gateway.service
```

여전히 실패하면 포트 충돌 가능성이 있습니다:

```bash
# OpenClaw 기본 포트 사용 여부 확인 (일반적으로 4000번대)
ss -tlnp | grep -E "4000|18800"
```

---

### openclaw.json이 깨진 경우

```bash
# 백업 목록 확인
ls -lt ~/.openclaw/openclaw.json.bak* | head -10

# 가장 최근 백업으로 복구
LATEST_BAK=$(ls -t ~/.openclaw/openclaw.json.bak* | head -1)
echo "복구할 백업: $LATEST_BAK"
cp "$LATEST_BAK" ~/.openclaw/openclaw.json

# 복구 후 검증
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && echo "복구 성공"
```

---

### ANTHROPIC_API_KEY가 없거나 잘못된 경우

OpenClaw wizard를 통해 다시 설정합니다:

```bash
openclaw wizard
```

또는 직접 편집합니다 (편집 전 반드시 백업):

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-manual-$(date +%s)
# 이후 텍스트 에디터로 ~/.openclaw/openclaw.json 열어서
# "env" > "ANTHROPIC_API_KEY" 값을 올바른 키로 수정
```

---

### airlock_orchestrator.py를 찾을 수 없는 경우

```bash
# 스크립트 위치 탐색
find ~/.openclaw -name "airlock_orchestrator.py" 2>/dev/null
```

없으면 cron-agent workspace가 아직 설정되지 않은 것입니다. [Airlock-first 운영 전략](./07-airlock-first-ops.md)를 참고해서 설정하세요.

---

### 에이전트가 응답하지 않는 경우

1. Gateway가 실행 중인지 재확인:
   ```bash
   systemctl --user is-active openclaw-gateway.service
   ```

2. API key가 유효한지 확인:
   ```bash
   curl -s https://api.anthropic.com/v1/models \
     -H "x-api-key: $(python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.openclaw/openclaw.json'))); print(d['env']['ANTHROPIC_API_KEY'])")" \
     -H "anthropic-version: 2023-06-01" | python3 -m json.tool | head -5
   ```
   `{"data": [...]}` 형태가 오면 key는 유효합니다.

3. 에이전트 세션이 stuck된 경우 OpenClaw에서 해당 에이전트를 재시작합니다.

---

### Cron job에 연속 에러가 있는 경우

```bash
python3 - << 'EOF'
import json, os

with open(os.path.expanduser("~/.openclaw/cron/jobs.json")) as f:
    data = json.load(f)

for job in data["jobs"]:
    errors = job.get("state", {}).get("consecutiveErrors", 0)
    if errors > 0:
        print(f"문제 job: {job['name']}")
        print(f"  에러 횟수: {errors}")
        print(f"  job id: {job['id']}")
        print(f"  payload: {job['payload'].get('message', '')[:200]}")
        print()
EOF
```

에러가 있는 job의 `payload.message` (cron 실행 명령)를 확인하고, 해당 스크립트를 직접 실행해서 에러를 재현한 후 수정합니다.

---

## 다음 단계

Quickstart를 완료했다면 다음 순서로 심화 학습을 권장합니다:

| 문서 | 내용 | 권장 대상 |
|------|------|-----------|
| [GCP VM 비용 최적화](./01-gcp-cost-setup.md) | GCP VM 비용 최적화 | 클라우드 운영 중인 경우 |
| [Vertex AI + LiteLLM 연동](./03-vertex-litellm.md) | Vertex AI + LiteLLM 연동 | 비용 절감 원하는 경우 |
| [멀티에이전트 구조 설계](./06-multi-agent-architecture.md) | 멀티에이전트 구조 설계 | 에이전트 2개 이상 운영 계획 |
| [Airlock 일일 운영 루프](./07-airlock-first-ops.md) | Airlock 일일 운영 루프 | 작업 기록 자동화 원하는 경우 |
| [서브에이전트 팀 운영](./13-subagent-orchestration.md) | 서브에이전트 팀 운영 | 복잡한 작업 위임 구조 필요 시 |
| [프롬프트 세팅 전체 가이드](./14-openclaw-prompt-setup-and-tools.md) | 프롬프트 세팅 전체 가이드 | 에이전트 역할 세밀 조정 시 |

실전 운영 사례는 [내가 실제로 했던 것들](./99-what-i-did-real-world-log.md)를 참고하세요.
