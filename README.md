# OpenClaw Practical Starter

> ⚠️ **Important**: 이 레포지토리의 모든 예제 코드에서 API 키, 프로젝트 ID, 사용자명은 플레이스홀더입니다. 실제 사용 시 본인의 값으로 변경해야 합니다.
> - `~/` 경로는 여러분의 홈 디렉토리를 의미합니다
> - `YOUR-PROJECT-ID`, `YOUR-API-KEY` 등은 실제 값으로 교체하세요
> - 모든 민감한 정보는 환경변수로 관리하는 것을 권장합니다

---

## OpenClaw란?

**OpenClaw**는 클라우드 VM 위에서 동작하는 **AI 에이전트 오케스트레이션 플랫폼**이다.

단순한 챗봇이나 단발성 CLI 도구가 아니라, 여러 AI 에이전트를 동시에 운영하고 서로 협력하게 만드는 **운영 인프라**다. 개발자가 "에이전트에게 역할을 부여하고, 스케줄을 설정하고, 산출물을 관리하는" 전 과정을 하나의 플랫폼에서 처리한다.

### 핵심 개념 한 줄 요약

| 개념 | 설명 |
|------|------|
| **Gateway** | 모든 에이전트 요청을 중계하는 로컬 서버 (systemd 서비스로 상시 실행) |
| **Agent** | 역할/규칙/모델이 할당된 AI 실행 단위. 각자 독립된 workspace를 가진다 |
| **Workspace** | 에이전트의 AGENTS.md, SOUL.md 등 역할 정의 파일이 있는 폴더 |
| **Cron** | 에이전트가 주기적으로 실행하는 예약 작업 스케줄러 |
| **Airlock** | 에이전트 작업 산출물을 기록하고 분류하는 저장소 |
| **Channel** | Discord 등 외부 메시징 플랫폼과의 연동 인터페이스 |

### 지원하는 LLM 프로바이더

- **Anthropic**: Claude Haiku, Claude Sonnet 등 (API key 방식)
- **Google Vertex AI**: Gemini 2.5 Pro, Gemini 2.0 Flash 등 (LiteLLM 프록시 경유)
- **OpenAI Codex**: gpt-5.3-codex 등 (OAuth 방식)
- **DeepSeek**: deepseek-reasoner, deepseek-chat (API key 방식)
- **Ollama**: 로컬 모델 (exaone, qwen, deepseek-r1 등)

---

## 누가, 왜 사용하는가

### 이런 상황이라면 OpenClaw가 맞다

- **Mac Mini 없이 AI 에이전트를 24시간 돌리고 싶다**: GCP 같은 클라우드 VM에서 동일한 환경을 더 저렴하게 구축할 수 있다.
- **에이전트 하나로는 역부족이다**: 코딩 에이전트, 학습 에이전트, 재무 분석 에이전트 등 역할을 분리하면 품질과 안정성이 올라간다.
- **"에이전트가 매일 밤 뭔가를 자동으로 해줬으면"**: cron 스케줄러로 nightly 작업, 모니터링, 요약 생성 등을 자동화할 수 있다.
- **작업 기록이 사라지는 게 아깝다**: Airlock 시스템으로 모든 에이전트 산출물을 구조화해서 보관하고 검색할 수 있다.
- **비용 걱정 없이 강력한 모델을 쓰고 싶다**: Vertex AI + LiteLLM 조합으로 GCP 무료 크레딧 기간에 Gemini Pro 등을 사실상 무료로 사용할 수 있다.

### 주요 이점

1. **Mac Mini 불필요**: GCP e2-highmem-2 기준 월 ~$70-80로 24시간 운영. 스팟 VM 활용 시 추가 절감 가능.
2. **멀티에이전트 네이티브**: 에이전트 간 위임(handoff), 역할 분리, 중앙 오케스트레이션을 기본 지원.
3. **Tailscale 네트워크**: 공개 IP 없이도 안전하게 원격 접속. VSCode Remote-SSH로 로컬처럼 개발 가능.
4. **다양한 LLM 연동**: Anthropic, Vertex AI, Codex, DeepSeek, Ollama 등을 에이전트마다 다른 모델로 운영 가능.
5. **운영 안정성**: Gateway 자동 재시작, 이벤트 모니터링, 중복 억제, 상태 점검이 내장되어 있다.

---

## 이 가이드의 구조

이 레포는 **OpenClaw를 처음 접하는 개발자가 단계적으로 실전 운영 환경을 구축**할 수 있도록 설계되었다. 시행착오를 줄이고, 비용/운영/확장성을 한 번에 잡는 것이 목표다.

### 권장 학습 순서

| 단계 | 문서 | 목표 |
|------|------|------|
| 0 | [OpenClaw란 무엇인가](docs/00-what-is-openclaw-and-install.md) | OpenClaw 개념 이해 + 설치 |
| 1 | [Quickstart (30-45분)](docs/00-quickstart-15min.md) | 설치 후 첫 동작 확인 |
| 2 | [GCP 비용/환경 세팅](docs/01-gcp-cost-setup.md) | 클라우드 VM 비용 최적화 |
| 3 | [Tailscale + VSCode 설정](docs/02-tailscale-vscode.md) | 원격 개발 환경 구성 |
| 4 | [Vertex AI + LiteLLM](docs/03-vertex-litellm.md) | Vertex AI + LiteLLM 연동 |
| 5 | [OpenAI Codex 운영](docs/04-codex-pro.md) | OpenAI Codex 운영 |
| 6 | [멀티에이전트 구조](docs/06-multi-agent-architecture.md) | 멀티에이전트 구조 설계 |
| 7 | [Airlock-first 운영](docs/07-airlock-first-ops.md) | Airlock 일일 운영 루프 |
| 심화 | [심화 가이드](docs/) | 도메인별 확장 (Discord, RAG, 음성 등) |
| 참고 | [실전 운영 로그](docs/99-what-i-did-real-world-log.md) | 실전 운영 시행착오 기록 |

---

## 이 레포가 해결하는 것

- GCP VM + Tailscale + VSCode 원격 개발로 빠르게 환경 세팅
- Vertex/LiteLLM + Codex 운영 조합 비교/적용
- 멀티에이전트(도메인 + 중앙 cron) 운영 패턴
- Airlock-first 기록/분류/학습 큐/회고 자동화
- 스키마 기반 handoff 및 품질 지표(KPI) 운영

---

## 빠른 시작

1. [OpenClaw란 무엇인가](docs/00-what-is-openclaw-and-install.md) - OpenClaw 개념 이해 및 설치
2. [Quickstart (30-45분)](docs/00-quickstart-15min.md) - 설치 후 첫 동작 확인
3. [GCP 비용/환경 세팅](docs/01-gcp-cost-setup.md) - VM 비용 최적화
4. [Tailscale + VSCode](docs/02-tailscale-vscode.md) - 원격 개발 환경
5. [Vertex AI + LiteLLM](docs/03-vertex-litellm.md) 또는 [OpenAI Codex](docs/04-codex-pro.md) - LLM 연동
6. [멀티에이전트 구조](docs/06-multi-agent-architecture.md) - 에이전트 분리
7. [Airlock-first 운영](docs/07-airlock-first-ops.md) - 일일 운영 루프
8. 실전 확장: [심화 가이드 목록](docs/) 참고

릴리즈 전 점검은 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) 참고.

---

## 폴더 구조

```
.
├── docs/          # 실전 가이드 문서 (단계별 학습)
├── templates/     # 에이전트/기록 템플릿 (AGENTS.md, SOUL.md 등)
├── schemas/       # handoff/index JSON 스키마
├── scripts/       # 운영 자동화 샘플 스크립트
└── examples/      # 도메인별 예시 구조
    ├── cron-agent/    # 중앙 스케줄러 오케스트레이터
    ├── study-agent/   # 학습 큐 큐레이션 + 간격 반복
    ├── voice-agent/   # STT/TTS 음성 파이프라인
    └── deals-agent/   # 핫딜 크롤링 + 개인화 추천 알림
```

### 예제 에이전트

- [cron-agent](examples/cron-agent/) - 중앙 스케줄러와 자동화 오케스트레이터
- [study-agent](examples/study-agent/) - 학습 큐 관리와 간격 반복 학습
- [voice-agent](examples/voice-agent/) - 음성 인터페이스 (STT/TTS) 파이프라인
- [deals-agent](examples/deals-agent/) - 핫딜 모니터링과 개인화 알림

---

## 심화 가이드

- [Extension vs Agent 판단 기준](docs/05-extension-vs-agent.md) - 언제 Extension을 쓰고 언제 Agent를 쓸까
- [RAG + Studybot 연동](docs/08-rag-studybot.md) - RAG 시스템과 학습봇 구축
- [Discord 채널봇 설정](docs/09-discord-channel-bot-setup.md) - Discord 연동 설정
- [음성 코딩 STT/TTS](docs/10-voice-coding-stt-tts.md) - 음성 인터페이스 구축
- [Google Cloud 설정](docs/11-google-cloud-setup.md) - GCP 상세 설정
- [RAG Privacy Sanitizer](docs/12-rag-privacy-sanitizer.md) - RAG 개인정보 보호
- [서브에이전트 팀 운영](docs/13-subagent-orchestration.md) - 복잡한 작업 위임 구조
- [프롬프트 세팅 가이드](docs/14-openclaw-prompt-setup-and-tools.md) - 에이전트 프롬프트 최적화
- [메모리와 컨텍스트 관리](docs/15-agent-memory-and-context-management.md) - 에이전트 메모리 관리

---

## 운영 원칙 (요약)

- **단일 거대 에이전트보다 역할 분리 + 중앙 오케스트레이션**: 에이전트 하나가 모든 것을 하면 컨텍스트가 오염된다. 역할을 나누고 handoff schema로 계약을 명확히 한다.
- **작업 산출물은 Airlock 우선 기록**: 에이전트의 모든 산출물은 즉시 사라지지 않도록 Airlock에 기록한다. 나중에 검색/학습/회고에 활용한다.
- **최소 변경 + 검증 + 롤백 경로 확보**: 자동화는 검증/롤백 없는 순간 무너진다. 매 변경에 백업을 만들고 되돌릴 수 있는 경로를 둔다.

---

## Contributors

이 프로젝트는 다음 분들의 기여로 만들어졌습니다:

- **[@Sudkorea](https://github.com/Sudkorea)** - 프로젝트 생성자, OpenClaw 실전 운영 경험 공유

### 도구 및 기술 스택

문서 작성 및 코드 개발 과정에서 다양한 AI 도구들을 활용했습니다:
- **Claude (Anthropic)** - 문서 구조화 및 마크다운 작성
- **OpenAI Codex** - 코드 예제 생성 및 스크립트 작성
- **AntiGravity** - 아키텍처 설계 및 다이어그램 구성
- **Cursor** - 실시간 코드 리뷰 및 개선 제안

*성능 비교 및 최적의 워크플로우 구축을 위해 여러 AI 도구를 병행 사용했습니다.*

### 기여하기

이 프로젝트에 기여하고 싶으시다면:
1. Fork 후 PR을 보내주세요
2. Issue에 개선 사항을 제안해주세요
3. 실전 사례를 공유해주세요

---

## 라이선스

MIT License - 자유롭게 사용하고 수정하실 수 있습니다.
