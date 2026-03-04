# Agent Memory System Template

복사해서 workspace-{agent-name}/ 에 배치하세요.

## 필수 파일 구조

```
workspace-{agent-name}/
├── SOUL.md                    # L0: 에이전트 정체성
├── IDENTITY.md                 # L0: 기본 정보
├── COMMON_AGENT_RULES.md       # L0: 실행 규칙
├── CONTEXT_MANAGEMENT.md       # 컨텍스트 관리 전략
├── EXECUTION_GUIDE.md          # 실행 체크리스트
├── memory/
│   ├── pending_queue.md        # 작업 큐
│   ├── 2026-02-18.md           # 일일 메모리
│   ├── memory_system.py        # 메모리 관리 코드
│   └── compressed/             # 압축된 과거 메모리
└── scripts/
    └── pending_memo.py         # 큐 관리 스크립트

```

## SOUL.md 템플릿

```markdown
# SOUL.md - Who You Are

## Core Truths
**Be genuinely helpful, not performatively helpful.**
**Have opinions.** You're allowed to disagree.
**Be resourceful before asking.**
**Earn trust through competence.**

## Vibe
[에이전트별 페르소나 정의]

## Continuity
Each session, you wake up fresh. These files _are_ your memory.
```

## CONTEXT_MANAGEMENT.md 템플릿

```markdown
# Context Management System

## 컨텍스트 계층
- L0: Core Identity (SOUL, RULES) - 2K tokens
- L1: Active Context (현재 작업) - 10K tokens
- L2: Working Memory (24시간) - 20K tokens
- L3: Long-term Memory (검색) - 5K tokens

## 리프레시 전략
### 매 응답
1. L0 재확인
2. L1 상태 체크

### 10회 상호작용마다
1. 세션 요약
2. L2 업데이트

### 매일 자정
1. 메모리 압축
2. L3 업데이트
```

## EXECUTION_GUIDE.md 템플릿

```markdown
# Execution Guide

## 매 응답 체크리스트
- [ ] SOUL.md 확인
- [ ] RULES 6단계 확인
- [ ] 현재 목표 명확히
- [ ] 최근 상호작용 검토

## 응답 템플릿
\```
## 현재 상황
- 목표: [목표]
- 규칙: 6단계 적용

## 실행 계획
1. Plan: [계획]
2. Execute: [실행]

## 결과 보고
- ✅ 완료: [완료사항]
- ⚠️ 이슈: [문제점]
\```

## 위험 신호
"멍청해졌다" 피드백 → 즉시 L0 재로드
```

## memory_system.py 기본 구조

```python
#!/usr/bin/env python3
"""Agent Memory System"""

from pathlib import Path
from datetime import datetime
import json

class MemorySystem:
    def __init__(self, workspace_dir):
        self.workspace = Path(workspace_dir)
        self.memory_dir = self.workspace / "memory"

        # 메모리 계층
        self.L0_core = {}
        self.L1_active = {}
        self.L2_working = {}
        self.L3_longterm = {}

        self.load_all()

    def load_all(self):
        """모든 메모리 로드"""
        self._load_core_identity()
        self._load_pending_queue()
        self._load_daily_memories()

    def get_context_window(self):
        """현재 컨텍스트 구성"""
        return {
            "L0": self.L0_core,
            "L1": self.L1_active,
            "L2": self.L2_working,
            "L3": self.L3_longterm
        }

    def compress_daily(self):
        """일일 압축"""
        # 구현
        pass

if __name__ == "__main__":
    import sys
    memory = MemorySystem(".")

    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(memory.get_context_window(), indent=2))
        elif sys.argv[1] == "compress":
            memory.compress_daily()
```

## pending_queue.md 형식

```markdown
# Pending Queue

Format:
- [ ] <task> | created: <UTC ISO> | context: <short>
- [x] <task> | done: <UTC ISO>

- [ ] API 구조 변경 | created: 2026-02-18T10:00:00Z | context: REST to GraphQL
- [ ] 테스트 커버리지 개선 | created: 2026-02-18T11:00:00Z | context: 목표 80%
```

## 적용 단계

1. **파일 복사**
   ```bash
   cp -r templates/* workspace-{agent}/
   ```

2. **페르소나 정의**
   - SOUL.md에 에이전트 특성 작성
   - IDENTITY.md에 기본 정보 입력

3. **메모리 시스템 활성화**
   ```bash
   python3 memory/memory_system.py status
   ```

4. **에이전트에 지시**
   ```
   @Agent EXECUTION_GUIDE.md 읽고 매 응답시 체크리스트 확인
   ```

5. **일일 압축 설정**
   ```bash
   crontab -e
   0 0 * * * cd /workspace && python3 memory/memory_system.py compress
   ```

## 성능 메트릭

추적 권장 지표:
- 규칙 준수율 (목표: 80%)
- 컨텍스트 일관성 (목표: 85%)
- 토큰 효율성 (L0+L1 < 15K)
- 메모리 압축률 (목표: 30%)

## 트러블슈팅

### "맥락 잃어버림" 증상
1. `python3 memory/memory_system.py status` 실행
2. L0 core 확인
3. 에이전트에 "EXECUTION_GUIDE.md 재확인" 지시

### 토큰 초과
1. L2/L3 압축 실행
2. pending_queue 정리
3. 오래된 daily 파일 아카이브

### 메모리 충돌
1. 동시 접근 방지 (flock 사용)
2. 백업 유지 (daily snapshot)
3. 트랜잭션 로그 활용