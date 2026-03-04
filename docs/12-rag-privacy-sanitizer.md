# 12. RAG 개인정보 제거 세팅

## 목적
원본 노트는 유지하면서, RAG 인덱싱용 데이터는 안전하게 마스킹.

---

## 1) 2+1 구조
- 원본(private): obsidian-vault
- 안전 미러(rag-safe): obsidian-vault-rag-safe
- 검색 대상: aistudy + rag-safe만

## 2) sanitize 스크립트
- 예시 경로:
  - `~/.openclaw/workspace-caine-agent/scripts/sanitize_obsidian_for_rag.py`

동작:
- 제외: .git, .obsidian, airlock, 바이너리 일부
- 마스킹: 이메일/전화/주소/토큰/API key 패턴
- 리포트 출력: sanitize report json

## 3) 운영 정책
- 원본 vault는 RAG에서 제외
- sanitize는 주기 실행보다, orchestrator 단계에서 1회 실행도 가능
- 실패 시 인덱싱 중단 + 알림

## 4) 체크리스트
- [ ] 민감 패턴 목록 최신화
- [ ] 샘플 문서 마스킹 결과 검토
- [ ] false positive/negative 주간 점검
