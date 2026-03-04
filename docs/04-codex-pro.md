# 04. Codex Pro (OpenAI 코딩 모델) 운영 가이드

## 개요

이 가이드는 OpenAI의 코드 특화 모델인 **gpt-5.3-codex**(272k 컨텍스트)를 openclaw 환경에서 활용하는 방법을 다룬다. Vertex AI + Gemini 조합과 어떻게 다르고, 언제 어떤 모델을 선택해야 하는지, 그리고 실제 운영 시 주의할 점들을 정리한다.

---

## 1. Codex란 무엇인가?

**Codex**는 OpenAI가 코드 생성 및 이해에 특화해서 훈련한 모델 계열이다. 초기 Codex(2021년)는 GitHub Copilot의 기반이 되었으나, 이후 GPT-4 계열로 통합되었다. 2025년 이후 OpenAI는 다시 코드 작업에 최적화된 모델로 `gpt-5.3-codex`를 출시했다.

### gpt-5.3-codex의 주요 특징

- **272,000 토큰 컨텍스트 윈도우**: 대형 코드베이스 전체를 한 번에 처리 가능
- **코드 추론 최적화**: 버그 탐지, 리팩토링, 테스트 생성에서 일반 모델 대비 높은 정확도
- **함수 호출(Function Calling) 지원**: 툴 기반 에이전트 워크플로우에 최적화
- **구조화된 출력(Structured Output) 지원**: JSON 스키마 기반 응답 보장
- **코드 실행 환경 인식**: 언어별 컨텍스트(Python, TypeScript, Go, Rust 등)를 자동으로 파악

### GPT-4o / GPT-4.1 대비 차이점

| 특성 | gpt-5.3-codex | gpt-4.1 / gpt-4o |
|------|--------------|-----------------|
| 주 용도 | 코드 특화 | 범용 |
| 컨텍스트 | 272k 토큰 | 128k 토큰 |
| 코드 추론 | 최고 수준 | 우수 |
| 자연어 대화 | 양호 | 최고 수준 |
| 비용 (입력) | 높음 | 중간 |

---

## 2. Codex vs Vertex AI 모델: 언제 무엇을 쓸까?

### Codex(OpenAI)를 선택해야 할 때

- **대규모 코드베이스 리팩토링**: 수십만 줄의 코드를 맥락과 함께 처리해야 할 때. 272k 컨텍스트가 결정적으로 유리하다.
- **복잡한 버그 추적**: 여러 파일에 걸친 스택 트레이스와 코드를 동시에 분석할 때.
- **테스트 코드 자동 생성**: 기존 구현 코드 전체를 읽고 엣지케이스까지 커버하는 테스트를 만들 때.
- **정밀한 함수 호출 에이전트**: JSON 스키마를 엄격하게 준수해야 하는 툴 에이전트를 만들 때.
- **GCP 크레딧 소진 후**: 무료 크레딧이 떨어지면 Vertex AI 비용이 크게 늘어난다. 이때 OpenAI 직접 호출이 더 경제적일 수 있다.

### Vertex AI(Gemini)를 선택해야 할 때

- **GCP 무료 크레딧 기간**: $300 크레딧이 살아있는 동안은 Gemini로 비용을 아낀다.
- **대량의 빠른 작업**: Gemini 2.0 Flash는 응답속도와 비용 면에서 극히 유리하다.
- **멀티모달 입력 처리**: 이미지나 문서를 코드와 함께 분석해야 할 때 Gemini가 강점을 보인다.
- **긴 문서/주석 처리**: Gemini 2.5 Pro의 100만 토큰 컨텍스트는 Codex를 능가한다.

### 실용적인 판단 기준

```
컨텍스트 크기가 결정적인가?
  - 128k 이하 -> Gemini 2.5 Pro 또는 Codex 둘 다 가능
  - 128k~272k -> Codex 선택
  - 272k 초과 -> Gemini 2.5 Pro (100만 토큰)

예산이 최우선인가?
  - GCP 크레딧 있음 -> Gemini Flash 우선
  - 크레딧 없음, 저비용 필요 -> Gemini Flash 유료 사용
  - 품질이 최우선 -> Codex

코드 특화 작업(리팩토링, 테스트 생성)인가?
  - 예 -> Codex 우선 고려
  - 아니오(일반 대화, 요약, 분석) -> Gemini 2.5 Pro
```

---

## 3. OpenAI API 접근 설정

### 3.1 OpenAI 계정 및 API 키 발급

1. [platform.openai.com](https://platform.openai.com) 에 접속하여 계정을 생성한다.
2. 결제 정보를 등록한다. 선불 크레딧 방식으로 충전하면 비용 관리가 쉽다.
3. API 키를 발급한다:
   - Dashboard > API keys > "Create new secret key"
   - 키 이름: `openclaw-dev` (나중에 식별하기 위한 이름)
   - 키는 한 번만 표시되므로 바로 복사해서 저장한다.

### 3.2 API 키 안전하게 저장

```bash
# 키를 환경 변수 파일에 저장 (홈 디렉토리)
mkdir -p ~/.config/openclaw
cat > ~/.config/openclaw/openai.env << 'EOF'
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
EOF

# 파일 권한 제한
chmod 600 ~/.config/openclaw/openai.env

# 쉘 프로파일에서 자동 로드 (~/.bashrc 또는 ~/.zshrc)
echo 'source ~/.config/openclaw/openai.env' >> ~/.bashrc
source ~/.bashrc

# 설정 확인
echo $OPENAI_API_KEY | head -c 20
# 출력: sk-proj-xxxxxxxxxxxxxxx (앞부분만 표시됨)
```

> **중요**: `OPENAI_API_KEY`를 코드에 직접 하드코딩하거나 Git 저장소에 커밋하지 않는다. 반드시 환경 변수 또는 시크릿 관리 도구를 사용한다.

### 3.3 사용 한도 및 Tier 확인

```bash
# API로 현재 사용 현황 확인
curl https://api.openai.com/v1/usage \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json"
```

OpenAI의 Rate Limit은 계정 Tier에 따라 다르다:

| Tier | 월 지출 조건 | RPM (gpt-5.3-codex) | TPM |
|------|------------|---------------------|-----|
| Free | 없음 | 3 | 40,000 |
| Tier 1 | $5 이상 충전 | 500 | 200,000 |
| Tier 2 | $50 이상 지출 | 5,000 | 2,000,000 |
| Tier 3 | $100 이상 지출 | 5,000 | 4,000,000 |

에이전트 기반 코딩 작업을 원활히 하려면 **Tier 1 이상**이 필요하다.

---

## 4. openclaw.json 설정

### 4.1 기본 설정 (OpenAI 직접 연결)

```json
{
  "apiProvider": "openai",
  "apiKey": "${OPENAI_API_KEY}",
  "model": "gpt-5.3-codex",
  "largeContextModel": "gpt-5.3-codex",
  "smallFastModel": "gpt-4o-mini",
  "maxTokens": 16384,
  "temperature": 0.1
}
```

실제 파일에서는 환경 변수를 직접 확장해서 쓰거나, 다음과 같이 구체적인 값을 설정한다:

```json
{
  "apiProvider": "openai",
  "apiBaseUrl": "https://api.openai.com/v1",
  "apiKey": "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx",
  "model": "gpt-5.3-codex",
  "largeContextModel": "gpt-5.3-codex",
  "smallFastModel": "gpt-4o-mini",
  "maxTokens": 16384,
  "contextWindow": 272000,
  "temperature": 0.1,
  "maxRetries": 3,
  "retryDelay": 5000
}
```

### 4.2 LiteLLM을 통해 OpenAI + Vertex AI 혼합 사용

LiteLLM 프록시가 이미 설정되어 있다면, OpenAI와 Vertex AI를 한 config.yaml에서 관리하고 openclaw는 프록시만 바라보게 할 수 있다.

LiteLLM config.yaml에 OpenAI 모델 추가:

```yaml
# /etc/litellm/config.yaml (기존 Vertex AI 설정에 추가)

model_list:
  # 기존 Vertex AI 모델들 (생략)...

  # OpenAI Codex 추가
  - model_name: codex
    litellm_params:
      model: openai/gpt-5.3-codex
      api_key: "os.environ/OPENAI_API_KEY"

  # 비용 효율적인 소형 모델
  - model_name: gpt-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: "os.environ/OPENAI_API_KEY"
```

이 경우 openclaw.json은 프록시를 통해 모든 모델에 접근:

```json
{
  "apiBaseUrl": "http://localhost:4000/v1",
  "apiKey": "sk-my-secret-master-key",
  "model": "codex",
  "largeContextModel": "codex",
  "smallFastModel": "gpt-mini"
}
```

### 4.3 모델 선택 전략 설정

작업 유형에 따라 다른 모델을 쓰도록 openclaw를 구성할 수 있다:

```json
{
  "apiBaseUrl": "http://localhost:4000/v1",
  "apiKey": "sk-my-secret-master-key",

  "model": "gemini-2.5-pro",

  "taskModelOverrides": {
    "code_generation": "codex",
    "code_review": "codex",
    "refactoring": "codex",
    "test_generation": "codex",
    "documentation": "gemini-2.5-pro",
    "research": "gemini-2.5-pro",
    "quick_question": "gemini-2.0-flash"
  },

  "contextThresholds": {
    "useCodexAboveTokens": 100000,
    "useFlashBelowTokens": 10000
  }
}
```

---

## 5. 모델 선택: gpt-5.3-codex와 272k 컨텍스트 활용

### 5.1 272k 컨텍스트를 효과적으로 사용하는 방법

```bash
# 프로젝트 전체를 한 번에 컨텍스트에 넣는 예시
# (Claude Code가 자동으로 처리하지만 원리를 이해하기 위한 예시)

# 토큰 수 추정 (대략적으로 4문자 = 1토큰)
wc -c src/**/*.py | tail -1
# 예: 800,000 bytes / 4 = 200,000 토큰 -> 272k 컨텍스트에 여유 있게 들어감
```

컨텍스트 전략:
- **100k 이하 코드베이스**: 전체 코드를 컨텍스트에 포함. Codex의 전체 파악 능력이 최대로 발휘됨.
- **100k~200k 코드베이스**: 관련 모듈만 선택적으로 포함. openclaw의 RAG 기능 활용.
- **200k 이상 코드베이스**: 파일 단위 순차 처리 또는 Gemini 2.5 Pro(100만 토큰) 검토.

### 5.2 코드 특화 프롬프트 패턴

Codex와 함께 효과적인 프롬프트 작성법:

```
# 리팩토링 요청 패턴
"다음 코드를 [목표]에 맞게 리팩토링해줘.
변경 사항마다 왜 그렇게 바꿨는지 한 줄 주석으로 설명해줘.
기존 테스트가 모두 통과해야 해."

# 버그 탐지 패턴
"다음 코드에서 [증상]이 발생하고 있어.
스택 트레이스: [에러 내용]
관련 코드를 읽고 가능한 원인 3가지를 우선순위 순으로 나열해줘."

# 테스트 생성 패턴
"다음 함수에 대한 pytest 테스트를 작성해줘.
정상 케이스, 엣지 케이스, 오류 케이스를 포함해야 해.
각 테스트에 독립적인 픽스처를 사용해줘."
```

---

## 6. 비용 비교와 최적화

### 6.1 모델별 비용 비교 (2026년 2월 기준 참고값)

| 모델 | 입력 (1M 토큰) | 출력 (1M 토큰) | 272k 요청 1회 비용(예시) |
|------|--------------|--------------|----------------------|
| gpt-5.3-codex | ~$15.00 | ~$60.00 | ~$4.10 (입력 full 기준) |
| gpt-4o | ~$5.00 | ~$15.00 | ~$1.36 |
| gpt-4o-mini | ~$0.15 | ~$0.60 | ~$0.04 |
| gemini-2.5-pro | ~$3.50 | ~$10.50 | ~$0.95 |
| gemini-2.0-flash | ~$0.075 | ~$0.30 | ~$0.02 |

> 이 수치는 참고값이며 OpenAI 가격 정책은 수시로 변경된다. 최신 가격은 [platform.openai.com/pricing](https://platform.openai.com/pricing)에서 확인한다.

### 6.2 비용 최소화 전략

**1단계: 작업 분류**

모든 요청을 Codex로 보내면 비용이 빠르게 쌓인다. 다음과 같이 분류한다:

```
고비용 모델(Codex) 적합:
  - 대형 코드베이스 전체 리팩토링
  - 복잡한 아키텍처 설계 검토
  - 다파일 버그 추적

중간 비용(Gemini 2.5 Pro, gpt-4o) 적합:
  - 코드 리뷰 (단일 파일)
  - 새 기능 구현 (명세가 명확할 때)
  - 문서 작성

저비용(Gemini Flash, gpt-4o-mini) 적합:
  - 코드 설명 요청
  - 간단한 문법 수정
  - 변수/함수명 제안
  - 짧은 Q&A
```

**2단계: 컨텍스트 크기 최적화**

```python
# 에이전트 코드 예시: 파일 크기에 따라 모델 자동 선택
def select_model(file_size_bytes: int, task_type: str) -> str:
    token_estimate = file_size_bytes // 4

    if task_type in ["refactor", "test_gen"] and token_estimate > 50000:
        return "gpt-5.3-codex"
    elif token_estimate < 10000:
        return "gemini-2.0-flash"
    else:
        return "gemini-2.5-pro"
```

**3단계: OpenAI 사용 한도 설정**

```bash
# OpenAI 대시보드에서 월 한도 설정
# platform.openai.com > Settings > Limits
# "Set a monthly budget" 에서 금액 설정

# API로 현재 사용량 확인
curl https://api.openai.com/v1/usage \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json"
```

### 6.3 실제 월간 비용 시뮬레이션

개발자 1명, 하루 4시간 활발한 코딩 세션 기준:

```
시나리오 A: Codex 위주
  - Codex 요청: 50회/일 × 30일 = 1,500회
  - 평균 입력 30k 토큰, 출력 2k 토큰
  - 비용: 1,500 × (30,000/1M × $15 + 2,000/1M × $60)
  - = 1,500 × ($0.45 + $0.12) = 1,500 × $0.57 = ~$855/월

시나리오 B: 혼합 전략 (권장)
  - Codex: 10회/일 (복잡한 작업만)
  - Gemini 2.5 Pro: 30회/일
  - Gemini Flash: 100회/일
  - 비용: (300 × $0.57) + (900 × $0.10) + (3,000 × $0.002)
  - = $171 + $90 + $6 = ~$267/월

시나리오 C: Vertex 무료 크레딧 소진 전
  - Gemini 위주 사용, Codex 5회/일만
  - 비용: (150 × $0.57) + 나머지는 무료 크레딧
  - = ~$85/월 (크레딧 소진 후)
```

---

## 7. Rate Limiting 및 에러 처리

### 7.1 OpenAI Rate Limit 이해

OpenAI API는 분당 요청 수(RPM)와 분당 토큰 수(TPM)로 제한한다. 한도 초과 시 `429 Too Many Requests` 오류가 반환된다.

```json
{
  "error": {
    "message": "Rate limit reached for gpt-5.3-codex in organization org-xxx on tokens per min. Limit: 200000, Used: 195000, Requested: 10000.",
    "type": "tokens",
    "code": "rate_limit_exceeded"
  }
}
```

### 7.2 LiteLLM을 통한 자동 재시도 설정

```yaml
# /etc/litellm/config.yaml

litellm_settings:
  num_retries: 5

  # OpenAI Rate Limit 대응: Gemini로 자동 폴백
  fallbacks:
    - {"codex": ["gemini-2.5-pro", "gemini-2.0-flash"]}
    - {"gpt-mini": ["gemini-2.0-flash"]}

  # 재시도 전 대기 시간 (초)
  retry_after: 60

  # 컨텍스트 초과 시 자동 처리
  context_window_fallbacks:
    - {"codex": ["gemini-2.5-pro"]}
```

### 7.3 수동 재시도 로직 (스크립트 작성 시)

```python
import openai
import time
from openai import RateLimitError, APITimeoutError

client = openai.OpenAI()

def call_codex_with_retry(
    messages: list,
    model: str = "gpt-5.3-codex",
    max_retries: int = 5,
    base_delay: float = 1.0
) -> str:
    """
    Exponential backoff으로 OpenAI API 호출 재시도
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4096,
                temperature=0.1
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            # Retry-After 헤더에서 대기 시간 파악
            retry_after = getattr(e, 'retry_after', None)
            wait_time = retry_after if retry_after else (base_delay * (2 ** attempt))

            print(f"Rate limit 초과. {wait_time}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
            time.sleep(wait_time)

        except APITimeoutError:
            if attempt == max_retries - 1:
                raise

            wait_time = base_delay * (2 ** attempt)
            print(f"타임아웃 발생. {wait_time}초 후 재시도...")
            time.sleep(wait_time)

    raise RuntimeError("최대 재시도 횟수 초과")
```

### 7.4 스트리밍 응답으로 타임아웃 방지

Codex는 긴 코드를 생성할 때 응답이 수십 초 걸릴 수 있다. 스트리밍을 사용하면 부분 응답을 즉시 받아볼 수 있다:

```python
import openai

client = openai.OpenAI()

def stream_codex_response(messages: list) -> str:
    """스트리밍으로 Codex 응답을 받아 실시간 출력"""
    full_response = ""

    with client.chat.completions.stream(
        model="gpt-5.3-codex",
        messages=messages,
        max_tokens=8192,
        temperature=0.1
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_response += text

    print()  # 줄바꿈
    return full_response
```

openclaw.json에서 스트리밍 활성화:

```json
{
  "apiBaseUrl": "https://api.openai.com/v1",
  "apiKey": "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx",
  "model": "gpt-5.3-codex",
  "streamResponse": true,
  "streamTimeout": 300
}
```

---

## 8. 코드 중심 워크로드 모범 사례

### 8.1 대형 파일 처리 전략

272k 컨텍스트를 가장 효과적으로 쓰는 패턴:

```bash
# 1. 파일들의 토큰 수를 사전에 추정
for f in src/**/*.py; do
  chars=$(wc -c < "$f")
  tokens=$((chars / 4))
  echo "$tokens $f"
done | sort -rn | head -20
# 가장 큰 파일들을 파악하고 컨텍스트 계획을 세운다
```

```
좋은 패턴:
  - 수정 대상 파일 + 직접 의존하는 파일들만 포함
  - 테스트 파일은 별도 요청으로 분리
  - 설정 파일, 빌드 스크립트는 필요할 때만 포함

피해야 할 패턴:
  - 무작정 전체 프로젝트를 포함
  - node_modules, .git, __pycache__ 포함
  - 관련 없는 기능의 코드 포함
```

### 8.2 반복 작업 자동화

Codex를 반복 사용하는 배치 작업 패턴:

```python
# 여러 파일에 동일한 리팩토링을 적용하는 스크립트 예시
import os
import openai

client = openai.OpenAI()

def batch_add_type_hints(files: list[str]) -> None:
    """파일 목록에 타입 힌트를 자동으로 추가"""
    for filepath in files:
        with open(filepath, 'r') as f:
            code = f.read()

        # 파일이 너무 크면 건너뜀 (272k 컨텍스트 내에서 처리 가능한지 확인)
        if len(code) > 800000:  # ~200k 토큰 초과
            print(f"건너뜀 (너무 큼): {filepath}")
            continue

        response = client.chat.completions.create(
            model="gpt-5.3-codex",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python expert. Add proper type hints to functions and return modified code only, no explanations."
                },
                {
                    "role": "user",
                    "content": f"Add type hints to all functions:\n\n```python\n{code}\n```"
                }
            ],
            max_tokens=len(code) // 2  # 출력은 보통 입력보다 짧음
        )

        result = response.choices[0].message.content
        # ```python ... ``` 블록 추출
        if "```python" in result:
            result = result.split("```python")[1].split("```")[0].strip()

        with open(filepath, 'w') as f:
            f.write(result)

        print(f"완료: {filepath}")

        # Rate Limit 방지를 위한 짧은 대기
        time.sleep(2)
```

### 8.3 Codex와 함께 작동하는 openclaw 워크플로우

```bash
# 1. 작업 시작 전 컨텍스트 준비
# openclaw가 자동으로 처리하지만 수동으로 설정할 때:
export OPENCLAW_MODEL=gpt-5.3-codex
export OPENCLAW_MAX_CONTEXT=250000  # 272k 중 여유분 남김

# 2. 코드 리뷰 세션
claude "이 PR의 diff를 보고 코드 품질, 잠재적 버그, 성능 문제를 검토해줘"

# 3. 대형 리팩토링
claude "src/auth/ 디렉토리 전체를 읽고 JWT 처리 부분을 최신 best practice로 리팩토링해줘"

# 4. 테스트 생성
claude "src/payment.py의 모든 public 메서드에 대한 pytest 테스트를 tests/test_payment.py에 작성해줘"
```

---

## 9. 설정 테스트 및 검증

### 9.1 API 연결 테스트

```bash
# 기본 연결 테스트
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5.3-codex",
    "messages": [
      {
        "role": "user",
        "content": "def fibonacci(n):\n    # TODO: implement\n    pass\n\nComplete this function."
      }
    ],
    "max_tokens": 200
  }'
```

정상 응답 예시:

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "gpt-5.3-codex",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 28,
    "total_tokens": 53
  }
}
```

### 9.2 컨텍스트 용량 테스트

```python
# 272k 컨텍스트 테스트 스크립트
import openai

client = openai.OpenAI()

# 200k 토큰 분량의 더미 코드 생성
large_code = "# dummy line\n" * 50000  # 약 200k 토큰

try:
    response = client.chat.completions.create(
        model="gpt-5.3-codex",
        messages=[
            {
                "role": "user",
                "content": f"다음 코드에서 주석만 추출해줘:\n{large_code}"
            }
        ],
        max_tokens=100
    )
    print("200k 토큰 컨텍스트 테스트: 성공")
    print(f"사용된 토큰: {response.usage.prompt_tokens}")

except openai.BadRequestError as e:
    print(f"컨텍스트 초과: {e}")
```

### 9.3 openclaw와의 통합 테스트

```bash
# openclaw.json이 올바르게 설정되었는지 확인
claude --model gpt-5.3-codex "안녕하세요. 지금 어떤 모델이 실행 중인지 알려주세요."

# 모델이 코드 작업에 응답하는지 확인
claude "파이썬으로 간단한 HTTP 서버를 만들어줘"
```

---

## 체크리스트

- [ ] OpenAI 계정 생성 및 결제 정보 등록
- [ ] API 키 발급 및 `~/.config/openclaw/openai.env`에 안전하게 저장
- [ ] `chmod 600 ~/.config/openclaw/openai.env` 권한 설정
- [ ] `source ~/.config/openclaw/openai.env` 쉘 프로파일에 추가
- [ ] OpenAI 계정 Tier 확인 (Tier 1 이상 권장)
- [ ] OpenAI 대시보드에서 월간 지출 한도 설정
- [ ] `curl` 테스트로 API 연결 확인
- [ ] openclaw.json에 `gpt-5.3-codex` 모델 설정
- [ ] (선택) LiteLLM config.yaml에 OpenAI 모델 추가
- [ ] 실제 코드 작업으로 응답 품질 확인
- [ ] Rate Limit 도달 시 폴백 동작 확인
- [ ] 월별 비용 추이 모니터링 체계 구축
