# 07. Airlock-first 운영 — 기록이 곧 자산이다

> 핵심 원칙: "에이전트가 한 일은 모두 Airlock에 먼저 기록한다. 기록되지 않은 작업은 존재하지 않은 것이다."
> Airlock는 단순한 로그가 아니다. 지식 축적, 복습, 회고의 원천이다.

---

## 1. Airlock 개념 — 왜 필요한가

### 1-1. 문제 인식

AI 에이전트와 일하다 보면 이런 상황이 반복된다.

```
상황 1: "지난주에 caine-agent가 뭔가 고쳤는데 뭘 고쳤더라?"
상황 2: "어제 배운 개념인데 오늘 이미 잊어버렸다."
상황 3: "에이전트가 실패했는데 왜 실패했는지 로그가 없다."
상황 4: "finance-agent가 중복 알림을 보냈는데 이전 알림 기록이 없다."
상황 5: "3주 전에 만든 구조인데 왜 이렇게 만들었는지 맥락이 없다."
```

이 문제들의 공통 원인은 하나다: **기록 없음**.

### 1-2. Airlock의 역할

Airlock(에어록)은 우주선의 에어록에서 이름을 따왔다. 우주선에서 에어록은 내부와 외부를 연결하는 중간 공간이다. 에이전트의 작업과 지식 베이스 사이에 있는 중간 저장 공간이 Airlock이다.

```
[에이전트 작업]
      │
      ▼
[Airlock: 즉시 기록]  ←─── "에어록 우선" 원칙
      │
      ├── 야간 분류기 → 카테고리별 인덱스
      ├── study-agent → 학습 큐 생성
      ├── Obsidian 연동 → 지식 그래프에 편입
      └── 회고/저널 → 장기 기억화
```

### 1-3. Airlock-first의 의미

"Airlock-first"는 **에이전트가 작업을 마치면 결과를 외부 시스템에 반영하기 전에 Airlock에 먼저 기록한다**는 운영 원칙이다.

이 원칙이 가져다주는 것:
- 모든 에이전트 활동의 완전한 이력
- 실패 원인 추적 가능
- 중복 작업 방지 (이전 기록 참조)
- 학습 큐의 원천 데이터
- Obsidian 등 지식 도구와의 연동 기반

---

## 2. 폴더 구조 상세

### 2-1. 전체 디렉토리 트리

```
airlock/
├── daily/                      ← 에이전트 작업 기록 (원본 데이터)
│   ├── 2026-02-18/
│   │   ├── 2026-02-18-caine-agent-user-validation.md
│   │   ├── 2026-02-18-finance-agent-daily-report.md
│   │   ├── 2026-02-18-study-agent-queue-curation.md
│   │   └── 2026-02-18-manual-note-fastapi-patterns.md
│   ├── 2026-02-19/
│   │   └── ...
│   └── ...
│
├── index/                      ← 야간 분류기 생성 인덱스 (자동 생성)
│   ├── 2026-02-18.json
│   ├── 2026-02-19.json
│   └── ...
│
├── logs/                       ← 에이전트 실행 로그 (원본 stderr/stdout)
│   ├── caine-2026-02-18.log
│   ├── finance-2026-02-18.log
│   ├── study-2026-02-18.log
│   └── ...
│
├── study_queue/                ← 학습 후보 목록 (study-agent가 생성)
│   ├── 2026-02-18.json
│   ├── 2026-02-19.json
│   └── pending/                ← 아직 학습하지 않은 항목
│       └── 2026-02-18-async-patterns.md
│
└── topic-shifts/               ← 주제 전환 기록 (맥락 단절 추적)
    ├── 2026-02-18-shift-to-fastapi.md
    └── 2026-02-20-shift-to-gcp-billing.md
```

### 2-2. daily/ — 핵심 기록 저장소

`daily/`는 Airlock의 심장이다. 모든 에이전트 세션과 수동 메모가 여기에 저장된다.

**파일 명명 규칙**:
```
YYYY-MM-DD-[에이전트이름]-[작업요약 2-4단어].md

예시:
2026-02-18-caine-agent-user-validation.md
2026-02-18-finance-agent-daily-report.md
2026-02-18-manual-note-fastapi-patterns.md
2026-02-18-airlock-agent-nightly-classification.md
```

수동 기록의 경우 `manual-note-` 접두사를 사용한다.

**파일 구조** (templates/AGENT_EXTENSION_TEMPLATE.md 기반):
```markdown
## TL;DR
한 문장 요약 — 야간 분류기가 이 줄을 먼저 읽는다.

## Context
왜 이 작업을 했는가? 트리거는 무엇인가?

## Problem / Acceptance
완료 기준이 무엇이었는가?

## Execution Logs
어떤 명령을 실행했고 결과는 무엇이었는가?

## Changes
어떤 파일을 수정/생성/삭제했는가?

## Validation
완료 기준을 달성했는가? 증거는?

## Rollback / Safety
되돌리려면 어떻게 하는가?

## Classification / Handoff
- Category: code | research | ops | finance | study | other
- Tags: [태그 목록]
- Study candidate: YES / NO

## TODO
다음 할 일은?
```

### 2-3. index/ — 자동 생성 인덱스

`index/`는 야간 분류기(airlock-agent)가 매일 자동으로 생성한다. 사람이 직접 편집하지 않는다.

```json
// airlock/index/2026-02-18.json
{
  "date": "2026-02-18",
  "generated_at_utc": "2026-02-18T14:55:00Z",
  "record_count": 4,
  "records": [
    {
      "file": "airlock/daily/2026-02-18/2026-02-18-caine-agent-user-validation.md",
      "agent": "caine-agent",
      "tl_dr": "Added Pydantic input validation to POST /api/users endpoint.",
      "category": "code",
      "tags": ["python", "pydantic", "validation", "fastapi"],
      "study_candidate": true,
      "risk": "low",
      "status": "complete"
    },
    {
      "file": "airlock/daily/2026-02-18/2026-02-18-finance-agent-daily-report.md",
      "agent": "finance-agent",
      "tl_dr": "Daily budget check: 83% of February budget used with 10 days remaining.",
      "category": "finance",
      "tags": ["budget", "monthly-check"],
      "study_candidate": false,
      "risk": "low",
      "status": "complete"
    }
  ],
  "summary": {
    "by_category": {
      "code": 1,
      "finance": 1,
      "study": 1,
      "ops": 1
    },
    "study_candidates": 2,
    "failed_tasks": 0
  }
}
```

### 2-4. logs/ — 실행 로그

`logs/`는 에이전트 실행의 raw 출력이다. 디버깅과 감사 추적에 사용된다.

```
# 로그 파일 명명 규칙
[에이전트이름]-YYYY-MM-DD.log

예시:
caine-2026-02-18.log
finance-2026-02-18.log
airlock-classifier-2026-02-18.log
```

로그 보존 정책: 30일 후 자동 압축, 90일 후 삭제.

### 2-5. study_queue/ — 학습 큐

`study_queue/`는 study-agent가 daily 기록을 분석해서 생성하는 학습 후보 목록이다.

```json
// airlock/study_queue/2026-02-18.json
{
  "date": "2026-02-18",
  "generated_by": "study-agent",
  "candidates": [
    {
      "id": "sq-2026-02-18-001",
      "source_file": "airlock/daily/2026-02-18/2026-02-18-caine-agent-user-validation.md",
      "topic": "Pydantic v2 field validators vs root validators",
      "why_study": "처음 사용한 패턴. 마이그레이션 차이가 비직관적이었음.",
      "review_dates": {
        "first": "2026-02-21",
        "second": "2026-02-25",
        "third": "2026-03-11"
      },
      "status": "pending",
      "tags": ["pydantic", "python", "validation"]
    }
  ]
}
```

**복습 주기**:
```
최초 학습 → 3일 후 1차 복습 → 7일 후 2차 복습 → 21일 후 3차 복습

          학습일         +3일        +7일         +21일
          2/18    →    2/21    →   2/28    →    3/18
```

### 2-6. topic-shifts/ — 주제 전환 기록

`topic-shifts/`는 작업 맥락이 갑자기 바뀔 때 그 이유와 상황을 기록한다. 나중에 "왜 이 작업을 중단했는가"를 추적하는 데 사용된다.

```markdown
// airlock/topic-shifts/2026-02-18-shift-to-fastapi.md

## 전환 시각
2026-02-18T14:30:00+09:00

## 이전 주제
GCP 빌링 최적화 - 미완료 상태

## 새 주제
FastAPI Pydantic 검증 구현

## 전환 이유
긴급 버그 요청: POST /api/users에서 빈 이름 허용 문제

## 미완료 항목
- [ ] GCP 예약 인스턴스 비교 분석 (이어서 해야 함)
- [ ] 비용 예측 스크립트 작성

## 재개 예정
이번 FastAPI 작업 완료 후 즉시 재개
```

---

## 3. 일일 운영 워크플로우

### 3-1. 하루 전체 타임라인

```
[아침]
09:00  cron-agent 기동
  → finance-agent: 일일 예산 체크
  → health-check: 전체 에이전트 상태 확인

[낮 동안]
작업 발생 → 에이전트 기동 → 작업 수행 → Airlock 기록
(수동 작업도 Airlock에 직접 기록)

[저녁]
20:00  study-agent 기동
  → 오늘 study_queue에서 복습 대상 선별
  → Discord 복습 카드 발송

[야간]
23:55  airlock-agent 기동 (야간 오케스트레이터)
  → daily/ 오늘 파일 전체 스캔
  → 카테고리 분류
  → index/ 생성
  → study_queue 후보 생성

00:05  cron-agent 일일 마감
  → 당일 실패 항목 집계
  → Discord #ops 요약 보고
```

### 3-2. 작업 발생 시 흐름

에이전트 기동부터 기록까지의 표준 흐름이다.

```
[사용자 또는 cron-agent]
          │
          │ handoff_packet 발송
          ▼
    [도메인 에이전트]
          │
          │ 1) 작업 시작 전 Airlock에 "시작" 기록 (선택)
          │ 2) 작업 수행
          │ 3) 결과 검증
          │ 4) Airlock에 "완료" 기록 (필수)
          │ 5) 오케스트레이터에 완료 보고
          ▼
    [Airlock daily/]
          │
          │ 야간 분류기가 처리
          ▼
    [index/ + study_queue/]
```

### 3-3. 수동 작업 기록 방법

에이전트가 아닌 사람이 직접 한 작업도 Airlock에 기록한다.

```markdown
# 파일명: 2026-02-18-manual-note-gcp-billing-research.md
# 위치: airlock/daily/2026-02-18/

## TL;DR
GCP 예약 인스턴스 vs 온디맨드 비용 비교 분석. e2-standard-2 기준 예약 시 40% 절감 확인.

## Context
Triggered by: 수동 (월 비용 최적화 검토)
Goal: 내년 인스턴스 유형 결정을 위한 비용 분석

## Execution Logs
- GCP 가격 계산기로 시나리오별 비교
- 1년 약정 vs 3년 약정 ROI 계산

## Changes
- 새 파일: notes/gcp-instance-cost-analysis.md

## Classification
- Category: research
- Tags: gcp, billing, cost-optimization
- Study candidate: NO (단순 데이터 수집)
```

---

## 4. 야간 오케스트레이터 스크립트 설명

### 4-1. 오케스트레이터의 역할

야간 오케스트레이터(airlock-agent)는 매일 23:55에 기동하여 다음을 수행한다.

```
1. daily/YYYY-MM-DD/ 스캔
   → 오늘 생성된 모든 .md 파일 목록 수집

2. 각 파일 분류
   → TL;DR 읽기
   → Category 추출 (파일 내 Classification 섹션)
   → Tags 추출
   → Study candidate 여부 판단

3. index/YYYY-MM-DD.json 생성
   → 분류 결과 저장
   → 카테고리별 통계 계산

4. study_queue/YYYY-MM-DD.json 생성
   → study_candidate: true인 항목 추출
   → 복습 일정 계산 (3일/7일/21일)

5. 완료 보고
   → cron-agent에 완료 신호
   → logs/airlock-classifier-YYYY-MM-DD.log 기록
```

### 4-2. 오케스트레이터 SYSTEM PROMPT 핵심

```markdown
# AGENT: airlock-agent

## Role
매일 23:55 Airlock daily 기록을 분류하고 인덱싱하는 야간 운영 에이전트.

## Execution Steps
1. 오늘 날짜 확인: $(date +%Y-%m-%d)
2. airlock/daily/YYYY-MM-DD/ 디렉토리 스캔
3. 각 .md 파일에서 다음 추출:
   - ## TL;DR 섹션 전체
   - ## Classification 섹션의 Category, Tags, Study candidate
4. airlock/index/YYYY-MM-DD.json 생성
5. study_candidate: YES인 항목을 airlock/study_queue/YYYY-MM-DD.json에 추가
6. 처리 결과를 logs/airlock-classifier-YYYY-MM-DD.log에 기록

## Safety Rules
- daily/ 파일 수정 금지 (읽기 전용)
- index/ 파일은 생성만 (덮어쓰기 금지)
- study_queue/ 기존 파일 내용 삭제 금지 (append-only)

## Failure Handling
- 파일 파싱 실패: "unclassified" 카테고리로 처리 후 계속
- 디렉토리 없음: 빈 index 생성 후 로그에 기록
- 3회 이상 연속 실패: cron-agent에 에스컬레이션
```

### 4-3. 스크립트 예시

```bash
#!/bin/bash
# scripts/run-airlock-classifier.sh

set -euo pipefail

DATE=$(date +%Y-%m-%d)
AIRLOCK_BASE="~/.openclaw/repos/obsidian-vault/airlock"
LOG_FILE="${AIRLOCK_BASE}/logs/airlock-classifier-${DATE}.log"
DAILY_DIR="${AIRLOCK_BASE}/daily/${DATE}"
INDEX_FILE="${AIRLOCK_BASE}/index/${DATE}.json"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] airlock-classifier 시작" >> "${LOG_FILE}"

# daily 디렉토리 존재 확인
if [ ! -d "${DAILY_DIR}" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WARNING: ${DAILY_DIR} 없음. 빈 인덱스 생성." >> "${LOG_FILE}"
  echo '{"date":"'"${DATE}"'","record_count":0,"records":[]}' > "${INDEX_FILE}"
  exit 0
fi

# 파일 수 확인
FILE_COUNT=$(ls "${DAILY_DIR}"/*.md 2>/dev/null | wc -l)
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] 처리 대상: ${FILE_COUNT}개 파일" >> "${LOG_FILE}"

# airlock-agent 기동 (LLM 분류)
claude \
  --system-prompt /agents/airlock-agent/SYSTEM.md \
  --input "오늘 날짜: ${DATE}. ${DAILY_DIR} 의 ${FILE_COUNT}개 파일을 분류하고 ${INDEX_FILE} 을 생성해줘." \
  >> "${LOG_FILE}" 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: 분류 실패 (exit code: ${EXIT_CODE})" >> "${LOG_FILE}"
  exit $EXIT_CODE
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] airlock-classifier 완료" >> "${LOG_FILE}"
```

---

## 5. 학습 큐와 지식 보존

### 5-1. study_queue의 생명주기

```
1단계: 생성 (airlock-agent)
  daily 기록에서 study_candidate: YES 항목 추출
  → study_queue/YYYY-MM-DD.json 에 후보 추가

2단계: 큐레이션 (study-agent)
  후보 목록에서 중복/낮은 가치 항목 제거
  → 학습 우선순위 정렬
  → 복습 일정 계산

3단계: 알림 (study-agent)
  복습 날짜가 되면 Discord 복습 카드 발송
  사용자가 "완료" 반응하면 상태 업데이트

4단계: 완료 처리
  status: "completed" 로 변경
  Obsidian 노트에 링크 추가 (선택)
```

### 5-2. 효과적인 study_candidate 판단 기준

에이전트가 Airlock 기록을 남길 때 다음 기준으로 학습 후보 여부를 판단한다.

**YES (학습 후보):**
```
- 처음 사용한 라이브러리/패턴 (예: Pydantic v2 validators)
- 실패에서 배운 교훈 (예: 비동기 처리 데드락 원인)
- 비직관적인 동작 발견 (예: GCP 예약 인스턴스 할인율 계산 방식)
- 아키텍처 결정과 그 이유
- 성능 최적화 트릭
```

**NO (학습 후보 아님):**
```
- 단순 반복 작업 결과 (예: 일일 예산 보고)
- 이미 익숙한 패턴의 반복
- 단순 데이터 수집/조회 결과
- 일회성 운영 작업
```

### 5-3. 복습 카드 형식

Discord로 발송되는 복습 카드 예시:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
복습 카드 (3일 후 복습)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
주제: Pydantic v2 field validators vs root validators

요약:
v1에서는 @validator를 썼지만 v2에서는
@field_validator와 @model_validator로 분리됨.
단일 필드는 field_validator, 다중 필드는 model_validator.

확인 질문:
"Pydantic v2에서 두 필드를 동시에 검증하려면
어떤 데코레이터를 쓰는가?"

원본 기록: airlock/daily/2026-02-18/...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
반응: ✅ 완료  ❓ 모르겠음  ⏩ 스킵
```

---

## 6. 주제 전환 추적

### 6-1. topic-shifts의 목적

작업 도중 주제가 바뀌는 것은 피할 수 없다. 긴급 버그, 새 요청, 우선순위 변경.
`topic-shifts/`는 이 전환의 맥락을 보존한다.

**추적하는 정보:**
- 무엇을 하다가 멈췄는가 (미완료 상태)
- 왜 멈췄는가 (전환 이유)
- 새로 시작한 것은 무엇인가
- 이전 작업을 언제 재개할 것인가

### 6-2. 자동 기록 vs 수동 기록

**자동**: 에이전트가 handoff 패킷의 topic 필드를 추적해서 자동 생성

**수동**: 사용자가 직접 작성

```bash
# 빠른 수동 topic-shift 기록 스크립트
# scripts/topic-shift.sh

#!/bin/bash
DATE=$(date +%Y-%m-%d)
TIME=$(date +%Y-%m-%dT%H:%M:%S%z)
SHIFT_DIR="/airlock/topic-shifts"
FILENAME="${SHIFT_DIR}/${DATE}-shift-$(echo $2 | tr ' ' '-').md"

cat > "${FILENAME}" << EOF
## 전환 시각
${TIME}

## 이전 주제
$1

## 새 주제
$2

## 전환 이유
$3

## 미완료 항목
(직접 추가)

## 재개 예정
(직접 추가)
EOF

echo "topic-shift 기록 완료: ${FILENAME}"
```

사용법:
```bash
bash /scripts/topic-shift.sh \
  "GCP 빌링 최적화" \
  "FastAPI Pydantic 검증" \
  "긴급 버그: POST /api/users 빈 이름 허용 문제"
```

---

## 7. 보존 정책

### 7-1. 파일별 보존 기간

| 폴더 | 보존 기간 | 이후 처리 |
|------|---------|---------|
| daily/ | 영구 보존 | Obsidian 아카이브로 이동 (1년 후) |
| index/ | 영구 보존 | 용량이 작아서 그대로 유지 |
| logs/ | 30일 → 압축 | 90일 후 삭제 |
| study_queue/ | 완료 항목 90일 | pending 항목은 영구 보존 |
| topic-shifts/ | 영구 보존 | 1년 후 Obsidian 아카이브로 이동 |

### 7-2. 자동 정리 스크립트

```bash
#!/bin/bash
# scripts/airlock-cleanup.sh
# cron-agent가 매주 일요일 02:00에 실행

AIRLOCK_BASE="~/.openclaw/repos/obsidian-vault/airlock"
LOG_DIR="${AIRLOCK_BASE}/logs"
STUDY_QUEUE_DIR="${AIRLOCK_BASE}/study_queue"
ARCHIVE_DIR="${AIRLOCK_BASE}/../archive"

DATE=$(date +%Y-%m-%d)

echo "=== Airlock 정리 시작: ${DATE} ==="

# 1. 30일 이상 된 로그 파일 압축
find "${LOG_DIR}" -name "*.log" -mtime +30 -not -name "*.gz" | while read f; do
  gzip "$f"
  echo "압축: $f"
done

# 2. 90일 이상 된 압축 로그 삭제
find "${LOG_DIR}" -name "*.log.gz" -mtime +90 | while read f; do
  rm "$f"
  echo "삭제: $f"
done

# 3. study_queue에서 90일 이상 된 완료 항목 정리
# (Python 스크립트로 JSON 처리)
python3 /scripts/cleanup_study_queue.py \
  --queue-dir "${STUDY_QUEUE_DIR}" \
  --days 90 \
  --status completed

# 4. 1년 이상 된 daily 기록을 아카이브로 이동
YEAR_AGO=$(date -d "1 year ago" +%Y-%m-%d)
find "${AIRLOCK_BASE}/daily" -mindepth 1 -maxdepth 1 -type d | while read d; do
  DIR_DATE=$(basename "$d")
  if [[ "$DIR_DATE" < "$YEAR_AGO" ]]; then
    YEAR=$(echo $DIR_DATE | cut -d'-' -f1)
    mkdir -p "${ARCHIVE_DIR}/${YEAR}"
    mv "$d" "${ARCHIVE_DIR}/${YEAR}/"
    echo "아카이브 이동: $d"
  fi
done

echo "=== Airlock 정리 완료 ==="
```

### 7-3. 디스크 사용량 모니터링

```bash
# 월간 Airlock 용량 보고 (finance-agent 비용 보고에 포함)
du -sh /airlock/daily/ /airlock/index/ /airlock/logs/ /airlock/study_queue/

# 출력 예시:
# 48M     /airlock/daily/
# 2.1M    /airlock/index/
# 8.5M    /airlock/logs/
# 1.2M    /airlock/study_queue/
```

---

## 8. Obsidian 연동

### 8-1. Airlock와 Obsidian 관계

Obsidian은 Airlock의 데이터를 시각화하고 지식 그래프로 연결하는 프론트엔드 역할을 한다.

```
[Airlock]                    [Obsidian Vault]
  daily/         →  (야간 연동)  → Notes/daily/
  study_queue/   →  (weekly 연동) → Study/queue/
  index/         →  (검색 연동)  → 태그 및 링크 네트워크
```

**연동 원칙**:
- Airlock이 원본 데이터
- Obsidian은 뷰 레이어 (편집하지 않음)
- Airlock → Obsidian 방향으로만 동기화

### 8-2. 연동 스크립트

```bash
#!/bin/bash
# scripts/sync-airlock-to-obsidian.sh
# cron-agent가 매일 01:00에 실행

AIRLOCK_DAILY="/airlock/daily"
OBSIDIAN_DAILY="~/obsidian-vault/Daily Notes/Airlock"
DATE=$(date +%Y-%m-%d)

# 오늘 날짜 Airlock daily 파일들을 Obsidian Daily Notes로 복사
mkdir -p "${OBSIDIAN_DAILY}/${DATE}"

# .md 파일 복사 (Obsidian YAML 프론트매터 추가)
for f in "${AIRLOCK_DAILY}/${DATE}"/*.md; do
  if [ -f "$f" ]; then
    BASENAME=$(basename "$f")
    TARGET="${OBSIDIAN_DAILY}/${DATE}/${BASENAME}"

    # Obsidian 프론트매터 추가
    cat > "${TARGET}" << EOF
---
source: airlock
date: ${DATE}
tags: airlock/daily
---

EOF
    cat "$f" >> "${TARGET}"
    echo "동기화: $BASENAME"
  fi
done

echo "Obsidian 동기화 완료: ${DATE}"
```

### 8-3. Obsidian에서 Airlock 활용

**데이터뷰(Dataview) 쿼리 예시**:

```dataview
// 이번 주 학습 후보 목록
TABLE date, tl_dr, tags
FROM "Daily Notes/Airlock"
WHERE study_candidate = "YES"
AND date >= date(today) - dur(7 days)
SORT date DESC
```

```dataview
// 미완료 TODO 추적
TASK
FROM "Daily Notes/Airlock"
WHERE !completed
SORT date DESC
```

**그래프 뷰 활용**:
- 태그를 통해 관련 기록 연결
- `[[링크]]` 문법으로 관련 노트 연결

---

## 9. 백업과 복구

### 9-1. 백업 전략

Airlock은 운영의 핵심 기록이므로 이중 백업이 필요하다.

```
[Airlock (로컬 VM)]
       │
       ├── 매일 02:00 → GCS 버킷 rsync
       │                (gs://my-backup/airlock/)
       │
       └── 매주 일요일 → 로컬 압축 백업
                        (/backup/airlock-YYYY-WW.tar.gz)
```

**GCS 자동 백업 스크립트**:
```bash
#!/bin/bash
# scripts/backup-airlock-to-gcs.sh

AIRLOCK_BASE="~/.openclaw/repos/obsidian-vault/airlock"
GCS_BUCKET="gs://my-openclaw-backup/airlock"
DATE=$(date +%Y-%m-%d)

echo "[${DATE}] Airlock GCS 백업 시작"

# rsync 방식으로 변경분만 업로드 (비용 효율적)
gsutil -m rsync -r \
  "${AIRLOCK_BASE}/daily" \
  "${GCS_BUCKET}/daily"

gsutil -m rsync -r \
  "${AIRLOCK_BASE}/index" \
  "${GCS_BUCKET}/index"

gsutil -m rsync -r \
  "${AIRLOCK_BASE}/study_queue" \
  "${GCS_BUCKET}/study_queue"

echo "[${DATE}] GCS 백업 완료"
echo "[${DATE}] 백업 크기: $(gsutil du -sh ${GCS_BUCKET} | awk '{print $1}')"
```

### 9-2. 복구 절차

VM이 손상되거나 재생성된 경우:

```bash
# 1. GCS에서 복구
gsutil -m rsync -r \
  gs://my-openclaw-backup/airlock \
  ~/.openclaw/repos/obsidian-vault/airlock

# 2. 권한 복구
find /airlock -type f -name "*.md" -exec chmod 644 {} \;
find /airlock -type d -exec chmod 755 {} \;

# 3. 복구 후 무결성 확인
ls /airlock/daily/ | wc -l  # 날짜 디렉토리 수 확인
ls /airlock/index/ | wc -l  # 인덱스 파일 수 확인

# 4. 최신 index 재생성 (복구 후 불일치가 있을 경우)
bash /scripts/run-airlock-classifier.sh
```

### 9-3. 복구 시나리오별 대응

| 시나리오 | 영향 | 복구 방법 |
|---------|------|---------|
| VM 재부팅 | 없음 | Airlock 파일 안전 (디스크 유지) |
| VM 삭제 후 재생성 | 전체 손실 | GCS 백업에서 rsync 복구 |
| 실수로 파일 삭제 | 부분 손실 | GCS에서 해당 파일만 복구 |
| 디스크 불량 | 전체 손실 | GCS 백업에서 복구 |
| 에이전트가 파일 덮어씀 | 부분 손실 | GCS에서 해당 날짜 복구 |

---

## 10. 실전 운영 팁

### 10-1. Airlock 기록 품질 향상

**TL;DR 잘 쓰는 법**:
```
나쁜 예:
"코드 수정했음"
"에이전트 실행"
"작업 완료"

좋은 예:
"Added Pydantic v2 field validator to POST /api/users, rejecting empty names with 422."
"finance-agent: Feb budget 83% used, 10 days remaining. No overage alert."
"study-agent: Generated 3 review cards from 5 airlock records. Next review: Feb 21."
```

TL;DR는 야간 분류기가 처음 읽는 줄이다. 분류기가 이 줄만 읽어도 카테고리와 태그를 정확하게 추출할 수 있어야 한다.

**Tags 일관성 유지**:
```
코드 관련: python, fastapi, pydantic, async, typescript, ...
인프라 관련: gcp, docker, tailscale, nginx, ...
학습 관련: algorithm, system-design, database, ...
재정 관련: budget, billing, cost-optimization, ...
```

### 10-2. 흔한 실수와 해결

**실수 1: Airlock 기록 미루기**
```
"나중에 기록하면 돼"라고 생각하다가 기록을 안 하게 됨.

해결: 작업 완료 즉시 기록. SYSTEM PROMPT에 "완료 선언 전 Airlock 기록 필수" 명시.
```

**실수 2: TL;DR이 너무 모호함**
```
"에이전트 실행 완료"는 분류기가 처리하지 못함.

해결: 구체적인 행위 + 결과를 한 문장으로. 누가 봐도 무슨 일이 있었는지 알 수 있어야 함.
```

**실수 3: study_candidate를 전부 YES로 설정**
```
모든 것이 중요하면 아무것도 중요하지 않게 됨.
study_queue가 쌓이기만 하고 실제 복습은 이루어지지 않음.

해결: YES 기준을 엄격하게 유지. 처음 보거나, 비직관적이거나, 실수에서 배운 경우만.
```

**실수 4: 로그 파일을 Airlock으로 착각**
```
logs/는 raw 실행 출력. 사람이 읽기 위한 구조화된 기록이 아님.
daily/ 파일이 없으면 야간 분류기가 처리할 내용이 없음.

해결: 에이전트 완료 후 daily/에 .md 파일 생성 여부를 반드시 확인.
```

### 10-3. 일주일 후 되돌아보기

매주 일요일 30분을 투자해 Airlock을 리뷰한다.

```
주간 리뷰 체크리스트:

□ 이번 주 daily/ 파일이 매일 생성되었는가?
□ index/ 파일이 매일 생성되었는가? (야간 분류기 정상 동작)
□ study_queue에 미처리 항목이 쌓이지는 않았는가?
□ topic-shifts가 있다면 재개하지 않은 작업이 있는가?
□ 실패 기록이 있다면 원인을 파악했는가?
□ 이번 주 가장 값진 학습은 무엇이었는가?
```

---

## 11. 빠른 시작 가이드

### 11-1. 처음 설정 (15분)

```bash
# 1. Airlock 디렉토리 생성
mkdir -p ~/.openclaw/repos/obsidian-vault/airlock/{daily,index,logs,study_queue,topic-shifts}

# 2. 오늘 날짜 daily 디렉토리 생성
mkdir -p ~/.openclaw/repos/obsidian-vault/airlock/daily/$(date +%Y-%m-%d)

# 3. 첫 번째 수동 기록 작성
cat > ~/.openclaw/repos/obsidian-vault/airlock/daily/$(date +%Y-%m-%d)/$(date +%Y-%m-%d)-manual-note-airlock-setup.md << 'EOF'
## TL;DR
Airlock-first 운영 시스템 초기 설정 완료. 디렉토리 구조 생성 및 첫 기록 작성.

## Context
Triggered by: 수동 (OpenClaw 멀티에이전트 시스템 초기 구성)
Goal: Airlock 운영 기반 마련

## Changes
- 생성: airlock/daily/, index/, logs/, study_queue/, topic-shifts/ 디렉토리

## Validation
- 디렉토리 구조 생성 확인: OK

## Classification
- Category: ops
- Tags: setup, airlock, initial
- Study candidate: NO
EOF

echo "첫 Airlock 기록 완료!"

# 4. 야간 분류기 cron 등록
(crontab -l 2>/dev/null; echo "55 23 * * * /path/to/scripts/run-airlock-classifier.sh") | crontab -

# 5. GCS 백업 cron 등록 (선택)
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/scripts/backup-airlock-to-gcs.sh") | crontab -

echo "Airlock 초기 설정 완료!"
crontab -l
```

### 11-2. 매일 루틴 (5분)

```bash
# 오늘의 Airlock 상태 빠른 확인
DATE=$(date +%Y-%m-%d)
AIRLOCK="~/.openclaw/repos/obsidian-vault/airlock"

echo "=== ${DATE} Airlock 현황 ==="
echo "오늘 기록: $(ls ${AIRLOCK}/daily/${DATE}/*.md 2>/dev/null | wc -l)개"
echo "미처리 study_queue: $(python3 -c "
import json, glob
total = 0
for f in glob.glob('${AIRLOCK}/study_queue/*.json'):
    data = json.load(open(f))
    total += sum(1 for c in data.get('candidates', []) if c.get('status') == 'pending')
print(total)
")개"
echo "오늘 로그 크기: $(du -sh ${AIRLOCK}/logs/*${DATE}* 2>/dev/null | awk '{print $1}' | paste -sd+ | bc 2>/dev/null || echo '0')B"
```

---

## 관련 문서

- [Extension vs Agent 판단 기준](./05-extension-vs-agent.md) — Extension vs Agent 판단 기준
- [멀티에이전트 구조 설계](./06-multi-agent-architecture.md) — 에이전트 아키텍처 설계
- [RAG + Studybot 연동](./08-rag-studybot.md) — RAG + Studybot 연동
- [서브에이전트 팀 운영](./13-subagent-orchestration.md) — 서브에이전트 팀 운영
- [Agent Extension 템플릿](../templates/AGENT_EXTENSION_TEMPLATE.md) — Airlock 기록 템플릿
- [Airlock 인덱스 스키마](../schemas/airlock_index.schema.json) — Airlock 인덱스 스키마
- [cron-agent 예제](../examples/cron-agent/) — cron-agent와 airlock 연동 예시
