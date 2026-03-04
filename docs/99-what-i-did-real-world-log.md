# 99. 내가 실제로 했던 것들 (시행착오 기반 정리)

> **Note:** 이 문서는 저자의 개인 프로젝트 구현 로그입니다. 프로젝트명, 봇 이름 등은 실제 사용 예시이며, 여러분의 환경에 맞게 변경하세요.

이 문서는 "처음부터 뭘 했고 왜 그렇게 바꿨는지"를 한 번에 보는 실전 로그 요약이다.

## A. 운영 구조
- `daily-agent` 중심 운영에서 `caine-agent` 중심으로 전환.
- `cron-agent` 신설 후 주요 cron 소유권 이관.
- 이벤트 기반 모니터링 + 중복 억제(fingerprint) 도입.

## B. Discord/채널
- 계정 역할 분리:
  - caine: 실행/개발
  - bubbles: 상태/알림
  - gigachad: 학습/회고
- 채널 목적 분리(deep-work / ops / study / diary).
- 중복응답 이슈를 mention 정책 엄격화로 해결.

## C. Airlock-first
- Airlock 템플릿/README 정비.
- nightly orchestrator(23:00 KST) 추가:
  - 분류(ops/finance/study/journal_input)
  - summary/index/study queue 후보 생성
- logs 분리 + 30일 보관 정책 적용.

## D. RAG privacy
- 원본 vault와 rag-safe worktree 분리.
- sanitize 스크립트로 개인정보/토큰 패턴 마스킹.
- RAG는 `aistudy + obsidian-vault-rag-safe`만 사용.

## E. Voice agent
- discord voice recv 기반 STT/TTS 루프 구축.
- 해결한 이슈:
  - whisper compute type fallback
  - GCP STT mono 에러(stereo->mono)
  - streaming timeout 복구
  - TTS 텍스트 sanitize
- 지연 이슈는 현재도 최적화 대상(p50/p95 계측 필요).

## F. Finance/event-trading-v2
- shock-data Option A(무료 데이터) 파이프라인 구현.
- Binance 451, GDELT timeout 등 외부 의존성 문제를 fallback 체인으로 완화.
- debug/require-real 플래그로 실데이터 강제 검증 경로 추가.

## G. 템플릿/표준화
- 코드/비코드 에이전트 템플릿 추가.
- airlock 기록 템플릿 추가.
- handoff/index 스키마 추가.
- KPI baseline + kpi snapshot cron 추가.

## G-2. Deals Agent (핫딜 알리미 + 개인화 추천)
- `deals-agent` 전용 파이프라인 구축 (크롤링 → Discord 알림 → 평점 수집 → 학습).
- Discord 봇 역할 분리: 비활성 봇(`zooble`)을 "집게사장"으로 리브랜딩해 전용 채널에 배정.
- 구현 구성요소:
  - `crawl_hotdeal.py`: arca.live/b/hotdeal HTML 파서 (BeautifulSoup). User-Agent 헤더로 403 회피.
  - `collect_ratings.py`: Discord API로 1️⃣~5️⃣ 이모지 반응 수집 → EMA(α=0.15)로 선호도 업데이트.
  - `scorer.py`: 3단계 성숙도 모델 (cold: 인기도, warm: 인기+선호, mature: 선호 중심).
  - SQLite 4테이블 (deals, ratings, preferences, source_sites).
- 크롤링 법적 이슈 조사:
  - robots.txt: `/b/hotdeal` 허용.
  - 대법원 2021도1533 (야놀자 vs 여기어때): 기술적 보호조치 미비 시 침입 불인정. 3개 혐의 무죄.
  - 개인 비상업 용도: 저작권법 30조(사적이용), 부정경쟁방지법 카목 비해당.
  - arca.live 운영사: 파라과이 법인(Umanle S.R.L.), 서버 호주. 한국 인터넷 검열 회피 목적 해외 설립. 다만 한국법은 한국 내 이용자에게 여전히 적용.
  - 결론: 저빈도/비상업/공개 데이터 수집의 법적 리스크는 낮음. 실질적 리스크는 IP 차단.
- 핵심 패턴:
  - Python 스크립트가 실제 로직 처리, 에이전트는 스크립트 실행 + Discord 발송만 담당.
  - soxl_alert_bot.py 패턴 재사용 (JSON stdout → cron-agent 소비).
  - 비활성 봇 계정 재활용으로 새 토큰 발급 불필요.

## H. 실제로 배운 것
1) 도구보다 운영구조가 먼저다.
2) 로그는 많다고 좋은 게 아니라, "의미 있는 이벤트"만 남겨야 한다.
3) 자동화는 결국 검증/롤백 없는 순간 무너진다.
4) 멀티에이전트는 역할 계약(스키마)이 없으면 금방 복잡도에 먹힌다.

## I. 3-arm bakeoff 회고 (Hybrid vs Vertex vs Codex)

### 목표(당시)
- 데이터 무결성 게이트 통과 후(`missing=0`, `mismatch=0`)에만 실험 시작.
- 순서 고정: `hybrid-S -> hybrid-M -> vertex-S -> vertex-M -> codex-S -> codex-M`.
- S 통과 전 M 금지, 실패 시 동일 단계 디버그/재시도.
- main/master 금지, exp 브랜치만 사용.
- 재시작/장애에도 이어서 돌 수 있게 상태파일 기반(idempotent) 운영.

### 실제 결과
- 최종 상태: `completed=true`, `phase=done`, `currentStep=codex-M`.
- 6단계 모두 최종 PASS.
- 유일한 명시적 실패 이벤트: `vertex-M` 1회 fail 후 재시도 PASS.
- 이후 tick들은 완료 상태 검증만 수행(no-op).

### "Codex가 가장 안정적으로 보인" 이유(정합성 관점)
- 상태 이벤트 기준으로 Codex 구간은 S/M 모두 1회 PASS로 마무리.
- Vertex는 M에서 실패-회복 이벤트가 남아 변동성이 더 큼.
- Hybrid는 초기 환경 이슈(테스트 러너/플러그인/의존성) 해결 후 통과.
- 결론: 이번 비교는 "모델 성능"보다 "운영 안정성/실행 완주성"에서 Codex가 가장 매끈했다.

### 치명적 실험 리스크 점검(중요)
1) **격리 리스크 (중요)**
   - repos는 분리(`gotothemoon-codex`, `gotothemoon-vertex`) + exp 브랜치로 분리됨.
   - 하지만 핵심 판정 파일(`final_check.py`, `test_dag_validation.py`, 주요 입력 매핑 코드)은 양쪽 해시가 동일했다.
   - 즉 "서로 다른 코드 실험"이라기보다 "동일 코드에 대해 운영 모드/진행 체인 비교" 성격이 강함.

2) **검증 깊이 리스크 (중요)**
   - PASS 근거가 주로 DAG smoke + `final_check.py` 정합성 검사 중심.
   - 이는 인터페이스/흐름 검증엔 유효하지만, 요구사항 전체(E2E 학습 품질/추천 품질) 검증으로는 부족.

3) **자동화 실행 리스크 (중간)**
   - 중간에 gateway restart/timeout, `sessions_send` timeout, subagent ping-pong 등 운용 노이즈 존재.
   - 다만 상태파일/재시도 로직으로 최종 완주에는 성공.

4) **workspace 격리 증빙 리스크 (중간)**
   - 정책상 `workspace-exp-*` 격리/정리가 설계됐고 완료 후 cleanup 수행 기록 있음.
   - 다만 최종 tick에서 `removed=0` 로그가 반복되어, "이미 정리됨"인지 "생성 자체가 제한적"이었는지 추적 증빙은 별도 보강 필요.

### 에이전트 의사결정에서 얻은 인사이트
- 좋은 점:
  - 게이트 우선(data gate first)으로 정책 고정 후 zip gate로 인한 불필요 대기를 제거.
  - 실패 시 동일 단계 고정 재시도로 FSM 규칙 유지.
  - branch policy와 state persistence를 매 tick 재검증해 drift를 줄임.
- 아쉬운 점:
  - subagent 응답 타임아웃이 잦아 동기 실행/직접 실행 fallback이 섞였고, 이로 인해 책임 경계가 흐려지는 구간이 생김.
  - "완료" 판정 근거를 운영 지표와 품질 지표로 분리 보고하지 않아, 해석 혼선이 발생함.

### 다음 실험에서 반드시 보완할 것 (실전 체크)
1) **Treatment 분리 강제**: arm별 코드/설정 diff를 체크섬으로 강제 기록.
2) **검증 2층화**: 운영 정합성 PASS와 모델/품질 PASS를 분리 게이트로 운영.
3) **결정 로그 표준화**: subagent timeout/fallback/재시도 사유를 구조화(JSON) 저장.
4) **재현 팩 고정**: 명령, 환경, 시드, 데이터 스냅샷, 결과 해시를 한 번에 export.
5) **완료 조건 명문화**: "흐름 완주"와 "요구사항 충족"을 다른 완료 상태로 분리.
