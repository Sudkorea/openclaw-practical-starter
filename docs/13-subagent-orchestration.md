# 13. 서브에이전트 팀 오케스트레이션

## 핵심 개념
- 라우터: 어떤 에이전트가 할지 결정
- PM: 작업 쪼개기/검증 계획
- specialist: 구현/테스트/리뷰
- cron-agent: 스케줄/상태/리마인드 중앙관리

---

## 권장 체인
`request -> router -> pm -> specialist -> pm verify -> final`

---

## handoff 패킷 표준
필수 필드:
- objective
- scope(files/commands)
- constraints(runtime/security/style/budget)
- acceptance(tests/lint/manual)
- risk(low/medium/high)

스키마:
- `schemas/handoff_packet.schema.json`

---

## 운영 규칙
1. 긴 작업은 서브에이전트 위임
2. 동일 이벤트 중복 알림 금지
3. 완료 보고 전 검증 로그 확인
4. critical은 메인 채널 에스컬레이션

---

## 실패 패턴
- 무분별한 병렬화: 컨텍스트 충돌/비용 폭증
- 역할 중복: 누가 책임자인지 불명확
- 검증 없는 완료선언: 신뢰 하락

해법: 역할 분리 + 계약(handoff schema) + KPI.
