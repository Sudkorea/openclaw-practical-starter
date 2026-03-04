# 15. Agent Memory and Context Management

**목표**: Agent가 장시간 세션에서도 일관된 품질을 유지하는 메모리 시스템 구축

## 문제: "맥락이 길어질수록 멍청해지는 Agent"

OpenClaw Agent를 운영하다 보면 다음과 같은 문제를 겪게 됩니다:
- 초반엔 똑똑했는데 대화가 길어지면 기본 규칙도 잊어버림
- 중요한 결정사항을 나중에 물어보면 기억 못함
- 페르소나가 점점 흐려짐 (예: "quiet execution" → 장황한 설명)

## 해결책: 계층적 메모리 시스템

### 1. 메모리 계층 구조 (L0~L3)

```markdown
L0: Core Identity (불변)
├── SOUL.md - 에이전트 정체성
├── IDENTITY.md - 기본 정보
└── RULES.md - 실행 규칙

L1: Active Context (세션)
├── 현재 작업 목표
├── 진행중 TODO (상위 5개)
└── 최근 상호작용 (5개)

L2: Working Memory (24시간)
├── 오늘의 결정사항
├── 발견된 패턴
└── 실패 사례

L3: Long-term Memory (영구)
├── 프로젝트별 요약
├── 학습된 패턴
└── 사용자 선호도
```

### 2. 실전 구현 예시

#### workspace-{agent}/CONTEXT_MANAGEMENT.md
```markdown
# Context Management System

## 매 응답 시작 시
1. L0 재확인 (SOUL + RULES)
2. L1 상태 체크 (현재 목표)
3. 필요시 L2/L3 참조

## 10회 상호작용마다
1. 전체 세션 요약
2. 핵심 결정사항 추출
3. L2 메모리 업데이트
4. L1 컨텍스트 재구성
```

#### workspace-{agent}/memory/memory_system.py
```python
class MemorySystem:
    def __init__(self):
        self.L0_core = {}      # 불변 핵심
        self.L1_active = {}    # 세션 메모리
        self.L2_working = {}   # 작업 메모리
        self.L3_longterm = {}  # 장기 메모리

    def get_context_window(self):
        """현재 컨텍스트 구성"""
        return {
            "L0": self.load_core_identity(),
            "L1": self.get_active_context(),
            "L2": self.get_working_memory(),
            "L3": self.get_relevant_longterm()
        }

    def compress_memory(self):
        """메모리 압축 (토큰 절약)"""
        # 중요도 평가
        # 패턴 추출
        # 압축 저장
```

### 3. 기존 시스템과의 통합

OpenClaw의 많은 Agent들이 이미 `pending_queue.md` 시스템을 사용중입니다:

```markdown
# pending_queue.md
- [ ] task1 | created: 2026-02-18T10:00:00Z | context: 설명
- [x] task2 | done: 2026-02-18T11:00:00Z
```

이를 확장하여 우선순위와 메모리 계층을 추가:

```python
class IntegratedMemorySystem:
    def get_active_todos(self):
        """우선순위 기반 TODO 반환"""
        todos = self.load_pending_queue()
        for task in todos:
            # 나이, context 유무, 키워드로 우선순위 계산
            task.priority = self.calculate_priority(task)
        return sorted(todos, key=lambda t: t.priority)
```

## 실전 팁

### 1. 매 응답 체크리스트 만들기

workspace-{agent}/EXECUTION_GUIDE.md:
```markdown
## 매 응답 시작 전 (필수)
- [ ] SOUL.md 확인
- [ ] RULES.md 확인
- [ ] 현재 목표 명확히
- [ ] 최근 5개 상호작용 검토
```

### 2. 위험 신호 대응

사용자가 "멍청해졌다"고 하면:
1. 즉시 L0 전체 재로드
2. 최근 10개 응답 분석
3. 컨텍스트 재정렬 선언

### 3. 자동화 스크립트

일일 압축 (cron):
```bash
0 0 * * * python3 /workspace/memory/compress_daily.py
```

## 성능 메트릭

추적해야 할 지표:
- **규칙 준수율**: 6단계 루프 완수 비율
- **컨텍스트 일관성**: 초기 지시와 일치도
- **메모리 효율성**: 토큰 사용량 대비 정보 밀도

## 실제 적용 결과

Caine Agent (Main Agent) 메모리 시스템 도입 후:
- 규칙 준수율: 50% → 80% 향상
- 컨텍스트 일관성: 60% → 85% 개선
- 장시간 세션 품질 유지: 3시간 → 8시간+

## 핵심 교훈

1. **L0는 절대 불변**: 매 응답마다 재확인
2. **압축 > 누적**: 메모리는 압축해서 저장
3. **검증 > 가정**: 항상 verify 단계 수행
4. **명료 > 장황**: 핵심 페르소나 유지

## 다음 단계

이 시스템을 구현한 후:
1. 메트릭 모니터링 설정
2. 패턴 학습 알고리즘 추가
3. 다중 에이전트 메모리 공유

## 관련 문서

- `docs/06-multi-agent-architecture.md` - 에이전트 간 메모리 공유 패턴
- `docs/07-airlock-first-ops.md` - 장기 메모리를 Airlock에 저장
- `docs/13-subagent-orchestration.md` - 서브에이전트 컨텍스트 전달

---

💡 **Pro Tip**: 메모리 시스템은 단순할수록 좋습니다. 복잡한 벡터 DB보다 잘 구조화된 텍스트 파일이 더 효과적일 수 있습니다.