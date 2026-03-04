# 05. Extension vs Agent — 언제 무엇을 쓸 것인가

> 핵심 질문: "이 작업을 Extension으로 처리해야 하는가, 독립 Agent로 분리해야 하는가?"
> 이 판단 하나가 운영 비용, 응답 속도, 유지보수 난이도를 크게 바꾼다.

---

## 1. 개념 정의

### 1-1. Extension이란?

Extension은 **Claude Code(또는 유사 LLM 인터페이스) 세션 내부에서 직접 실행되는 단발성·보조 기능**이다.
별도 프로세스나 서비스를 띄우지 않으며, 사용자의 현재 대화 흐름 안에서 즉시 동작한다.

특징:
- 컨텍스트를 공유한다 (현재 세션의 파일, 변수, 대화 이력)
- 응답 지연이 거의 없다 (네트워크 왕복 없음)
- 실행이 끝나면 흔적이 남지 않는다 (상태 비저장)
- 스케줄링·백그라운드 동작 없음

```
[사용자] ──── 대화 ────▶ [Claude Code 세션]
                               │
                         Extension 실행
                               │
                         결과를 즉시 반환
```

### 1-2. Agent란?

Agent는 **독립적인 목적(role)과 실행 주기를 가진 자율 동작 단위**다.
자체 SYSTEM PROMPT, 상태 파일, 입출력 경로를 갖고, 다른 에이전트나 외부 시스템과 handoff 패킷으로 소통한다.

특징:
- 역할(role)이 명시적으로 정의되어 있다
- 스케줄(cron) 또는 이벤트로 자동 기동
- 실행 결과를 Airlock에 기록한다 (상태 저장)
- 다른 에이전트에게 작업을 위임하거나 보고할 수 있다

```
[cron / 이벤트] ──▶ [Agent: SYSTEM PROMPT + 역할]
                            │
                     Airlock에 기록
                            │
                     handoff 패킷 발송
                            │
                     다음 Agent 또는 채널
```

---

## 2. 결정 트리 — Extension vs Agent

다음 질문에 답하면서 내려가면 된다.

```
작업이 생겼다
     │
     ▼
Q1. 이 작업을 지금 당장, 한 번만 수행하면 끝인가?
     │
     ├── YES ──▶ Q2. 컨텍스트(열린 파일, 현재 대화)가 필요한가?
     │                  │
     │                  ├── YES ──▶ [Extension]
     │                  │           현재 세션에서 바로 처리
     │                  │
     │                  └── NO  ──▶ Q3. 10초 이상 걸리거나
     │                              외부 API 호출이 있는가?
     │                                   │
     │                                   ├── YES ──▶ [Agent (단발)]
     │                                   └── NO  ──▶ [Extension]
     │
     └── NO  ──▶ Q4. 반복/스케줄/모니터링이 필요한가?
                        │
                        ├── YES ──▶ [Agent (상시)]
                        │
                        └── NO  ──▶ Q5. 다른 에이전트에게
                                    결과를 넘겨야 하는가?
                                         │
                                         ├── YES ──▶ [Agent]
                                         └── NO  ──▶ [Extension]
```

---

## 3. Extension이 적합한 작업

### 3-1. 특성 요약

| 기준 | 값 |
|------|----|
| 실행 빈도 | 1회, 즉시 |
| 컨텍스트 | 현재 세션 공유 |
| 결과 저장 | 불필요 (또는 사용자가 직접 저장) |
| 외부 연동 | 없거나 최소 |
| 유지보수 | 거의 없음 |

### 3-2. 구체적인 예시

#### 코드 정리 및 리팩터링
```
사용자: "이 함수 중복 코드를 제거해줘"
→ Extension: 현재 열린 파일을 읽고, 즉시 수정 후 반환
```
- 현재 세션의 파일 컨텍스트를 바로 활용
- 결과를 사용자가 검토 후 저장
- 반복 실행 불필요

#### 타입 힌트 / 독스트링 추가
```
사용자: "auth.py에 타입 힌트 추가해줘"
→ Extension: 파일 읽기 → 수정 → diff 보여주기
```

#### 즉석 번역·요약
```
사용자: "이 README를 한국어로 요약해줘"
→ Extension: 현재 파일을 읽어 즉시 요약 반환
```

#### 단발성 분석
```
사용자: "이 SQL 쿼리 성능 문제점 설명해줘"
→ Extension: 쿼리 분석 후 설명 반환
```

#### 포맷 변환
```
사용자: "이 JSON을 YAML로 바꿔줘"
→ Extension: 변환 후 즉시 반환
```

#### 테스트 케이스 생성
```
사용자: "이 함수에 대한 pytest 케이스 만들어줘"
→ Extension: 함수 시그니처 분석 → 테스트 코드 생성
```

---

## 4. Agent가 적합한 작업

### 4-1. 특성 요약

| 기준 | 값 |
|------|----|
| 실행 빈도 | 반복, 스케줄, 이벤트 트리거 |
| 컨텍스트 | 자체 상태 파일 또는 Airlock |
| 결과 저장 | Airlock 필수 기록 |
| 외부 연동 | API, DB, 메시지 채널 등 |
| 유지보수 | SYSTEM PROMPT + 스키마 관리 |

### 4-2. 구체적인 예시

#### 야간 Airlock 분류 오케스트레이터
```
23:55 cron → cron-agent 기동
  → airlock/daily/ 파일 스캔
  → 카테고리 분류 (study / ops / finance / deal)
  → study_queue 후보 생성
  → 분류 결과 index/ 저장
  → study-agent에 handoff
```

#### 재정 모니터링 에이전트
```
매일 09:00 → finance-agent 기동
  → 카드/계좌 API 조회
  → 예산 초과 여부 판단
  → Discord #finance 채널 보고
  → 이상 감지 시 main 채널 에스컬레이션
```

#### 학습 복습 알림 에이전트
```
매일 20:00 → study-agent 기동
  → study_queue/ 스캔
  → 3일/7일/21일 복습 대상 선별
  → Discord 복습 카드 발송
  → 완료 기록 Airlock에 저장
```

#### 딜 감시 에이전트
```
30분 간격 → deals-agent 기동
  → 가격 비교 API 조회
  → 임계값 이하 상품 발견 시 알림
  → 이전 알림 중복 체크 (Airlock 조회)
  → 새 알림만 Discord 발송
```

#### CI 품질 게이트 에이전트
```
PR 머지 이벤트 → qa-agent 기동
  → 테스트/린트 결과 분석
  → 실패 항목 분류 및 리포트
  → PM 에이전트에 handoff
  → 결과 Airlock 기록
```

---

## 5. 성능 특성 비교

### 5-1. 응답 지연

```
Extension:
  사용자 요청 ──▶ LLM 추론 ──▶ 결과
  지연: ~2~10초 (추론 시간만)

Agent (단발):
  이벤트 ──▶ 프로세스 기동 ──▶ LLM 추론 ──▶ 결과 저장
  지연: ~5~30초 (기동 + 추론 + I/O)

Agent (상시):
  cron ──▶ 백그라운드 실행 ──▶ 결과 비동기 도착
  지연: 사용자가 인식 못함 (비동기)
```

### 5-2. 토큰 비용

| 방식 | 컨텍스트 크기 | 비용 특성 |
|------|-------------|-----------|
| Extension | 현재 대화 전체 | 대화가 길수록 비쌈 |
| Agent (단발) | SYSTEM PROMPT + 작업 문서만 | 격리되어 있어 저렴 |
| Agent (상시) | SYSTEM PROMPT + 최소 컨텍스트 | 스케줄 간격으로 제어 가능 |

> 팁: Agent는 컨텍스트를 격리해서 불필요한 대화 이력을 포함하지 않으므로, 동일 작업을 반복할 때 토큰 효율이 훨씬 높다.

### 5-3. 안정성

```
Extension 실패:
  → 사용자가 즉시 인식, 재시도 가능
  → 부작용 없음 (대화만 끊김)

Agent 실패:
  → Airlock에 실패 기록 남음
  → 다음 스케줄에 자동 재시도 가능
  → 에스컬레이션 경로 필요
```

---

## 6. Extension에서 Agent로 전환하는 방법

처음엔 Extension으로 시작하고, 다음 신호가 보이면 Agent로 전환한다.

### 6-1. 전환 신호

- 같은 작업을 3회 이상 수동으로 반복했다
- "이거 매일 해줘"라는 요청이 생겼다
- 결과를 다른 시스템이나 에이전트에 넘겨야 한다
- 실행이 30초 이상 걸려서 대화가 막힌다
- 실패 시 자동 재시도가 필요하다

### 6-2. 전환 절차

#### Step 1: 현재 Extension 프롬프트를 정리

Extension으로 쓰던 프롬프트를 문서화한다.

```markdown
# Extension → Agent 전환 노트

## 원래 Extension 사용 패턴
- 트리거: 매일 밤 수동 실행
- 프롬프트: "airlock/daily/에 있는 오늘 파일 정리해줘"
- 결과: 분류된 목록 출력

## 전환 결정 이유
- 3주 연속 매일 수동으로 실행
- 자동화 필요
```

#### Step 2: SYSTEM PROMPT 작성

`templates/AGENT_TEMPLATE_CODE.md`를 참고해서 Agent SYSTEM PROMPT를 작성한다.

```markdown
# AGENT: airlock-classifier

## Role / Scope
- 매일 23:55에 기동하는 Airlock 분류 에이전트
- airlock/daily/YYYY-MM-DD/ 의 모든 기록을 읽어 분류

## Routing / Handoff
- 분류 완료 → study-agent에 study_queue 후보 전달
- 이상 감지 → main 채널 에스컬레이션

## Execution Rules
1. 오늘 날짜 디렉토리만 처리
2. 기존 index/ 파일 덮어쓰지 않음
3. 분류 불가 항목은 "unclassified" 태그

## Output Policy
- airlock/index/YYYY-MM-DD.json 저장
- 처리 완료 로그: airlock/logs/classifier-YYYY-MM-DD.log

## Airlock Policy
- 모든 실행 결과는 Airlock에 기록 필수
- 실패 시 error 필드에 원인 기록

## Safety / Secrets
- 파일 삭제 절대 금지
- 읽기 전용 작업만 허용 (index 생성 제외)
```

#### Step 3: 실행 환경 구성

```bash
# crontab 등록
55 23 * * * /path/to/scripts/run-airlock-classifier.sh

# 스크립트 예시 (scripts/run-airlock-classifier.sh)
#!/bin/bash
DATE=$(date +%Y-%m-%d)
LOG_FILE="/airlock/logs/classifier-${DATE}.log"

claude \
  --system-prompt /agents/airlock-classifier/SYSTEM.md \
  --input "오늘 날짜: ${DATE}. airlock/daily/${DATE}/ 분류를 시작해줘." \
  >> "${LOG_FILE}" 2>&1
```

#### Step 4: Airlock 출력 템플릿 확인

```json
// airlock/index/2026-02-18.json
{
  "date": "2026-02-18",
  "generated_at_utc": "2026-02-18T14:55:00Z",
  "record_count": 12,
  "records": [
    {
      "file": "airlock/daily/2026-02-18/task-001.md",
      "category": "study",
      "tags": ["python", "async"],
      "study_candidate": true
    }
  ]
}
```

#### Step 5: 수동 테스트 후 cron 활성화

```bash
# 수동 테스트
bash /path/to/scripts/run-airlock-classifier.sh

# 결과 확인
cat /airlock/logs/classifier-$(date +%Y-%m-%d).log
cat /airlock/index/$(date +%Y-%m-%d).json

# 문제 없으면 cron 활성화
crontab -e
```

---

## 7. Agent에서 Extension으로 되돌리는 경우

Agent가 과도하게 복잡해졌을 때는 Extension으로 단순화하는 것이 낫다.

### 되돌림 신호

- Agent가 실행되는 횟수가 월 5회 미만으로 줄었다
- 해당 작업이 사용자 주도 대화로 충분히 처리된다
- Agent 유지보수 비용이 가져다주는 가치보다 크다

### 되돌림 방법

1. Agent SYSTEM PROMPT에서 핵심 지시문만 추출
2. 해당 지시문을 Extension 사용 가이드 문서로 변환
3. cron 비활성화
4. Airlock 기록은 보존 (history 보존 정책 유지)

---

## 8. 실전 Best Practices

### 8-1. Extension 사용 원칙

1. **세션 컨텍스트 활용이 핵심**: 현재 열린 파일, 대화 맥락을 직접 사용할 수 있을 때만 Extension을 선택한다.
2. **결과를 즉시 검토**: Extension 결과는 사용자가 바로 확인하고 필요시 Airlock에 수동 기록한다.
3. **무한 확장 금지**: Extension 프롬프트가 50줄을 넘기 시작하면 Agent 전환을 검토한다.
4. **실패해도 괜찮다**: Extension은 실패해도 부작용이 없다. 과감하게 시도한다.

### 8-2. Agent 설계 원칙

1. **단일 책임 원칙**: Agent 하나는 하나의 명확한 역할만 가진다. 역할이 2개 이상이면 분리를 고려한다.
2. **Airlock 우선 기록**: 모든 Agent 실행 결과는 반드시 Airlock에 기록한다. 기록 없는 자동화는 블랙박스다.
3. **실패 경로 명시**: SYSTEM PROMPT에 실패 시 행동(재시도, 에스컬레이션, 로그 기록)을 항상 명시한다.
4. **handoff 스키마 준수**: 다른 Agent에 넘길 때는 반드시 `schemas/handoff_packet.schema.json` 형식을 따른다.
5. **최소 컨텍스트**: Agent의 SYSTEM PROMPT는 필요한 정보만 포함한다. 불필요한 배경 정보로 토큰을 낭비하지 않는다.

### 8-3. 판단이 어려울 때

Extension과 Agent 사이에서 판단이 어려울 때는 **먼저 Extension으로 시작**한다.
자동화 필요성은 실제 운영해봐야 안다. 과도한 Agent 설계는 유지보수 부채를 낳는다.

```
원칙: 단순하게 시작 → 불편함이 생기면 그때 Agent로 전환
```

---

## 9. 체크리스트

### Extension 사용 전 체크

- [ ] 이 작업은 지금 한 번만 필요한가?
- [ ] 현재 세션의 파일/대화 컨텍스트가 필요한가?
- [ ] 결과를 사용자가 직접 검토할 것인가?
- [ ] 30초 이내에 완료 가능한가?

### Agent 전환 전 체크

- [ ] 같은 작업을 3회 이상 반복했는가?
- [ ] 결과를 자동으로 저장하고 추적해야 하는가?
- [ ] 다른 시스템/에이전트에 결과를 넘겨야 하는가?
- [ ] SYSTEM PROMPT를 작성할 준비가 되었는가?
- [ ] Airlock 출력 경로를 정했는가?
- [ ] 실패 시 행동을 정의했는가?

---

## 관련 문서

- [멀티에이전트 구조 설계](./06-multi-agent-architecture.md) — 에이전트 설계 원칙
- [Airlock-first 운영 전략](./07-airlock-first-ops.md) — Airlock 기록 방법
- [서브에이전트 팀 운영](./13-subagent-orchestration.md) — 서브에이전트 팀 운영
- [Agent 템플릿 (코드용)](../templates/AGENT_TEMPLATE_CODE.md) — Agent SYSTEM PROMPT 템플릿
- [Agent Extension 템플릿](../templates/AGENT_EXTENSION_TEMPLATE.md) — Airlock 기록 템플릿
- [Handoff 패킷 스키마](../schemas/handoff_packet.schema.json) — handoff 패킷 스키마
