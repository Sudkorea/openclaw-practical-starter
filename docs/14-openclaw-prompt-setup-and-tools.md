# 14. OpenClaw 노트: 프롬프트 세팅 + 기본 기능 + 툴 정리

이 문서는 "처음 에이전트를 만들 때 무엇을 어디에 적어야 하는지"와
"OpenClaw에서 기본적으로 뭘 할 수 있는지"를 빠르게 보는 요약 노트다.

---

## 1) 에이전트 프롬프트/정체성 파일 세팅법

에이전트 워크스페이스에 보통 아래 파일을 둔다.

- `AGENTS.md` : 역할/작업 규칙/위임 규칙(실무 행동 규칙)
- `SOUL.md` : 말투/태도/정체성(성격/톤)
- `IDENTITY.md` : 이름/모드 요약
- `TOOLS.md` : 어떤 도구를 어떻게 쓸지 운영 가이드
- `USER.md` : 사용자 선호/맥락 메모

### 최소 권장 템플릿
- 코드 에이전트: `~/.openclaw/common/templates/AGENT_TEMPLATE_CODE.md`
- 비코드 에이전트: `~/.openclaw/common/templates/AGENT_TEMPLATE_NONCODE.md`

### 작성 원칙
1. `AGENTS.md`에는 행동 규칙(검증/보고/위임)을 명확히 쓴다.
2. `SOUL.md`는 짧고 선명하게(너무 길면 실효성 하락).
3. `IDENTITY.md`는 한 줄 정체성으로 유지.
4. 산출물 기록 규칙은 Airlock 정책으로 통일.

---

## 2) OpenClaw 기본 기능 (핵심)

1. 멀티 에이전트 운영
- agent별 모델/워크스페이스/권한 분리
- agent-to-agent 위임 가능

2. 크론 자동화
- 정시/주기 작업 예약
- 실패/완료 알림 연계

3. 채널 라우팅
- Discord 등 채널별 계정/멘션/정책 설정
- deep-work/ops/study 같은 컨텍스트 분리 가능

4. 도구 실행
- 파일 읽기/쓰기, 명령 실행, 브라우저 자동화, 웹 검색, 이미지 분석 등

5. 운영 안정화
- 이벤트 모니터링, 중복 억제, 상태 점검, 업데이트/재시작

6. 메모리/기록
- memory 파일 + airlock 기록으로 연속성 확보

---

## 3) 에이전트가 사용할 수 있는 툴(요약)

### 작업/개발
- `read`, `write`, `edit`, `exec`, `process`

### 웹/브라우저
- `web_search`, `web_fetch`, `browser`

### 자동화/운영
- `cron`, `gateway`, `session_status`

### 커뮤니케이션
- `message`

### 멀티에이전트
- `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`

### 기타
- `image`, `memory_search`, `memory_get`

> 실제 사용 가능 툴은 에이전트별 allow 설정에 따라 달라진다.

---

## 4) Airlock 기록 규칙 (운영 표준)

- 경로: `~/.openclaw/repos/obsidian-vault/airlock`
- 형식: `AGENT_EXTENSION_TEMPLATE.md` 준수
- 최소 필수:
  - TL;DR
  - 실행 로그(명령/에러)
  - 변경 파일
  - 검증 결과
  - 다음 액션

주제 전환/보류사항은 `topic-shifts/`에 저장.

---

## 5) 실무 팁

- 처음엔 에이전트 많이 만들지 말고 2~3개로 시작.
- "역할 중복"을 줄이는 게 성능보다 중요.
- 로그는 상세 채널로, 메인 채널은 중요한 이벤트만.
- 템플릿/스키마 먼저 정하고 자동화를 얹어야 오래 간다.
