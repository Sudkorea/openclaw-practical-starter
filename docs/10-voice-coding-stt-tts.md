# 10. 누워서 목소리로 코딩: STT/TTS 세팅 + 지연 줄이기

## 목표
- Discord 음성 입력 → STT → LLM 응답 → TTS 재생
- 중간에 에러 나도 서비스가 멈추지 않게

---

## 1) 운영 모드
- `lowcost`: local whisper + edge tts
- `hybrid`: local whisper + gcp tts
- `gcp-quality`: gcp stt + gcp tts
- `fallback-safe`: 강제 저비용

권장 시작:
- 기본은 `lowcost` 또는 `hybrid`
- 품질 검증 뒤 `gcp-quality`

---

## 2) 자주 터지는 문제와 해결
1. Whisper compute type 오류
- 증상: int8_float16 미지원
- 해결: CPU/CUDA별 fallback 전략 적용

2. GCP STT mono 에러
- 증상: WAV 2채널 입력으로 400
- 해결: stereo -> mono 다운믹스 + config에 channel=1 명시

3. streaming timeout
- 증상: Audio Timeout Error
- 해결: idle stop signal 강제 + dead worker 재생성

4. TTS가 URL/마크다운 그대로 읽음
- 해결: sanitize_tts_text로 code block/링크/괄호 정리

---

## 3) 지연(latency) 줄이는 우선순위
P0 (체감 큰 것)
- 침묵 기준(silence_sec) 튜닝
- 세그먼트 flush 주기 단축

P1
- STT 모드/요청 최적화
- LLM 응답 길이 제한

P2
- TTS 포맷/보이스/버퍼링 최적화

---

## 4) 필수 지표
- E2E latency p50/p95 (발화 종료→재생 시작)
- STT 에러율
- 세션당 timeout 횟수

지표 없으면 개선이 아니라 느낌 싸움이 됨.
