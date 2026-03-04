# 03. Vertex AI + LiteLLM 프록시 세팅

## 개요

이 가이드는 Google Cloud의 Vertex AI에 호스팅된 Gemini 모델군을 **LiteLLM 프록시**를 통해 OpenAI 호환 API로 노출하는 전체 설정 과정을 다룬다. 설정이 끝나면 Claude Code(openclaw), 또는 OpenAI API를 기대하는 어떤 툴이든 Vertex AI 모델을 투명하게 호출할 수 있다.

---

## 1. Vertex AI와 LiteLLM이란?

### Vertex AI
Google Cloud Platform(GCP)의 관리형 ML 플랫폼이다. Gemini 시리즈(gemini-2.5-pro, gemini-2.0-flash 등)를 API로 제공하며, 요청 단위 과금 방식이라 서버를 띄울 필요가 없다. GCP 무료 크레딧 기간 중에는 실질적으로 비용 없이 강력한 모델을 사용할 수 있다.

주요 특징:
- 엔터프라이즈급 SLA와 데이터 거버넌스
- 리전별 엔드포인트 선택 가능(지연 최소화)
- IAM 기반 세밀한 접근 제어
- Cloud Logging/Monitoring 연동

### LiteLLM
100개 이상의 LLM 프로바이더를 **단일 OpenAI 호환 API**로 통합해주는 오픈소스 프록시/라이브러리다. LiteLLM 없이 Vertex AI를 직접 호출하면 Google 전용 SDK와 인증 방식을 써야 하는데, LiteLLM이 그 차이를 흡수해준다.

주요 기능:
- OpenAI `v1/chat/completions` 엔드포인트 에뮬레이션
- 모델 폴백(fallback) 및 로드밸런싱
- 비용 추적 및 예산 한도 설정
- 요청/응답 로깅

### 왜 LiteLLM을 프록시로 쓰는가?

Claude Code는 내부적으로 OpenAI 호환 엔드포인트를 기대한다. Vertex AI는 자체 인증 방식(서비스 계정 JSON, gcloud ADC 등)과 API 스키마를 쓰기 때문에 직접 연결하기 어렵다. LiteLLM을 중간에 두면:

1. `localhost:4000` 으로 OpenAI 형식 요청을 보내면
2. LiteLLM이 Vertex AI 형식으로 변환해서 전달하고
3. 응답을 OpenAI 형식으로 다시 변환해서 반환한다

결과적으로 Claude Code는 Vertex AI와 통신하면서도 OpenAI SDK를 그대로 쓸 수 있다.

---

## 2. GCP 프로젝트 설정

### 2.1 프로젝트 생성 또는 선택

```bash
# 기존 프로젝트 목록 확인
gcloud projects list

# 새 프로젝트 생성 (필요한 경우)
gcloud projects create my-openclaw-project --name="OpenClaw Dev"

# 활성 프로젝트 설정
gcloud config set project my-openclaw-project
```

### 2.2 필수 API 활성화

```bash
# Vertex AI API
gcloud services enable aiplatform.googleapis.com

# IAM API (서비스 계정 관리용)
gcloud services enable iam.googleapis.com

# Cloud Resource Manager API
gcloud services enable cloudresourcemanager.googleapis.com
```

활성화 확인:

```bash
gcloud services list --enabled | grep -E "aiplatform|iam"
```

### 2.3 결제 계정 연결 확인

Vertex AI는 결제 계정이 연결되어 있어야 사용 가능하다. 무료 크레딧($300 상당)이 있어도 결제 계정 연결은 필수다.

```bash
# 현재 프로젝트의 결제 정보 확인
gcloud billing projects describe my-openclaw-project
```

GCP 콘솔 > 결제 > 결제 계정 관리에서 연결 상태를 확인할 수 있다.

---

## 3. 서비스 계정 생성 및 JSON 키 발급

### 3.1 서비스 계정 생성

```bash
# 서비스 계정 생성
gcloud iam service-accounts create litellm-vertex-sa \
    --display-name="LiteLLM Vertex AI Service Account" \
    --description="LiteLLM 프록시가 Vertex AI를 호출하는 데 사용하는 계정"
```

### 3.2 필요한 역할 부여

```bash
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="litellm-vertex-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Vertex AI 사용자 역할 부여
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"
```

최소 권한 원칙에 따라 `roles/aiplatform.user`만 부여한다. Admin 역할은 불필요하다.

### 3.3 JSON 키 파일 다운로드

```bash
# 키 파일을 안전한 위치에 저장
mkdir -p ~/.config/gcp-keys
gcloud iam service-accounts keys create ~/.config/gcp-keys/litellm-vertex-sa.json \
    --iam-account=${SA_EMAIL}

# 파일 권한을 소유자 전용으로 제한
chmod 600 ~/.config/gcp-keys/litellm-vertex-sa.json
```

> **주의**: 이 JSON 파일은 GCP 접근 권한을 가진 비밀 키다. `.gitignore`에 추가하고 절대 버전 관리에 포함시키지 않는다.

키 파일 내용 예시(실제 값은 다름):

```json
{
  "type": "service_account",
  "project_id": "my-openclaw-project",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "client_email": "litellm-vertex-sa@my-openclaw-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

---

## 4. LiteLLM 설치 및 구성

### 4.1 Python 환경 준비

```bash
# Python 3.11 이상 권장
python3 --version

# 가상환경 생성 (systemd 서비스에서는 절대 경로 사용)
python3 -m venv /opt/litellm-venv
source /opt/litellm-venv/bin/activate
```

### 4.2 LiteLLM 설치

```bash
# LiteLLM 및 Vertex AI 의존성 설치
pip install 'litellm[proxy]' google-cloud-aiplatform

# 버전 확인
litellm --version
```

### 4.3 config.yaml 작성

LiteLLM의 핵심 설정 파일이다. `/etc/litellm/config.yaml`에 저장한다.

```bash
sudo mkdir -p /etc/litellm
sudo nano /etc/litellm/config.yaml
```

기본 설정 예시:

```yaml
# /etc/litellm/config.yaml

model_list:
  # Gemini 2.5 Pro (고성능 작업용)
  - model_name: gemini-2.5-pro
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

  # gemini-3-pro-preview 별칭 처리
  # 주의: "gemini-3-pro-preview"라는 모델명은 실제 Vertex AI에 존재하지 않는다.
  # Claude Code 설정이나 툴에서 이 이름을 요청하는 경우, 실제로는
  # gemini-2.5-pro로 라우팅되도록 별칭을 설정해야 한다.
  - model_name: gemini-3-pro-preview
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

  # Gemini 2.0 Flash (빠른 응답, 저비용)
  - model_name: gemini-2.0-flash
    litellm_params:
      model: vertex_ai/gemini-2.0-flash-001
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

  # 폴백용 Flash Lite
  - model_name: gemini-flash-lite
    litellm_params:
      model: vertex_ai/gemini-2.0-flash-lite-001
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

litellm_settings:
  # 재시도 설정
  num_retries: 3
  request_timeout: 600

  # 컨텍스트 초과 시 자동 축소
  drop_params: true

  # 비용 추적 활성화
  success_callback: ["langfuse"]  # 선택사항

  # 로깅 레벨
  set_verbose: false

general_settings:
  # 마스터 키 (API 요청 인증용)
  master_key: "sk-my-secret-master-key"

  # 프록시 포트
  port: 4000

  # 요청 타임아웃 (초)
  request_timeout: 600
```

---

## 5. 모델 라우팅 및 폴백 전략

### 5.1 로드밸런싱 설정

여러 리전에 걸쳐 부하를 분산시키면 할당량 초과(429 오류)를 줄일 수 있다.

```yaml
model_list:
  # 동일 모델을 여러 리전에 등록하면 LiteLLM이 자동으로 분산
  - model_name: gemini-2.5-pro
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

  - model_name: gemini-2.5-pro
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: us-east4
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

  - model_name: gemini-2.5-pro
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: europe-west4
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json

litellm_settings:
  # 라우팅 전략: least-busy, latency-based, simple-shuffle, usage-based-routing
  routing_strategy: latency-based-routing

  # 폴백 설정: 특정 모델 실패 시 다른 모델로 자동 전환
  fallbacks:
    - {"gemini-2.5-pro": ["gemini-2.0-flash"]}
    - {"gemini-3-pro-preview": ["gemini-2.5-pro", "gemini-2.0-flash"]}

  # 컨텍스트 초과 시 폴백
  context_window_fallbacks:
    - {"gemini-2.5-pro": ["gemini-2.0-flash"]}
```

### 5.2 gemini-3-pro-preview 별칭 처리 (중요)

일부 프롬프트 템플릿이나 툴이 `gemini-3-pro-preview`라는 모델명을 하드코딩하고 있을 수 있다. 이 모델명은 2026년 2월 현재 Vertex AI에서 실제로 제공되지 않는다. 다음과 같이 별칭을 만들어 `gemini-2.5-pro`로 라우팅한다.

```yaml
model_list:
  # gemini-3-pro-preview 요청 -> 실제로는 gemini-2.5-pro로 처리
  - model_name: gemini-3-pro-preview
    litellm_params:
      model: vertex_ai/gemini-2.5-pro-preview-0506
      vertex_project: my-openclaw-project
      vertex_location: us-central1
      vertex_credentials: /home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json
```

openclaw.json에서 모델명을 명시할 때도 `gemini-3-pro-preview`가 아닌 `gemini-2.5-pro` 또는 LiteLLM에 등록한 정확한 `model_name`을 사용하는 것이 더 안전하다.

---

## 6. systemd 서비스 설정

LiteLLM 프록시를 VM 재시작 후에도 자동으로 기동되도록 systemd 서비스로 등록한다.

### 6.1 서비스 파일 작성

```bash
sudo nano /etc/systemd/system/litellm.service
```

```ini
[Unit]
Description=LiteLLM Proxy Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu

# LiteLLM 실행
ExecStart=/opt/litellm-venv/bin/litellm \
    --config /etc/litellm/config.yaml \
    --port 4000 \
    --num_workers 4

# 재시작 정책
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# 환경 변수 (config.yaml에서 참조하는 경우)
Environment="GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json"
Environment="LITELLM_MASTER_KEY=sk-my-secret-master-key"

# 로그 출력
StandardOutput=journal
StandardError=journal
SyslogIdentifier=litellm

# 보안 강화 (선택)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 6.2 서비스 등록 및 기동

```bash
# systemd 데몬 재로드
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable litellm

# 서비스 시작
sudo systemctl start litellm

# 상태 확인
sudo systemctl status litellm

# 실시간 로그 확인
sudo journalctl -u litellm -f
```

### 6.3 서비스 관리 명령어 참고

```bash
# 설정 변경 후 재시작
sudo systemctl restart litellm

# 일시 정지
sudo systemctl stop litellm

# 로그 조회 (최근 100줄)
sudo journalctl -u litellm -n 100 --no-pager

# 에러만 필터링
sudo journalctl -u litellm -p err --no-pager
```

---

## 7. 비용 관리 및 할당량

### 7.1 Vertex AI 할당량 확인

```bash
# 현재 할당량 확인 (gcloud)
gcloud compute project-info describe --project=my-openclaw-project

# Vertex AI 할당량은 GCP 콘솔에서 확인
# IAM 및 관리자 > 할당량 > "Vertex AI" 검색
```

### 7.2 LiteLLM 예산 한도 설정

config.yaml에 사용자/키별 예산을 설정할 수 있다.

```yaml
litellm_settings:
  # 전체 예산 한도 (USD)
  max_budget: 50.0

  # 예산 리셋 주기: daily, weekly, monthly
  budget_duration: monthly

general_settings:
  master_key: "sk-my-secret-master-key"

# 개별 API 키에 예산 설정 (LiteLLM 대시보드 또는 API로 관리)
# 아래는 예시로, 실제 적용은 /key/generate 엔드포인트를 사용
```

### 7.3 GCP 결제 알림 설정

```bash
# 월 $20 초과 시 알림 (GCP 콘솔에서 설정 권장)
# 결제 > 예산 및 알림 > 예산 만들기
```

예산 알림은 GCP 콘솔 UI에서 설정하는 것이 가장 간단하다:
1. GCP 콘솔 > 결제 > 예산 및 알림
2. "예산 만들기" 클릭
3. 금액과 알림 임계값 설정(50%, 90%, 100%)
4. 이메일 알림 수신자 지정

### 7.4 모델별 비용 비교 (2026년 2월 기준 참고값)

| 모델 | 입력 (1M 토큰) | 출력 (1M 토큰) | 적합한 용도 |
|------|--------------|--------------|-----------|
| gemini-2.5-pro | ~$3.50 | ~$10.50 | 복잡한 추론, 아키텍처 설계 |
| gemini-2.0-flash | ~$0.075 | ~$0.30 | 빠른 코드 완성, 간단한 질문 |
| gemini-2.0-flash-lite | ~$0.0375 | ~$0.15 | 대량 처리, 저비용 배치 |

> 정확한 가격은 [GCP Vertex AI 가격 페이지](https://cloud.google.com/vertex-ai/generative-ai/pricing)에서 확인한다.

---

## 8. 설정 테스트

### 8.1 프록시 동작 확인

```bash
# 헬스체크 엔드포인트
curl http://localhost:4000/health

# 등록된 모델 목록 확인
curl http://localhost:4000/models \
  -H "Authorization: Bearer sk-my-secret-master-key"
```

### 8.2 실제 요청 테스트

```bash
# gemini-2.5-pro 테스트
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-my-secret-master-key" \
  -d '{
    "model": "gemini-2.5-pro",
    "messages": [
      {"role": "user", "content": "안녕하세요. 1+1은 무엇인가요?"}
    ],
    "max_tokens": 100
  }'

# gemini-3-pro-preview 별칭 테스트 (gemini-2.5-pro로 라우팅되어야 함)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-my-secret-master-key" \
  -d '{
    "model": "gemini-3-pro-preview",
    "messages": [
      {"role": "user", "content": "Hello, what model are you?"}
    ],
    "max_tokens": 100
  }'
```

### 8.3 openclaw.json에서 LiteLLM 프록시 연결

```json
{
  "apiBaseUrl": "http://localhost:4000/v1",
  "apiKey": "sk-my-secret-master-key",
  "model": "gemini-2.5-pro",
  "largeContextModel": "gemini-2.5-pro",
  "smallFastModel": "gemini-2.0-flash"
}
```

---

## 9. 장애 시 점검 루틴

### 9.1 LiteLLM이 응답하지 않을 때

```bash
# 서비스 상태 확인
sudo systemctl status litellm

# 포트 점유 확인
sudo ss -tlnp | grep 4000

# 프로세스 확인
ps aux | grep litellm

# 강제 재시작
sudo systemctl restart litellm && sleep 3 && sudo systemctl status litellm
```

### 9.2 Vertex AI 인증 실패 시

```bash
# 서비스 계정 키 파일 존재 확인
ls -la ~/.config/gcp-keys/litellm-vertex-sa.json

# 키 파일이 유효한 JSON인지 확인
python3 -c "import json; json.load(open('/home/ubuntu/.config/gcp-keys/litellm-vertex-sa.json')); print('JSON OK')"

# 직접 인증 테스트
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcp-keys/litellm-vertex-sa.json \
python3 -c "
import google.auth
creds, project = google.auth.default()
print(f'Project: {project}')
print('Auth OK')
"
```

### 9.3 할당량 초과(429) 대응

```yaml
# config.yaml에서 재시도 및 폴백 강화
litellm_settings:
  num_retries: 5
  retry_after: 30  # 재시도 전 대기 시간 (초)

  fallbacks:
    - {"gemini-2.5-pro": ["gemini-2.0-flash", "gemini-flash-lite"]}

  context_window_fallbacks:
    - {"gemini-2.5-pro": ["gemini-2.0-flash"]}
```

---

## 체크리스트

- [ ] GCP 프로젝트 생성 및 결제 계정 연결
- [ ] Vertex AI API 활성화 (`aiplatform.googleapis.com`)
- [ ] 서비스 계정 생성 및 `roles/aiplatform.user` 역할 부여
- [ ] JSON 키 파일 다운로드 및 권한 설정 (`chmod 600`)
- [ ] Python 가상환경 생성 및 LiteLLM 설치
- [ ] `/etc/litellm/config.yaml` 작성 (모델명, 프로젝트ID, 리전 확인)
- [ ] `gemini-3-pro-preview` 별칭 설정 (필요한 경우)
- [ ] systemd 서비스 등록 및 기동 확인
- [ ] `curl localhost:4000/health` 로 헬스체크 통과
- [ ] 실제 요청 테스트 통과
- [ ] openclaw.json에 `apiBaseUrl: http://localhost:4000/v1` 설정
- [ ] GCP 결제 알림 설정 (월 예산 한도)
