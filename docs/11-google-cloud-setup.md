# 11. Google Cloud 계정 세팅 (OpenClaw/Voice/RAG 공용)

## 1) 프로젝트/결제 기본
- 새 프로젝트 생성
- 결제 계정 연결(무료 크레딧 확인)
- 예산 알림(Budget Alert) 필수

## 2) IAM/서비스 계정
- 서비스 계정 1개 생성(용도별 분리 권장)
- 키 JSON 발급 후 로컬 안전 경로 저장
- 예: `~/.openclaw/secrets/<project>.json`

주의: 키를 git에 절대 커밋하지 말 것.

## 3) API 활성화
- Speech-to-Text
- Text-to-Speech
- (필요 시) Vertex AI

## 4) 로컬/VM 환경 변수
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_PROJECT_ID`

## 5) 운영 팁
- 개발/운영 프로젝트 분리
- 월 예산 상한 및 경보 설정
- 비용 초과 시 fallback-safe 모드 강제
