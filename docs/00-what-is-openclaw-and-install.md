# 00. OpenClaw란 무엇인가, 그리고 설치 방법

이 문서는 OpenClaw를 처음 접하는 개발자를 위한 개념 설명과 전체 설치 과정을 다룬다. 설치 완료 후 [OpenClaw Quickstart](./00-quickstart-15min.md)로 이어서 진행한다.

---

## 목차

1. [OpenClaw란 무엇인가](#1-openclaw란-무엇인가)
2. [핵심 개념 설명](#2-핵심-개념-설명)
3. [시스템 요구사항](#3-시스템-요구사항)
4. [단계별 설치 과정](#4-단계별-설치-과정)
5. [설치 후 검증](#5-설치-후-검증)
6. [기본 설정 개요](#6-기본-설정-개요)
7. [자주 발생하는 문제와 해결책](#7-자주-발생하는-문제와-해결책)

---

## 1. OpenClaw란 무엇인가

### 한 줄 정의

**OpenClaw**는 클라우드 VM에서 여러 AI 에이전트를 동시에 운영하는 **오케스트레이션 플랫폼**이다.

### 좀 더 구체적으로

기존에 AI 에이전트를 쓰는 방식은 대부분 이랬다:

- 터미널에서 Claude Code를 직접 실행한다.
- 작업이 끝나면 종료된다.
- 다음에 또 필요하면 다시 시작한다.
- 에이전트가 뭘 했는지 기록이 남지 않는다.
- 여러 에이전트가 협력하려면 수동으로 중재해야 한다.

OpenClaw는 이 모든 것을 자동화한다:

- **Gateway**가 항상 백그라운드에서 실행되면서 에이전트 요청을 처리한다.
- **Cron** 스케줄러로 에이전트가 정해진 시간에 자동으로 작업을 실행한다.
- **Airlock**이 모든 에이전트 산출물을 구조화해서 보관한다.
- **Agent-to-Agent 위임**으로 에이전트끼리 작업을 나눠서 처리한다.
- **Channel**을 통해 Discord 같은 외부 플랫폼에서 에이전트를 제어한다.

### 왜 "클라우드 VM"인가

- **Mac Mini 없이 24시간 운영**: 개인 컴퓨터를 항상 켜놓을 수 없다. GCP 같은 클라우드 VM은 월 $70-100 수준에서 24시간 안정적으로 실행된다.
- **비용 효율**: Vertex AI + GCP 무료 크레딧 조합이면 강력한 모델을 사실상 무료로 쓸 수 있다.
- **어디서나 접속**: Tailscale 네트워크로 카페, 사무실, 집 어디서든 동일한 환경에 접속한다.
- **확장성**: VM 스펙을 올리거나 여러 VM에 에이전트를 분산하는 것이 쉽다.

### OpenClaw vs 단순 CLI 툴

| 비교 항목 | 단순 CLI 실행 | OpenClaw |
|-----------|--------------|----------|
| 실행 방식 | 매번 수동으로 시작 | Gateway가 항상 대기 |
| 스케줄링 | crontab 등 별도 설정 | 내장 cron 스케줄러 |
| 멀티에이전트 | 불가능 | 기본 지원 (위임/협력) |
| 산출물 관리 | 파일이 흩어짐 | Airlock으로 중앙 집중 |
| 상태 모니터링 | 없음 | dashboard + 헬스체크 |
| LLM 선택 | 에이전트마다 고정 | 에이전트마다 다른 모델 |
| 외부 연동 | 없음 | Discord 등 채널 연동 |

---

## 2. 핵심 개념 설명

OpenClaw를 사용하기 전에 알아야 할 핵심 개념들이다. 처음엔 낯설어도 실제로 쓰다 보면 자연스럽게 익혀진다.

### 2-1. Gateway

**Gateway**는 OpenClaw의 중앙 서버다. 로컬 VM에서 `systemd` 서비스로 항상 실행된다.

```
역할:
- 에이전트 요청을 받아서 LLM API로 전달
- 에이전트 세션 상태 관리
- cron 스케줄 실행
- 채널(Discord 등) 이벤트 수신 및 라우팅
- Dashboard UI 제공 (브라우저에서 http://127.0.0.1:18789)
```

Gateway가 꺼지면 모든 에이전트가 멈춘다. `openclaw status`로 Gateway 상태를 항상 먼저 확인한다.

### 2-2. Agent

**Agent**는 역할이 할당된 AI 실행 단위다. 하나의 에이전트는 다음으로 구성된다:

```
에이전트 구성요소:
- 모델: 어떤 LLM을 쓸지 (Claude Haiku, Gemini Pro 등)
- Workspace: 역할 정의 파일이 있는 폴더
- Auth profile: API key 또는 OAuth 인증 방식
- Routing rules: 어떤 채널 메시지에 반응할지
```

에이전트는 `~/.openclaw/agents/[에이전트명]/` 에 설정이 저장되고, `~/.openclaw/workspace-[에이전트명]/` 에 역할 정의 파일이 저장된다.

**실제 운영 중인 에이전트 예시:**
- `claude-haiku`: 일상적인 보조 작업 (홈 어시스턴트 역할)
- `crone-agent`: 스케줄 관리, cron job 실행 중앙화
- `finance-agent`: 재무 데이터 분석 및 모니터링
- `study-agent`: 학습 큐 관리 및 요약 생성
- `vertex-coder`: Vertex AI Gemini 모델 기반 코딩 전담

에이전트 목록은 `openclaw agents list`로 확인한다.

### 2-3. Workspace

**Workspace**는 에이전트의 "인격"과 "역할 규칙"을 정의하는 파일들이 모인 폴더다.

```
~/.openclaw/workspace-[에이전트명]/
├── AGENTS.md      # 역할/행동 규칙/위임 규칙 (필수)
├── IDENTITY.md    # 에이전트 이름과 정체성 (필수)
├── SOUL.md        # 말투/태도/성격 (권장)
├── TOOLS.md       # 어떤 도구를 어떻게 쓸지 (선택)
├── USER.md        # 사용자 선호/컨텍스트 메모 (선택)
└── HEARTBEAT.md   # 주기적 자가 점검 규칙 (선택)
```

이 파일들은 에이전트가 대화를 시작할 때 "시스템 프롬프트"처럼 자동으로 읽힌다.

### 2-4. Cron

**Cron**은 에이전트가 정해진 시간에 자동으로 실행되도록 스케줄을 관리하는 시스템이다. Unix crontab과 개념은 같지만, 에이전트에게 자연어 메시지를 보내는 방식이다.

```json
// ~/.openclaw/cron/jobs.json 예시 (일부)
{
  "jobs": [
    {
      "name": "nightly airlock orchestrator",
      "schedule": "0 23 * * *",
      "agentId": "cron-agent",
      "payload": {
        "message": "airlock orchestrator를 실행해서 오늘 기록을 분류하고 index를 만들어줘"
      },
      "enabled": true
    }
  ]
}
```

Cron job 설정은 `openclaw cron` 명령어 또는 Dashboard UI에서 관리한다.

### 2-5. Airlock

**Airlock**은 에이전트 작업 산출물을 기록하고 분류하는 저장소 시스템이다.

```
~/.openclaw/repos/obsidian-vault/airlock/
├── daily/          # 일별 요약 (ops/finance/study/journal_input 분류)
├── index/          # 날짜별 JSON 인덱스
├── logs/           # 원시 실행 로그
├── study_queue/    # 학습 후보 목록
└── topic-shifts/   # 주제 전환/보류 기록
```

에이전트가 작업을 마치면 결과를 즉시 Airlock에 기록하도록 AGENTS.md에 규칙을 명시한다. 매일 밤 `airlock_orchestrator`가 이 기록들을 분류하고 요약을 생성한다.

Airlock 기록 파일 이름 형식: `{에이전트명}_{작업명}_{날짜}.md`

### 2-6. Handoff

**Handoff**는 에이전트 간 작업 위임 시 사용하는 표준 데이터 구조다. `schemas/handoff_packet.schema.json`에 정의되어 있다.

```json
// Handoff packet 필수 필드
{
  "objective": "무엇을 해야 하는가",
  "scope": {
    "files": ["관련 파일 목록"],
    "commands": ["실행 가능한 명령어"]
  },
  "constraints": {
    "runtime": "제한 시간",
    "security": "보안 규칙",
    "budget": "토큰/비용 한도"
  },
  "acceptance": {
    "tests": ["완료 검증 기준"],
    "lint": ["코드 품질 기준"]
  },
  "risk": "low | medium | high"
}
```

Handoff schema가 명확하지 않으면 에이전트들이 서로 책임을 떠넘기거나 중복 작업을 하는 상황이 발생한다.

### 2-7. LLM 프로바이더 연동 구조

OpenClaw는 여러 LLM 프로바이더를 동시에 지원한다. `~/.openclaw/openclaw.json`에 설정된다.

```
프로바이더 유형:
- anthropic: Claude Haiku/Sonnet 등 (직접 API)
- google-vertex: Gemini 2.5 Pro 등 (LiteLLM 프록시 경유)
- openai-codex: gpt-5.3-codex 등 (OAuth)
- deepseek: deepseek-reasoner/chat (직접 API)
- ollama: 로컬 모델 (직접 API, http://localhost:11434)
```

에이전트마다 다른 모델을 할당할 수 있다. 예를 들어 일상 보조 작업은 저렴한 Haiku, 복잡한 코딩은 Vertex Gemini Pro를 쓰는 방식이다.

---

## 3. 시스템 요구사항

### 하드웨어 (클라우드 VM 기준 권장)

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 2 vCPU | 2-4 vCPU |
| RAM | 8 GB | 16 GB (e2-highmem-2) |
| 디스크 | 50 GB | 100 GB |
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |

> 참고: 8GB RAM에서는 여러 에이전트를 동시에 실행하거나 LiteLLM 프록시를 함께 운영할 때 부족할 수 있다. e2-highmem-2 (16GB)를 권장한다. 자세한 내용은 [GCP 비용/환경 세팅](./01-gcp-cost-setup.md) 참고.

### 소프트웨어 사전 요구사항

| 소프트웨어 | 버전 | 용도 |
|-----------|------|------|
| Node.js | 18.x 이상 (22.x 권장) | OpenClaw CLI 실행 |
| npm | 9.x 이상 (10.x 권장) | 패키지 설치 |
| Python | 3.10 이상 (3.11 권장) | 스크립트 실행 |
| Git | 2.x | 레포지토리 관리 |
| systemd | - | Gateway 서비스 관리 (Linux) |

### 필수 외부 서비스 (하나 이상)

OpenClaw 자체는 LLM 모델을 내장하지 않는다. 최소 하나의 LLM 프로바이더가 필요하다.

| 프로바이더 | 준비물 | 비용 |
|-----------|--------|------|
| Anthropic (권장 시작점) | API key (`sk-ant-...`) | 유료 (사용량 과금) |
| Google Vertex AI | GCP 프로젝트 + 서비스 계정 | GCP 무료 크레딧 사용 가능 |
| OpenAI Codex | ChatGPT Pro 계정 (OAuth) | 월 구독 필요 |
| DeepSeek | API key | 저렴한 편 |
| Ollama | 별도 서버 또는 고사양 로컬 머신 | 무료 (하드웨어 비용) |

---

## 4. 단계별 설치 과정

### 개요

```
[1단계] Node.js 설치
     ↓
[2단계] OpenClaw CLI 설치
     ↓
[3단계] 초기 설정 마법사 실행 (onboard)
     ↓
[4단계] Gateway 서비스 등록 및 시작
     ↓
[5단계] 첫 번째 에이전트 설정
     ↓
[완료] openclaw status 확인
```

---

### 4-1단계: Node.js 설치

OpenClaw CLI는 Node.js로 작성되어 있다. Node.js 22.x LTS 버전을 설치한다.

```bash
# NodeSource 공식 스크립트로 Node.js 22.x 설치
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# 설치 확인
node --version
# 예상 출력: v22.22.0 이상

npm --version
# 예상 출력: 10.x.x 이상
```

**npm 전역 설치 경로 설정 (권장)**

기본적으로 npm 전역 패키지는 sudo 권한이 필요한 `/usr/lib/node_modules`에 설치된다. 이를 홈 디렉토리로 변경하면 sudo 없이도 전역 설치가 가능하다:

```bash
# npm 전역 패키지 경로를 ~/.npm-global 으로 변경
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global

# PATH에 추가 (현재 세션에서 즉시 적용)
export PATH=~/.npm-global/bin:$PATH

# 영구 적용을 위해 ~/.bashrc 또는 ~/.profile 에 추가
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

확인:
```bash
npm config get prefix
# 예상 출력: /home/[USER]/.npm-global
```

---

### 4-2단계: OpenClaw CLI 설치

```bash
npm install -g openclaw

# 설치 확인
openclaw --version
# 예상 출력: 2026.2.12 (또는 최신 버전)

# 도움말 확인
openclaw --help
```

**예상 출력 (--help):**
```
OpenClaw 2026.2.12 — AI agent orchestration platform

Usage: openclaw [options] [command]

Commands:
  agent       Run an agent turn via the Gateway
  agents      Manage isolated agents
  channels    Channel management
  cron        Cron scheduler
  gateway     Gateway control
  onboard     Interactive wizard to set up the gateway
  status      Show system status
  ...
```

설치 후 바이너리 위치 확인:
```bash
which openclaw
# 예상 출력: /home/[USER]/.npm-global/bin/openclaw
```

---

### 4-3단계: 초기 설정 마법사 (onboard)

`openclaw onboard` 명령은 대화형 마법사를 통해 핵심 설정을 단계적으로 완성한다.

```bash
openclaw onboard
```

마법사는 다음 항목들을 순서대로 설정한다:

**[마법사 진행 흐름]**

1. **LLM 프로바이더 선택 및 API key 입력**

   ```
   Which AI provider would you like to use?
   > Anthropic (Claude)
     Google Vertex AI
     OpenAI Codex
     Skip (set up later)
   ```

   Anthropic을 선택하면:
   ```
   Enter your Anthropic API key (sk-ant-...):
   > sk-ant-api03-xxxxxxxxxxxxxxxxxxxx
   ```

   API key는 [https://console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) 에서 발급받는다.

2. **기본 에이전트 생성**

   ```
   Create a default agent?
   > Yes (recommended)
     Skip
   ```

   Yes 선택 시 `claude-haiku` 에이전트가 기본 설정으로 생성된다.

3. **Gateway 서비스 등록**

   ```
   Set up Gateway as a system service?
   > Yes (recommended for always-on operation)
     No (start manually each time)
   ```

   Yes 선택 시 `systemd` 사용자 서비스로 Gateway가 등록된다.

4. **설정 완료 확인**

   ```
   Setup complete!
   Config saved to: ~/.openclaw/openclaw.json
   Gateway service: enabled
   Default agent: claude-haiku

   Run 'openclaw status' to verify everything is working.
   ```

**마법사를 건너뛰고 싶다면**

수동으로 `~/.openclaw/openclaw.json`을 작성할 수도 있지만, 처음에는 마법사를 사용하는 것이 실수를 줄이는 데 훨씬 좋다. 마법사 완료 후 설정을 수동으로 수정하는 방식을 권장한다.

---

### 4-4단계: Gateway 서비스 시작

**systemd 사용자 서비스로 등록된 경우 (onboard에서 Yes 선택):**

```bash
# 서비스 상태 확인
systemctl --user status openclaw-gateway.service

# 예상 출력:
# ● openclaw-gateway.service - OpenClaw Gateway
#      Loaded: loaded (/home/[USER]/.config/systemd/user/openclaw-gateway.service; enabled)
#      Active: active (running) since 2026-02-18 10:00:00 UTC; 1min ago
#      ...

# 서비스가 실행 중이 아니라면 시작
systemctl --user start openclaw-gateway.service

# VM 재시작 후 자동 시작 확인 (enabled 상태인지 확인)
systemctl --user is-enabled openclaw-gateway.service
# 예상 출력: enabled
```

**수동으로 Gateway를 시작하고 싶다면:**

```bash
# 포그라운드에서 실행 (테스트용)
openclaw gateway start

# 백그라운드에서 실행
openclaw gateway start --detach
```

**VM 재시작 후에도 자동 시작되도록 설정:**

```bash
# systemd 사용자 서비스의 lingering 활성화
# (SSH 로그아웃 후에도 서비스가 계속 실행되도록)
sudo loginctl enable-linger $USER

# 확인
loginctl show-user $USER | grep Linger
# 예상 출력: Linger=yes
```

> 중요: `loginctl enable-linger`가 없으면 SSH 세션을 종료할 때 사용자 서비스도 함께 멈춘다. 24시간 운영을 위해 반드시 설정한다.

---

### 4-5단계: 첫 번째 에이전트 설정

onboard 마법사에서 기본 에이전트가 생성됐다면 이 단계는 확인 용도다. 직접 에이전트를 만드는 경우에도 이 과정을 따른다.

**에이전트 목록 확인:**

```bash
openclaw agents list
```

**예상 출력:**
```
Agents:
- claude-haiku (default)
  Model: anthropic/claude-haiku-4-5-20251001
  Workspace: ~/.openclaw/workspace-haiku
```

**Workspace 파일 확인:**

```bash
ls ~/.openclaw/workspace-haiku/
# 또는 설정된 workspace 경로
```

**예상 출력:**
```
AGENTS.md
IDENTITY.md
SOUL.md
```

AGENTS.md가 없거나 비어 있다면 에이전트가 역할 규칙 없이 동작한다. `templates/` 폴더의 템플릿을 복사해서 채운다:

```bash
# 코드/개발 중심 에이전트라면
cp ~/.openclaw/common/templates/AGENT_TEMPLATE_CODE.md \
   ~/.openclaw/workspace-haiku/AGENTS.md

# 비코드 보조 작업 에이전트라면
cp ~/.openclaw/common/templates/AGENT_TEMPLATE_NONCODE.md \
   ~/.openclaw/workspace-haiku/AGENTS.md
```

---

### (선택) Tailscale 설치

Tailscale은 필수는 아니지만 원격 개발 환경을 훨씬 편하게 만든다. 클라우드 VM에서 OpenClaw를 운영한다면 강력히 권장한다.

```bash
# Tailscale 설치
curl -fsSL https://tailscale.com/install.sh | sh

# Tailscale 시작 및 인증
sudo tailscale up
# 출력된 URL을 브라우저에서 열어 계정 로그인

# Tailscale IP 확인
tailscale ip -4
# 예상 출력: 100.x.x.x

# 자동 시작 설정
sudo systemctl enable tailscaled
```

Tailscale 설치 후에는 GCP 방화벽에서 SSH 포트를 외부에 열지 않아도 된다. 자세한 내용은 [Tailscale + VSCode 설정](./02-tailscale-vscode.md) 참고.

---

## 5. 설치 후 검증

설치가 완료됐는지 아래 단계로 확인한다.

### 5-1. openclaw status 확인

```bash
openclaw status
```

**정상 출력 예시:**
```
OpenClaw status

Overview
┌─────────────────┬──────────────────────────────────────────────┐
│ Item            │ Value                                        │
├─────────────────┼──────────────────────────────────────────────┤
│ OS              │ linux 6.1.0-xxx (x64) · node 22.22.0        │
│ Gateway         │ local · ws://127.0.0.1:18789 · reachable    │
│ Gateway service │ systemd installed · enabled · running        │
│ Agents          │ 1 · default claude-haiku active              │
│ Sessions        │ 0 active                                     │
└─────────────────┴──────────────────────────────────────────────┘
```

확인 항목:
- `Gateway`: `reachable` 상태인지
- `Gateway service`: `enabled · running` 상태인지
- `Agents`: 에이전트가 1개 이상 표시되는지

### 5-2. 설정 파일 유효성 검사

```bash
# openclaw.json 유효성 검사
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && echo "OK: openclaw.json valid"

# cron jobs.json 유효성 검사
python3 -m json.tool ~/.openclaw/cron/jobs.json > /dev/null && echo "OK: jobs.json valid"
```

**정상 출력:**
```
OK: openclaw.json valid
OK: jobs.json valid
```

### 5-3. API key 연결 확인

Anthropic API key가 올바르게 설정됐는지 확인:

```bash
python3 - << 'EOF'
import json, os

config_path = os.path.expanduser("~/.openclaw/openclaw.json")
with open(config_path) as f:
    d = json.load(f)

version = d.get("meta", {}).get("lastTouchedVersion", "UNKNOWN")
api_key = d.get("env", {}).get("ANTHROPIC_API_KEY", "")

print(f"OpenClaw version : {version}")
print(f"ANTHROPIC_API_KEY: {'SET (' + api_key[:15] + '...)' if api_key else 'MISSING'}")

wizard = d.get("wizard", {})
print(f"Onboard status   : {wizard.get('lastRunCommand', 'not run')}")
EOF
```

**정상 출력 예시:**
```
OpenClaw version : 2026.2.12
ANTHROPIC_API_KEY: SET (sk-ant-api03-...)
Onboard status   : onboard
```

### 5-4. Gateway 헬스체크

```bash
openclaw health
```

**정상 출력:**
```
Gateway health: OK
Response time: 12ms
```

### 5-5. 첫 번째 에이전트 응답 테스트

에이전트가 실제로 응답하는지 확인한다. Dashboard UI에서 해도 되고, CLI에서 직접 메시지를 보내도 된다.

**CLI로 에이전트에게 메시지 보내기:**

```bash
# 기본 에이전트(default)에게 메시지 전송
openclaw agent --message "안녕. 현재 시각을 알려줘."
```

**정상 응답 예시:**
```
[claude-haiku] 안녕하세요! 현재 UTC 기준 시각은 2026-02-18 10:30:00 입니다.
```

응답이 오면 설치와 기본 설정이 완료된 것이다.

---

## 6. 기본 설정 개요

### 설정 파일 구조

```
~/.openclaw/
├── openclaw.json          # 핵심 설정 파일 (모델/인증/브라우저 등)
├── openclaw.json.bak-*    # 자동 백업 파일들
├── agents/                # 에이전트별 설정
│   └── [에이전트명]/
│       └── agent/         # 에이전트 내부 설정
├── cron/
│   └── jobs.json          # cron job 목록
├── workspace-[에이전트명]/  # 에이전트별 역할 정의 파일
│   ├── AGENTS.md
│   ├── IDENTITY.md
│   └── SOUL.md
└── repos/                 # 에이전트가 관리하는 레포지토리들
    └── obsidian-vault/    # Airlock 저장소
        └── airlock/
```

### openclaw.json 핵심 구조

```json
{
  "meta": {
    "lastTouchedVersion": "2026.2.12",
    "lastTouchedAt": "2026-02-18T10:00:00.000Z"
  },
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-api03-...",
    "GOOGLE_CLOUD_PROJECT": "my-gcp-project",
    "GOOGLE_CLOUD_LOCATION": "us-central1"
  },
  "models": {
    "providers": {
      "google-vertex": {
        "baseUrl": "http://localhost:4000/v1",
        "apiKey": "sk-litellm-proxy",
        "api": "openai-completions",
        "models": [...]
      }
    }
  },
  "browser": {
    "enabled": true,
    "headless": true
  }
}
```

> 주의: `openclaw.json`을 직접 수정할 때는 반드시 백업 후 진행한다. OpenClaw가 설정을 변경할 때 자동으로 `.bak-{설명}-{타임스탬프}` 형식의 백업을 만든다.

### 에이전트 추가 방법

새 에이전트를 추가하는 방법은 두 가지다:

**방법 1: Dashboard UI 사용**

브라우저에서 `http://127.0.0.1:18789` 접속 > Agents 탭 > "New Agent" 클릭

**방법 2: CLI 사용**

```bash
# 에이전트 추가 마법사
openclaw agents add

# 또는 openclaw.json 직접 편집 후 Gateway 재시작
# (수동 편집 시 JSON 유효성 반드시 검사)
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && \
  systemctl --user restart openclaw-gateway.service
```

### Cron job 추가 방법

```bash
# cron 마법사 실행
openclaw cron add
```

또는 `~/.openclaw/cron/jobs.json`을 직접 편집한다. 편집 후에는 Gateway를 재시작하거나 `openclaw cron reload` 명령을 실행한다.

---

## 7. 자주 발생하는 문제와 해결책

### 문제 1: `openclaw: command not found`

**증상:**
```
$ openclaw --version
-bash: openclaw: command not found
```

**원인:** npm 전역 설치 경로가 PATH에 없다.

**해결:**
```bash
# npm 전역 설치 경로 확인
npm config get prefix
# 출력 예: /home/[USER]/.npm-global

# 해당 경로의 bin을 PATH에 추가
export PATH=$(npm config get prefix)/bin:$PATH

# 영구 적용
echo 'export PATH=$(npm config get prefix)/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# 확인
which openclaw
openclaw --version
```

---

### 문제 2: Gateway가 시작되지 않는다

**증상:**
```
$ openclaw status
Error: Cannot connect to Gateway at ws://127.0.0.1:18789
```

**해결 단계:**

```bash
# 1. 서비스 상태 확인
systemctl --user status openclaw-gateway.service

# 2. 서비스 로그 확인
journalctl --user -u openclaw-gateway.service -n 50

# 3. 포트 충돌 확인
ss -tlnp | grep 18789

# 4. 수동 재시작
systemctl --user restart openclaw-gateway.service

# 5. 재시작 후 5초 대기 후 상태 확인
sleep 5 && systemctl --user is-active openclaw-gateway.service
```

서비스가 등록되지 않은 경우 (onboard를 건너뛴 경우):
```bash
openclaw gateway install
systemctl --user enable openclaw-gateway.service
systemctl --user start openclaw-gateway.service
```

---

### 문제 3: API key가 없거나 잘못됐다

**증상:**
```
Error: Invalid API key. Check your ANTHROPIC_API_KEY configuration.
```

**해결:**
```bash
# 현재 설정된 키 확인 (앞 20자만)
python3 -c "
import json, os
d = json.load(open(os.path.expanduser('~/.openclaw/openclaw.json')))
key = d.get('env', {}).get('ANTHROPIC_API_KEY', '')
print('Key:', key[:20] + '...' if key else 'MISSING')
"

# 키 재설정 (백업 자동 생성됨)
openclaw config set env.ANTHROPIC_API_KEY sk-ant-api03-새로운키값...

# 또는 마법사로 재설정
openclaw configure
```

Anthropic API key는 [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) 에서 발급받는다.

---

### 문제 4: openclaw.json이 손상됐다

**증상:**
```
SyntaxError: Unexpected token } in JSON at position 1234
```

**해결:**
```bash
# 백업 목록 확인 (최신 순)
ls -lt ~/.openclaw/openclaw.json.bak* | head -10

# 가장 최근 백업으로 복구
LATEST=$(ls -t ~/.openclaw/openclaw.json.bak* | head -1)
echo "복구할 파일: $LATEST"
cp "$LATEST" ~/.openclaw/openclaw.json

# 복구 후 검증
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && echo "복구 성공"

# Gateway 재시작
systemctl --user restart openclaw-gateway.service
```

---

### 문제 5: SSH 로그아웃 시 Gateway가 멈춘다

**증상:** SSH를 종료하면 에이전트가 더 이상 응답하지 않는다.

**원인:** `loginctl enable-linger`가 설정되지 않아 SSH 세션 종료 시 사용자 서비스도 종료된다.

**해결:**
```bash
sudo loginctl enable-linger $USER

# 확인
loginctl show-user $USER | grep Linger
# 예상 출력: Linger=yes
```

이후에는 SSH를 종료해도 Gateway와 에이전트가 계속 실행된다.

---

### 문제 6: Node.js 버전이 낮다

**증상:**
```
Error: The engine "node" is incompatible with this module.
Expected version ">=18.0.0". Got "16.x.x"
```

**해결:**
```bash
# 현재 Node.js 버전 확인
node --version

# nvm으로 버전 관리 (권장)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

nvm install 22
nvm use 22
nvm alias default 22

# 또는 NodeSource로 재설치
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# 버전 확인
node --version  # v22.x.x 이어야 함
```

---

### 문제 7: openclaw onboard가 중간에 실패했다

**해결:** onboard는 다시 실행해도 안전하다. 기존 설정이 있으면 덮어쓸지 묻는다.

```bash
# onboard 재실행
openclaw onboard

# 또는 마법사로 개별 설정
openclaw configure
```

---

## 설치 완료 후 다음 단계

설치와 기본 검증이 완료됐다면 다음 문서로 이동한다:

| 문서 | 내용 |
|------|------|
| [OpenClaw Quickstart](./00-quickstart-15min.md) | 설치 직후 첫 동작 확인 (30-45분) |
| [GCP VM 비용 최적화](./01-gcp-cost-setup.md) | GCP VM 비용 최적화 (클라우드 운영 시) |
| [Tailscale + VSCode 설정](./02-tailscale-vscode.md) | Tailscale + VSCode Remote 설정 |
| [Vertex AI + LiteLLM 연동](./03-vertex-litellm.md) | Vertex AI + LiteLLM 연동 (비용 절감) |
| [멀티에이전트 구조 설계](./06-multi-agent-architecture.md) | 멀티에이전트 구조 설계 |
| [Airlock 일일 운영 루프](./07-airlock-first-ops.md) | Airlock 일일 운영 루프 |

처음이라면 [OpenClaw Quickstart](./00-quickstart-15min.md)부터 시작하는 것을 권장한다.
