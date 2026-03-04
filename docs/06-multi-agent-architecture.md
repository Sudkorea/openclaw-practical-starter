# 06. 멀티에이전트 아키텍처 — 역할 분리와 협업 설계

> 핵심 원칙: "하나의 거대한 에이전트보다, 명확한 역할을 가진 작은 에이전트 팀이 낫다."
> 역할 분리는 비용을 낮추고, 실패를 격리하고, 확장을 쉽게 만든다.

---

## 1. 철학 — 왜 역할을 분리하는가

### 1-1. 단일 에이전트의 문제

하나의 에이전트에 모든 것을 맡기면 다음 문제가 생긴다.

```
[거대한 단일 에이전트]
  - 금융 모니터링도 함
  - 코드 리뷰도 함
  - 학습 큐 관리도 함
  - 딜 감시도 함
  - 일정 관리도 함

결과:
  - SYSTEM PROMPT가 수백 줄 → 모순 지시 발생
  - 하나가 실패하면 전체 중단
  - 컨텍스트 윈도우 초과 빈번
  - 비용 폭증 (모든 작업이 무거운 컨텍스트를 공유)
  - 책임 소재 불명확
```

### 1-2. 역할 분리의 이점

```
[분리된 에이전트 팀]

  cron-agent (오케스트레이터)
      │
      ├── finance-agent  → 금융만 담당
      ├── study-agent    → 학습만 담당
      ├── deals-agent    → 딜 감시만 담당
      ├── caine-agent    → 코드 실행만 담당
      └── voice-agent    → 음성만 담당

결과:
  - 각 SYSTEM PROMPT는 짧고 명확
  - 하나가 실패해도 나머지는 정상 동작
  - 컨텍스트가 격리되어 토큰 비용 절감
  - 역할 추가/제거가 쉬움
  - 책임 소재 명확
```

### 1-3. 핵심 설계 원칙

| 원칙 | 내용 |
|------|------|
| 단일 책임 | 에이전트 하나는 하나의 도메인만 |
| 계약 기반 통신 | handoff 패킷 스키마 준수 |
| 실패 격리 | 한 에이전트의 실패가 전체에 전파되지 않음 |
| Airlock 우선 기록 | 모든 결과를 Airlock에 기록한 후 다음 단계 |
| 최소 컨텍스트 | 에이전트는 자기 역할에 필요한 정보만 포함 |

---

## 2. 에이전트 유형

OpenClaw 멀티에이전트 시스템에서 에이전트는 크게 세 가지 유형으로 분류된다.

### 2-1. 오케스트레이터 (Orchestrator)

**역할**: 전체 시스템의 흐름을 제어한다. 일정을 관리하고, 작업을 도메인 에이전트에 위임하고, 실패를 탐지해서 에스컬레이션한다.

**특성**:
- 스케줄(cron)로 기동
- 도메인 로직을 직접 수행하지 않음 (위임만 함)
- 전체 시스템 상태를 파악
- 실패 정책을 집행

**대표 에이전트**: `cron-agent`

```
cron-agent 하루 일과 예시:

08:55  → 모든 서브에이전트 상태 확인 (health check)
09:00  → finance-agent 기동 (일일 예산 보고)
12:00  → deals-agent 기동 (점심 딜 스캔)
18:00  → study-agent 기동 (저녁 복습 큐 준비)
22:00  → caine-agent 기동 (일일 코드 정리)
23:55  → airlock-classifier 기동 (야간 분류)
00:05  → 당일 실패 항목 집계 → Discord 보고
```

### 2-2. 도메인 에이전트 (Domain Agent)

**역할**: 특정 도메인의 전문가다. 오케스트레이터로부터 handoff 패킷을 받아 도메인 특화 작업을 수행하고 결과를 Airlock에 기록한다.

**특성**:
- 오케스트레이터 또는 이벤트로 기동
- 자기 도메인 파일/API에만 접근
- 결과를 Airlock에 기록하고 오케스트레이터에 완료 보고
- 도메인 외 요청은 즉시 라우팅

**대표 에이전트**: `finance-agent`, `study-agent`, `deals-agent`, `voice-agent`

### 2-3. 실행자 (Executor)

**역할**: 코드 실행, 파일 조작, 외부 명령 등 "손"이 필요한 작업을 담당한다. 판단은 하지 않고 실행만 한다.

**특성**:
- 다른 에이전트로부터 구체적인 명령을 받아 실행
- 실행 결과(stdout, stderr, exit code)를 Airlock에 기록
- 실패 시 즉시 오케스트레이터에 보고
- 보안 제약이 가장 엄격함 (실행 권한 보유)

**대표 에이전트**: `caine-agent` (코드 실행 전담)

---

## 3. 에이전트 통신 패턴

에이전트 간 통신은 크게 세 가지 패턴을 따른다.

### 3-1. 위임 (Delegation)

오케스트레이터가 도메인 에이전트에 작업을 넘기는 패턴.

```
cron-agent
    │
    │  handoff_packet {
    │    objective: "오늘 학습 큐 생성",
    │    scope: { files: ["/airlock/daily/2026-02-18/"] },
    │    acceptance: { output_file: "/airlock/study_queue/2026-02-18.json" },
    │    risk: "low"
    │  }
    │
    ▼
study-agent
    │
    │  [작업 수행]
    │
    ▼
Airlock 기록 + 완료 보고
```

### 3-2. 파이프라인 (Pipeline)

에이전트 A의 출력이 에이전트 B의 입력이 되는 순차 패턴.

```
airlock-classifier
    │
    │  분류 완료 → index/2026-02-18.json 생성
    │
    ▼
study-agent
    │
    │  index 파일 읽어서 study_candidate: true 항목 추출
    │
    ▼
study_queue/2026-02-18.json 생성
    │
    ▼
Discord 복습 알림 발송
```

### 3-3. 이벤트 기반 (Event-driven)

외부 이벤트(웹훅, 파일 변경, API 알림)를 받아 에이전트를 기동하는 패턴.

```
GitHub PR 생성 이벤트
    │
    ▼
웹훅 수신 스크립트
    │
    │  handoff_packet {
    │    objective: "PR #42 코드 리뷰",
    │    scope: { files: ["changed files list"] },
    │    risk: "medium"
    │  }
    │
    ▼
caine-agent (코드 리뷰 수행)
    │
    ▼
review-agent (리뷰 코멘트 작성)
    │
    ▼
GitHub PR 코멘트 게시
```

---

## 4. Handoff 패킷 상세

handoff 패킷은 에이전트 간 통신의 계약서다. 스키마는 `schemas/handoff_packet.schema.json`에 정의되어 있다.

### 4-1. 필수 필드

```json
{
  "objective": "string — 작업 목표를 한 문장으로",
  "scope": {
    "files": ["처리할 파일 경로 목록"],
    "commands": ["허용된 명령어 목록"]
  },
  "constraints": {
    "runtime": "최대 실행 시간 (예: 5min)",
    "security": "보안 제약 (예: no network calls)",
    "style": "코드 스타일 규칙",
    "budget": "토큰 예산 수준 (low/medium/high)"
  },
  "acceptance": {
    "tests": "완료 조건: 테스트",
    "lint": "완료 조건: 린트",
    "manual": "완료 조건: 수동 확인"
  },
  "risk": "low | medium | high"
}
```

### 4-2. 실제 사용 예시

#### 예시 1: 학습 큐 생성 위임

```json
{
  "objective": "2026-02-18 airlock daily 기록에서 학습 후보를 추출하여 study_queue에 저장",
  "scope": {
    "files": ["/airlock/daily/2026-02-18/"],
    "commands": []
  },
  "constraints": {
    "runtime": "5min",
    "security": "read-only on source files",
    "style": "append-only on study_queue",
    "budget": "low"
  },
  "acceptance": {
    "tests": "",
    "lint": "",
    "manual": "/airlock/study_queue/2026-02-18.json 생성 확인"
  },
  "risk": "low"
}
```

#### 예시 2: 코드 실행 위임

```json
{
  "objective": "api/routes/users.py에 입력 검증 로직 추가 및 테스트 통과 확인",
  "scope": {
    "files": [
      "api/routes/users.py",
      "api/tests/test_users.py"
    ],
    "commands": [
      "pytest api/tests/test_users.py -q",
      "ruff check api/routes/users.py"
    ]
  },
  "constraints": {
    "runtime": "10min",
    "security": "no git push",
    "style": "PEP 8, 기존 코드 스타일 유지",
    "budget": "medium"
  },
  "acceptance": {
    "tests": "pytest api/tests/ 전체 통과",
    "lint": "ruff 0 errors",
    "manual": "POST /api/users 엔드포인트 smoke test 200 반환"
  },
  "risk": "medium"
}
```

### 4-3. risk 수준별 에스컬레이션 정책

| risk | 실패 시 행동 | 완료 보고 |
|------|------------|-----------|
| low | Airlock 로그만 기록 | 조용히 완료 |
| medium | Airlock 기록 + ops 채널 알림 | ops 채널 보고 |
| high | Airlock 기록 + main 채널 즉시 에스컬레이션 | 사용자 확인 대기 |

---

## 5. 예시 아키텍처 — 7개 에이전트 시스템

실제 운영 가능한 7개 에이전트 구성이다.

### 5-1. 전체 구조 다이어그램

```
                    ┌─────────────────────────────────┐
                    │          cron-agent              │
                    │    (중앙 오케스트레이터)           │
                    │  - 스케줄 관리                    │
                    │  - 위임 및 상태 추적               │
                    │  - 실패 에스컬레이션               │
                    └──────────────┬──────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
  │  finance-agent │    │  study-agent   │    │  deals-agent   │
  │ (재정 도메인)   │    │ (학습 도메인)   │    │ (딜 도메인)     │
  │ - 예산 추적     │    │ - 복습 큐 관리  │    │ - 가격 모니터링 │
  │ - 지출 분석     │    │ - 학습 스케줄   │    │ - 딜 알림       │
  │ - 이상 감지     │    │ - RAG 쿼리     │    │ - 중복 체크     │
  └────────────────┘    └────────────────┘    └────────────────┘
           │                       │                       │
           └───────────────────────┴───────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
         ┌────────────────┐            ┌────────────────┐
         │  caine-agent   │            │  voice-agent   │
         │ (실행자)        │            │ (음성 도메인)   │
         │ - 코드 실행     │            │ - STT 처리     │
         │ - 파일 조작     │            │ - TTS 생성     │
         │ - 쉘 명령      │            │ - 세션 관리    │
         └────────────────┘            └────────────────┘
                    │
                    ▼
         ┌────────────────┐
         │airlock-agent   │
         │(분류/인덱스)    │
         │- 야간 분류      │
         │- 인덱스 생성    │
         │- 보존 정책 실행 │
         └────────────────┘
```

### 5-2. 각 에이전트 상세

#### cron-agent (오케스트레이터)

| 항목 | 내용 |
|------|------|
| 유형 | Orchestrator |
| 트리거 | 시스템 시작 후 cron 루프 |
| 모델 | 빠르고 저렴한 모델 (Haiku급) |
| 권한 | 다른 에이전트 메시지 발송, 스케줄 읽기 |
| 출력 | Airlock 일별 실행 로그 |

```yaml
# cron-agent 스케줄 예시 (cron_jobs.json)
jobs:
  - id: morning-finance
    schedule: "0 9 * * *"
    target: finance-agent
    action: agent_message
    on_failure: escalate

  - id: evening-study
    schedule: "0 20 * * *"
    target: study-agent
    action: agent_message
    on_failure: log_only

  - id: nightly-airlock
    schedule: "55 23 * * *"
    target: airlock-agent
    action: agent_message
    on_failure: escalate
```

#### finance-agent (재정 도메인)

| 항목 | 내용 |
|------|------|
| 유형 | Domain |
| 트리거 | cron-agent (매일 09:00) |
| 모델 | 중간급 (Sonnet급) |
| 권한 | 카드/계좌 API 읽기, Discord 쓰기 |
| 출력 | `/airlock/daily/YYYY-MM-DD-finance-*.md` |

```markdown
# finance-agent SYSTEM PROMPT 핵심

## Role
재정 모니터링 전담. 예산 추적, 지출 분석, 이상 감지.

## In scope
- 일일 카드 지출 조회 및 예산 대비 분석
- 월말 결산 보고서 생성
- 예산 초과 시 Discord #finance 알림

## Out of scope
- 투자 판단, 송금 실행 → 사용자에게 에스컬레이션
```

#### study-agent (학습 도메인)

| 항목 | 내용 |
|------|------|
| 유형 | Domain |
| 트리거 | cron-agent (매일 20:00) + airlock-agent 완료 후 |
| 모델 | 중간급 (Sonnet급) |
| 권한 | study_queue 읽기/쓰기, Discord 쓰기 |
| 출력 | `/airlock/study_queue/YYYY-MM-DD.json` |

```markdown
# study-agent 복습 주기

- 3일 후 복습: 최초 학습 항목 (단기 기억 → 중기 전환)
- 7일 후 복습: 3일 복습 완료 항목
- 21일 후 복습: 7일 복습 완료 항목 (장기 기억 확인)

각 복습 카드에는:
- 원래 학습 날짜
- 개념 요약 (3줄 이내)
- 확인 질문 1개
```

#### deals-agent (딜 도메인)

| 항목 | 내용 |
|------|------|
| 유형 | Domain |
| 트리거 | cron-agent (30분 간격) |
| 모델 | 빠르고 저렴한 모델 |
| 권한 | 가격 API 읽기, Discord 쓰기 |
| 출력 | `/airlock/daily/YYYY-MM-DD-deals-*.md` |

중복 알림 방지:
```python
# deals-agent 중복 체크 로직 (의사 코드)
def should_alert(product_id, price):
    last_alert = airlock.get_last_alert(product_id)
    if last_alert is None:
        return True  # 첫 알림
    if (now - last_alert.time) < timedelta(hours=6):
        return False  # 6시간 이내 중복
    if abs(price - last_alert.price) / last_alert.price < 0.05:
        return False  # 5% 미만 가격 변동
    return True  # 의미있는 변동
```

#### caine-agent (실행자)

| 항목 | 내용 |
|------|------|
| 유형 | Executor |
| 트리거 | 다른 에이전트의 handoff 또는 직접 요청 |
| 모델 | 능력 높은 모델 (Sonnet/Opus급) |
| 권한 | 파일 읽기/쓰기, 쉘 실행, 테스트 실행 |
| 출력 | `/airlock/daily/YYYY-MM-DD-caine-*.md` |

```markdown
# caine-agent 보안 규칙

## 허용
- 파일 읽기/쓰기 (지정된 경로만)
- 테스트 실행 (pytest, ruff 등)
- git status, git diff, git add, git commit

## 금지
- git push (사용자 승인 없이)
- rm -rf, DROP TABLE
- 패키지 설치 (pip install) - 사용자 승인 필요
- 네트워크 요청 (handoff에 명시된 경우 제외)
```

#### voice-agent (음성 도메인)

| 항목 | 내용 |
|------|------|
| 유형 | Domain |
| 트리거 | 사용자 음성 입력 이벤트 |
| 모델 | 빠른 모델 (응답 지연 최소화) |
| 권한 | STT/TTS API, 오디오 파일 읽기/쓰기 |
| 출력 | `/airlock/daily/YYYY-MM-DD-voice-*.md` |

#### airlock-agent (분류/인덱스)

| 항목 | 내용 |
|------|------|
| 유형 | Domain (시스템 유틸리티) |
| 트리거 | cron-agent (매일 23:55) |
| 모델 | 중간급 |
| 권한 | Airlock 전체 읽기, index/study_queue 쓰기 |
| 출력 | `/airlock/index/YYYY-MM-DD.json` |

---

## 6. 에이전트 경계 설계 방법

새 에이전트를 설계할 때 다음 5단계를 따른다.

### Step 1: 도메인 질문

```
이 에이전트가 담당하는 도메인이 무엇인가?

예: "재정" → finance-agent
예: "학습" → study-agent
예: "코드 실행" → caine-agent

도메인이 두 개 이상이면 → 에이전트를 분리하라.
```

### Step 2: 경계 질문

```
이 에이전트가 절대 하지 말아야 할 것은?

예: finance-agent는 코드를 실행하지 않는다.
예: caine-agent는 재정 판단을 하지 않는다.

"Out of scope" 목록을 SYSTEM PROMPT에 명시한다.
```

### Step 3: 입력/출력 정의

```
입력:
- 어떤 형식으로 작업을 받는가? (handoff 패킷? 이벤트? 직접 메시지?)
- 입력 데이터는 어디에 있는가? (파일 경로, API 엔드포인트)

출력:
- 결과를 어디에 기록하는가? (Airlock 경로 명시)
- 다음 에이전트에게 무엇을 전달하는가?
```

### Step 4: 실패 정책 정의

```
실패 시:
1. Airlock에 실패 기록 (필수)
2. risk 수준에 따라:
   - low: 조용히 종료
   - medium: ops 채널 알림
   - high: main 채널 에스컬레이션
3. 재시도 정책: 최대 몇 회? 간격은?
```

### Step 5: 모델 선택

```
모델 선택 기준:

빠른/저렴한 모델 (Haiku급):
  - 라우팅 결정만 하는 오케스트레이터
  - 단순 분류 작업
  - 30분 간격 반복 작업

중간 모델 (Sonnet급):
  - 도메인 분석 및 보고
  - 학습 큐 큐레이션
  - 대부분의 도메인 에이전트

강력한 모델 (Opus급):
  - 복잡한 코드 리뷰
  - 아키텍처 결정
  - 필요할 때만 (비용 주의)
```

---

## 7. 안티패턴 — 피해야 할 설계

### 7-1. 역할 중복 (Anti-pattern: Role Overlap)

```
[나쁜 예]
finance-agent: "학습 관련 지출도 내가 처리할게요"
study-agent: "학습 비용 추적은 제가 할게요"

→ 어느 에이전트가 책임자인지 불명확
→ 두 에이전트가 동일 이벤트에 반응해서 중복 알림

[해결]
경계를 명확히 정의:
- 재정 데이터 → finance-agent 단독 책임
- 학습 도메인 → study-agent 단독 책임
- 경계에 걸친 사항 → 오케스트레이터가 조정
```

### 7-2. 무분별한 병렬화 (Anti-pattern: Blind Parallelism)

```
[나쁜 예]
cron-agent가 모든 에이전트를 동시에 기동:
- 동일 Airlock 파일을 여러 에이전트가 동시에 쓰기 시도
- 파일 충돌 및 데이터 손실 위험
- 비용 폭증 (모든 에이전트가 동시에 LLM 호출)

[해결]
순서 의존성이 있는 작업은 순차적으로:
  1. airlock-agent (분류) 완료 대기
  2. study-agent (큐 생성) 기동
  3. cron-agent (완료 보고)

독립적인 작업만 병렬화:
  finance-agent || deals-agent || voice-agent  (병렬 가능)
  airlock-agent → study-agent  (순차 필수)
```

### 7-3. 검증 없는 완료 선언 (Anti-pattern: Silent Success)

```
[나쁜 예]
caine-agent: "코드 수정 완료했습니다"
(실제로는 테스트를 실행하지 않음)

→ 오케스트레이터가 완료로 처리
→ 문제가 나중에 발견되면 원인 추적 불가

[해결]
acceptance 조건을 SYSTEM PROMPT에 명시:
  "완료 선언 전에 반드시:
   1. pytest 통과 확인
   2. ruff lint 확인
   3. Airlock에 검증 결과 기록"
```

### 7-4. 빈 handoff (Anti-pattern: Empty Handoff)

```
[나쁜 예]
handoff_packet = {
  "objective": "코드 고쳐줘",
  "risk": "low"
}
(scope, constraints, acceptance 없음)

→ 받는 에이전트가 무엇을 해야 할지 모름
→ 과도한 작업 범위로 비용 폭증
→ 완료 조건 불명확으로 루프 발생

[해결]
모든 필수 필드 포함:
- scope.files: 정확한 파일 경로
- constraints.runtime: 최대 실행 시간
- acceptance: 구체적인 완료 조건
```

### 7-5. Airlock 미기록 (Anti-pattern: No Record)

```
[나쁜 예]
deals-agent가 알림을 발송하고 기록을 남기지 않음

→ 중복 알림 방지 불가 (이전 알림 조회 불가)
→ 실패 시 원인 추적 불가
→ 야간 분류기가 당일 활동을 인식하지 못함

[해결]
모든 에이전트 SYSTEM PROMPT에 Airlock 정책 명시:
  "작업 완료/실패 여부와 관계없이
   실행 결과를 Airlock에 기록한다."
```

---

## 8. 확장 고려사항

### 8-1. 에이전트 추가 시 체크리스트

- [ ] 기존 에이전트와 역할 중복이 없는가?
- [ ] SYSTEM PROMPT에 In scope / Out of scope 명시
- [ ] Airlock 출력 경로 정의
- [ ] 실패 정책 정의
- [ ] cron-agent 스케줄에 등록 (필요시)
- [ ] handoff 패킷 스키마 준수
- [ ] 모델 선택 (역할에 맞는 비용/성능 균형)

### 8-2. 팀 규모별 권장 구성

#### 소규모 (1-3명)
```
cron-agent (오케스트레이터)
  ├── study-agent
  ├── finance-agent
  └── caine-agent (실행자)
```
4개 에이전트로 핵심 기능 커버.

#### 중규모 (3-10명)
```
cron-agent (오케스트레이터)
  ├── study-agent
  ├── finance-agent
  ├── deals-agent
  ├── voice-agent
  ├── caine-agent (실행자)
  └── airlock-agent (분류)
```
7개 에이전트. 도메인별 전문화.

#### 대규모 (10명+)
```
cron-agent (오케스트레이터)
  ├── [도메인 클러스터 A]
  │     ├── finance-agent
  │     ├── budget-agent
  │     └── tax-agent
  ├── [도메인 클러스터 B]
  │     ├── study-agent
  │     ├── rag-agent
  │     └── quiz-agent
  ├── [실행 클러스터]
  │     ├── caine-agent (코드)
  │     ├── infra-agent (인프라)
  │     └── qa-agent (테스트)
  └── [시스템 클러스터]
        ├── airlock-agent
        └── monitor-agent
```
클러스터별 서브 오케스트레이터 도입 고려.

### 8-3. 비용 최적화

```
에이전트별 모델 티어 전략:

Tier 1 (저비용): 오케스트레이터, 분류, 라우팅
  - Haiku 또는 동급
  - 판단보다 라우팅 위주

Tier 2 (중간): 도메인 에이전트
  - Sonnet 또는 동급
  - 대부분의 실무 에이전트

Tier 3 (고비용): 복잡한 추론
  - Opus 또는 동급
  - 아키텍처 결정, 복잡한 코드 리뷰
  - 수동 트리거 또는 risk: high 상황에서만

비용 모니터링:
  - 에이전트별 토큰 사용량을 Airlock에 기록
  - 월별 finance-agent 비용 보고에 LLM 비용 포함
```

---

## 9. 장애 대응 절차

```
에이전트 실패 시:

1단계: Airlock 확인
  cat /airlock/logs/AGENT-NAME-YYYY-MM-DD.log
  → 실패 원인 파악

2단계: risk 수준 확인
  low  → 로그 검토 후 다음 스케줄까지 대기
  medium → 수동 재실행 시도
  high  → 즉시 사용자 개입

3단계: 수동 재실행
  bash /scripts/run-AGENT-NAME.sh

4단계: SYSTEM PROMPT 검토
  실패 패턴이 반복되면 SYSTEM PROMPT 또는 스케줄 수정

5단계: 사후 기록
  /airlock/daily/YYYY-MM-DD-incident-AGENT.md 에 기록
  - 실패 원인
  - 조치 내용
  - 재발 방지책
```

---

## 관련 문서

- [Extension vs Agent 판단 기준](./05-extension-vs-agent.md) — Extension vs Agent 판단 기준
- [Airlock-first 운영 전략](./07-airlock-first-ops.md) — Airlock 운영 상세
- [서브에이전트 팀 운영](./13-subagent-orchestration.md) — 서브에이전트 팀 패턴
- [Handoff 패킷 스키마](../schemas/handoff_packet.schema.json) — handoff 패킷 스키마
- [cron-agent 예제](../examples/cron-agent/) — cron-agent 실전 예시
- [Agent 템플릿 (코드용)](../templates/AGENT_TEMPLATE_CODE.md) — 에이전트 SYSTEM PROMPT 템플릿
