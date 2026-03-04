# Deals Agent 예제

개인화된 핫딜 알림 파이프라인 (선호도 학습 기능 포함)

## 이 Agent가 하는 일

deals-agent는 핫딜 사냥 워크플로우를 자동화합니다:

1. **딜 커뮤니티 크롤링** — 핫딜 사이트를 주기적으로 크롤링
   (arca.live/b/hotdeal부터 시작)하여 딜 메타데이터 추출
2. **Discord 알림 발송** — 새 딜을 전용 채널에 포스팅
   (가격, 카테고리, 구매처, 인기도 포함)
3. **사용자 평점 수집** — 각 딜 메시지에 1️⃣~5️⃣ 이모지 반응 추가,
   사용자가 클릭하여 관심도 평가
4. **선호도 학습** — 평점에 EMA(지수이동평균) 적용하여
   개인화 프로필 구축 (카테고리, 가격대, 구매처별 가중치)
5. **점수 계산 및 필터링** — 평점이 쌓이면 인기도 기반 순위(cold start)에서
   선호도 가중 스코어링으로 전환
6. **소스 사이트 품질 추적** — 지속적으로 높은 평점 받는 딜 소스를
   모니터링하고 새로운 크롤 타겟 제안

## 아키텍처 개요

```
cron (6h interval)
    |
    v
crawl_hotdeal.py  -->  SQLite (deals, ratings, preferences, source_sites)
    |
    v
scorer.py  -->  ranked deals
    |
    v
Discord #deals channel  <--  user emoji reactions (1~5)
    |
    v
collect_ratings.py (3h interval)  -->  preference update (EMA)
```

## 파일 구조

```
deals-agent/
    README.md                    <- this file
    AGENTS.md                    <- behavioral rules
    IDENTITY.md                  <- agent persona
    SOUL.md                      <- personality / tone
    TOOLS.md                     <- available tools / paths
    USER.md                      <- user preference context (auto-updated)
    scripts/
        init_db.py               <- SQLite schema initialization
        crawl_hotdeal.py         <- web crawler + deal parser
        collect_ratings.py       <- Discord reaction collector + EMA learner
        scorer.py                <- 3-phase scoring engine (cold/warm/mature)
    data/
        deals.db                 <- SQLite database
    state/
        crawl_state.json         <- last crawl timestamp
        rating_state.json        <- last processed message ID
```

## 빠른 시작

1. 이 폴더를 agent workspace로 복사:
   ```
   cp -r examples/deals-agent/ ~/.openclaw/workspace-deals-agent/
   ```

2. 데이터베이스 초기화:
   ```
   python3 scripts/init_db.py
   ```

3. `openclaw.json`에 agent 등록:
   ```json
   {
     "id": "deals-agent",
     "name": "Deals Agent",
     "workspace": "/home/you/.openclaw/workspace-deals-agent",
     "model": "openai-codex/gpt-5.3-codex",
     "identity": { "name": "Your Name", "emoji": "🦀" },
     "tools": {
       "allow": [
         "group:web", "group:fs", "group:runtime",
         "group:memory", "group:messaging", "browser", "session_status"
       ]
     }
   }
   ```

4. Discord 봇 계정과 채널 설정 후 바인딩 추가:
   ```json
   {
     "agentId": "deals-agent",
     "match": {
       "channel": "discord",
       "accountId": "your-bot-account",
       "guildId": "your-guild-id"
     }
   }
   ```

5. Cron job 추가 (아래 Cron 설정 섹션 참고)

6. 크롤러 테스트:
   ```
   python3 scripts/crawl_hotdeal.py
   ```
   `"send": true`와 딜 목록이 포함된 JSON이 출력되어야 함

## 스코어링 모델

The scoring engine uses a 3-phase maturity model:

| Phase   | Ratings | Strategy |
|---------|---------|----------|
| Cold    | 0-19    | Popularity only (upvotes + comments, log-scaled) |
| Warm    | 20-99   | 60% popularity + 40% preference weights |
| Mature  | 100+    | 30% popularity + 70% preference weights |

Preference weights are learned via EMA (alpha=0.15):
```
new_weight = 0.15 * normalized_rating + 0.85 * old_weight
```

Features tracked:
- `category:전자제품`, `category:식품`, etc.
- `site:쿠팡`, `site:네이버`, etc.
- `price_range:under_10k`, `price_range:10k_50k`, etc.

## Cron 설정

Two cron jobs handle the pipeline:

**Job 1: Crawl + Notify (every 6 hours)**
```json
{
  "schedule": { "kind": "cron", "expr": "0 2,8,14,20 * * *", "tz": "Asia/Seoul" },
  "payload": {
    "kind": "agentTurn",
    "message": "Run crawl_hotdeal.py, parse output, send new deals to Discord with emoji reactions",
    "timeoutSeconds": 300
  }
}
```

**Job 2: Collect Ratings (every 3 hours)**
```json
{
  "schedule": { "kind": "cron", "expr": "30 1,4,7,10,13,16,19,22 * * *", "tz": "Asia/Seoul" },
  "payload": {
    "kind": "agentTurn",
    "message": "Run collect_ratings.py, update preference weights",
    "timeoutSeconds": 120
  }
}
```

## Discord 메시지 형식

Individual deal:
```
🦀 **[전자제품] RTX 5070 Ti 최저가**
💰 890,000원
🏪 쿠팡 | 👍 42 | 💬 15
🔗 https://arca.live/b/hotdeal/12345

1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣
```

Batch summary (6+ deals):
- Top 5 posted individually with emoji reactions
- Remaining deals in a compact summary message

## 웹 스크래핑: 법적 고려사항 (한국)

> **면책조항**: 이는 법률 자문이 아닙니다. 필요시 변호사와 상담하세요.

Web scraping in Korea involves three main legal frameworks:

### robots.txt
arca.live's robots.txt allows `/b/hotdeal` (only `/u/` and edit/delete paths
are disallowed). However, robots.txt compliance alone does not guarantee legality.

### Site Operator & Jurisdiction
arca.live is operated by **Umanle S.R.L.**, a Paraguay-registered entity, with
servers hosted in Australia. The site was established partly to operate outside
Korean internet regulatory jurisdiction. This makes enforcement of Korean ToS
provisions more complex, but **Korean law (정보통신망법) still applies to
Korean users accessing the service from Korea**.

### Key Laws

| Law | Risk for Personal Use | Notes |
|-----|----------------------|-------|
| 정보통신망법 48조 (네트워크 침입) | Low-Medium | 대법원 2021도1533 판결: 기술적 보호조치 미비 시 침입 불인정. 단, CAPTCHA/rate limit 우회 시 리스크 상승 |
| 저작권법 93조 (DB 제작자 권리) | Very Low | 제목/링크만 수집, 전체 DB의 상당부분 아님. 30조 사적이용 면책 |
| 부정경쟁방지법 2조(카) | Negligible | "자신의 영업을 위하여" 요건 — 개인 비상업 용도는 해당 없음 |

### Landmark Case: 대법원 2021도1533 (2022.05.12)
여기어때가 야놀자 데이터를 크롤링한 사건. **3개 혐의 모두 무죄**.
핵심: "접근권한" 판단은 서비스 제공자의 주관적 의사가 아니라, 기술적
보호조치 등 객관적/외형적 사정 기준.

### Recommended Mitigations
1. **기술적 보호조치 우회 금지** — CAPTCHA 자동 풀이, rate limit 우회 절대 금지
2. **Rate limiting** — 요청 간 충분한 간격 유지 (최소 5초)
3. **최소 수집** — 제목/가격/링크만 수집, 본문/이미지/댓글 전체 미수집
4. **비재배포** — 수집 데이터 외부 공개/재배포 금지
5. **중단 요청 즉시 이행** — cease-and-desist 시 즉시 중단
6. **비로그인 공개 데이터만** — 로그인 필요 콘텐츠는 수집하지 않음

### ToS Note
arca.live 이용약관은 "크롤링/스크래핑 등 비정상적 행위로 사이트에 영향을
줄 경우" 이용 제한을 명시. 조건부 제한("영향을 줄 경우")이므로 저빈도/
비파괴적 접근은 직접적 위반으로 보기 어려움.

### Risk Summary
**개인 비상업 용도, 저빈도(6시간 1회), 공개 페이지 제목/링크만 수집**하는
현재 방식의 법적 리스크는 **낮음**. 가장 큰 실질적 리스크는 법적 문제보다
**IP 차단/계정 제한** 등 기술적 조치.

## 소스 사이트 자동 확장

The system tracks all source sites (쿠팡, 네이버, 11번가, etc.) mentioned in deals:

```sql
SELECT site, total_deals, avg_rating, high_rated_count, crawl_candidate
FROM source_sites
WHERE crawl_candidate = 1;
```

A site becomes a crawl expansion candidate when:
- `avg_rating >= 3.5` AND `high_rated_count >= 5`

The daily report surfaces these candidates for user approval before adding them
as new crawl targets.

## 비용 고려사항

- **LLM tokens**: Cron job prompts are short (~200 tokens). The agent itself does
  minimal reasoning; most work is in Python scripts.
- **Storage**: SQLite DB grows slowly (~1KB per deal). 100 deals/day ≈ 36KB/year.
- **API calls**: Discord API calls are free. Web fetches are one page per 6 hours.
- **Compute**: Python scripts run in <5 seconds each.

## 이 예제 확장하기

- **Add more sources**: Write a new parser function in `crawl_hotdeal.py` for
  each source site. Keep the same deal schema.
- **Improve scoring**: Replace the weighted-sum model with a simple logistic
  regression once you have 200+ ratings.
- **Add daily summary**: Create a cron job at 23:30 KST that reads the day's deals,
  computes stats, and posts a summary to Discord.
- **Integrate with Airlock**: Record daily crawl stats to the Airlock for
  nightly orchestrator classification.

See `docs/09-discord-channel-bot-setup.md` for Discord integration details and
`docs/06-multi-agent-architecture.md` for agent design philosophy.
