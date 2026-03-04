# 01. GCP VM 비용/환경 세팅 완전 가이드

## 왜 GCP인가

### 무료 크레딧과 예측 가능한 비용

GCP(Google Cloud Platform)를 선택하는 가장 큰 이유는 신규 가입자에게 제공되는 **$300 무료 크레딧(90일)**이다. AI 에이전트 개발 환경을 본격적으로 구축하기 전에 충분히 실험할 수 있는 금액이다.

무료 크레딧 외에도 GCP가 유리한 이유:

- **지속 사용 할인(Sustained Use Discount)**: 별도 예약 없이도 한 달 기준 사용 시간이 25% 이상이면 자동으로 최대 30% 할인이 적용된다.
- **E2 시리즈의 가성비**: E2 머신 타입은 N2 대비 저렴하면서도 개발 워크로드에 충분한 성능을 제공한다.
- **세밀한 청구 알림**: 예산 임계값에 따라 이메일/Pub/Sub 알림을 설정할 수 있어 요금 폭탄을 방지할 수 있다.
- **Vertex AI와의 통합**: OpenClaw가 활용하는 Gemini API를 포함한 Vertex AI 서비스와 같은 프로젝트 내에서 통합 관리가 된다.

---

## VM 타입 선택: e2-highmem-2가 정답인 이유

### 주의: e2-standard-2는 16GB RAM이 아니다

흔한 실수 중 하나가 `e2-standard-2`를 선택하고 16GB RAM을 기대하는 것이다. **e2-standard-2는 8GB RAM**이다. OpenClaw 에이전트를 여러 개 동시에 실행하거나, LiteLLM 프록시와 함께 Claude Code를 돌리면 금방 메모리 부족을 겪는다.

| 머신 타입 | vCPU | RAM | 월 예상 비용(서울 기준) |
|---|---|---|---|
| e2-standard-2 | 2 | 8 GB | ~$49 |
| **e2-highmem-2** | **2** | **16 GB** | **~$81** |
| e2-standard-4 | 4 | 16 GB | ~$98 |
| e2-highmem-4 | 4 | 32 GB | ~$162 |

**OpenClaw 개발 환경 권장: `e2-highmem-2`**

- 2 vCPU는 Claude Code 에이전트 1-2개 동시 실행에 충분하다.
- 16 GB RAM은 LiteLLM 프록시 + Claude Code + 로컬 모델 서빙 없이 운영 시 여유 있게 사용 가능하다.
- e2-standard-4(4 vCPU, 16 GB)보다 약 17% 저렴하다.

비용이 제일 중요하다면 `e2-highmem-2`, 동시에 여러 에이전트를 돌리고 싶다면 `e2-highmem-4`를 고려한다.

---

## 단계별 VM 생성 가이드

### 1단계: GCP 프로젝트 생성

```bash
# gcloud CLI가 설치되어 있다면 터미널에서 바로 실행 가능
gcloud projects create openclaw-dev-001 --name="OpenClaw Dev"
gcloud config set project openclaw-dev-001
```

또는 GCP 콘솔(console.cloud.google.com)에서:

1. 상단 프로젝트 드롭다운 클릭
2. "새 프로젝트" 선택
3. 프로젝트 이름: `openclaw-dev` (소문자, 하이픈만 허용)
4. "만들기" 클릭

예상 화면: 프로젝트 생성 후 대시보드로 이동되며 상단에 새 프로젝트 이름이 표시된다.

### 2단계: Compute Engine API 활성화

```bash
gcloud services enable compute.googleapis.com
```

콘솔에서는: "API 및 서비스" > "라이브러리" > "Compute Engine API" 검색 > "사용" 클릭

### 3단계: VM 인스턴스 생성

**CLI 방법 (권장):**

```bash
gcloud compute instances create openclaw-vm \
  --project=openclaw-dev-001 \
  --zone=asia-northeast3-a \
  --machine-type=e2-highmem-2 \
  --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --service-account=$(gcloud iam service-accounts list --format='value(email)' | head -1) \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=openclaw-server \
  --create-disk=auto-delete=yes,boot=yes,device-name=openclaw-vm,image=projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20250112,mode=rw,size=100,type=pd-balanced \
  --no-shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring \
  --labels=env=dev,project=openclaw \
  --reservation-affinity=any
```

**예상 출력:**
```
Created [https://www.googleapis.com/compute/v1/projects/openclaw-dev-001/zones/asia-northeast3-a/instances/openclaw-vm].
NAME          ZONE               MACHINE_TYPE   PREEMPTIBLE  INTERNAL_IP  EXTERNAL_IP    STATUS
openclaw-vm   asia-northeast3-a  e2-highmem-2               10.178.0.2   34.64.XXX.XXX  RUNNING
```

**콘솔 방법:**

1. Compute Engine > VM 인스턴스 > "인스턴스 만들기"
2. 이름: `openclaw-vm`
3. 리전: `asia-northeast3 (서울)`, 영역: `asia-northeast3-a`
4. 머신 구성:
   - 시리즈: E2
   - 머신 유형: **e2-highmem-2** (2vCPU, 16GB 메모리)
   - ※ 목록에서 "highmem" 필터로 검색하면 빠르게 찾을 수 있다
5. 부팅 디스크: "변경" 클릭
   - 운영체제: Ubuntu
   - 버전: Ubuntu 22.04 LTS
   - 부팅 디스크 유형: 균형 있는 영구 디스크
   - 크기: 100 GB
6. "만들기" 클릭

### 4단계: 리전 선택 팁

| 리전 | 지연 시간(한국 기준) | 특이사항 |
|---|---|---|
| asia-northeast3 (서울) | 5-20ms | 국내 최저 지연, 일부 서비스 미지원 |
| asia-northeast1 (도쿄) | 30-50ms | 안정적, 서비스 범위 넓음 |
| us-central1 (아이오와) | 180-200ms | 최저 비용, Vertex AI 모델 가장 많음 |

Vertex AI의 최신 Gemini 모델을 사용하려면 `us-central1`이 가장 빠르게 지원된다. 그러나 개발 편의성(저지연)을 위해 `asia-northeast3`을 우선 추천한다.

---

## 디스크 설정

### 100GB를 권장하는 이유

```
Claude Code 캐시 및 체크포인트:  ~10 GB
Python 가상환경 여러 개:          ~5 GB
Docker 이미지 (선택사항):         ~20 GB
프로젝트 코드베이스들:            ~10 GB
로그 및 에어락 파일:               ~5 GB
여유 공간:                        ~50 GB
```

50GB로 시작하면 몇 달 후 디스크 부족을 경험하게 된다. 처음부터 100GB로 설정하는 것이 낫다. pd-balanced(균형 있는 영구 디스크) 100GB의 월 비용은 약 **$10**이다.

### 디스크 확인 및 관리

VM 생성 후 디스크 상태 확인:

```bash
df -h
# 예상 출력:
# Filesystem      Size  Used Avail Use% Mounted on
# /dev/sda1        98G  5.5G   88G   6% /
```

나중에 디스크를 늘려야 할 경우(VM 중지 없이 가능):

```bash
# GCP 콘솔에서 디스크 크기를 200GB로 변경 후 VM 내에서 실행
sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1
```

---

## 방화벽 규칙 설정

### 최소한으로 열어야 하는 포트

보안 원칙: 필요한 포트만 열고, Tailscale을 통해 접근하는 것을 기본으로 한다.

```bash
# Tailscale을 사용한다면 SSH 포트는 내부 IP로만 제한 가능
# 초기 셋업을 위해 일단 SSH(22) 허용
gcloud compute firewall-rules create allow-ssh \
  --project=openclaw-dev-001 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=openclaw-server
```

Tailscale 설치 완료 후에는 SSH 방화벽 규칙을 Tailscale CIDR로 제한하거나 아예 비활성화할 수 있다.

```bash
# Tailscale 설치 완료 후 - SSH를 내 Tailscale IP 대역으로만 허용
gcloud compute firewall-rules update allow-ssh \
  --source-ranges=100.64.0.0/10

# 또는 GCP 외부 SSH를 완전히 비활성화하고 Tailscale로만 접속
gcloud compute firewall-rules delete allow-ssh
```

### 콘솔에서 방화벽 설정

1. VPC 네트워크 > 방화벽 > "방화벽 규칙 만들기"
2. 이름: `allow-ssh-openclaw`
3. 방향: 수신
4. 일치 시 작업: 허용
5. 대상: 지정된 대상 태그 > `openclaw-server`
6. 소스 IPv4 범위: `0.0.0.0/0` (초기), 이후 Tailscale 대역으로 변경
7. 프로토콜 및 포트: TCP 22
8. "만들기" 클릭

---

## SSH 키 설정

### 방법 1: gcloud CLI로 자동 키 관리 (권장)

```bash
# 로컬 머신에서 실행
gcloud compute ssh openclaw-vm --zone=asia-northeast3-a
# 처음 실행 시 자동으로 키 페어 생성 및 등록
# ~/.ssh/google_compute_engine 에 저장됨
```

### 방법 2: 수동 SSH 키 생성 및 등록

```bash
# 로컬 머신에서 SSH 키 생성
ssh-keygen -t ed25519 -C "openclaw-dev" -f ~/.ssh/openclaw_gcp

# 공개키 확인
cat ~/.ssh/openclaw_gcp.pub
# 출력 예시: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... openclaw-dev
```

GCP 콘솔에서 공개키 등록:
1. Compute Engine > VM 인스턴스 > `openclaw-vm` 클릭
2. "수정" 버튼
3. "SSH 키" 섹션 > "항목 추가"
4. 공개키 내용 붙여넣기
5. "저장"

```bash
# 이후 SSH 접속
ssh -i ~/.ssh/openclaw_gcp [USERNAME]@[EXTERNAL_IP]
```

### SSH config 파일 설정 (편의성 향상)

```bash
# ~/.ssh/config 에 추가
Host openclaw-gcp
    HostName 34.64.XXX.XXX   # VM 외부 IP
    User [your_username]
    IdentityFile ~/.ssh/openclaw_gcp
    ServerAliveInterval 60
    ServerAliveCountMax 3

# 이후 단축 명령으로 접속 가능
ssh openclaw-gcp
```

---

## 비용 상세 분석

### 월 비용 추정 (서울 리전 기준, 2025년 2월 기준)

| 항목 | 단가 | 월 사용 | 월 비용 |
|---|---|---|---|
| e2-highmem-2 (720시간/월) | $0.112/시간 | 720시간 | ~$81 |
| pd-balanced 100GB | $0.100/GB/월 | 100 GB | ~$10 |
| 외부 IP 주소 (사용 중) | $0.004/시간 | 720시간 | ~$3 |
| 네트워크 송신 (한국 내) | $0.085/GB | ~10 GB | ~$1 |
| **합계** | | | **~$95/월** |

지속 사용 할인(25% 이상 사용 시) 적용 후 실제 VM 비용은 약 **$57-70** 수준까지 내려간다.

### 야간/주말 VM 중지 시 절약 효과

하루 8시간만 사용(평일 기준):

```
하루 8시간 × 22일(평일) = 176시간/월
e2-highmem-2: 176 × $0.112 = ~$20
디스크(항상 과금): $10
외부 IP(중지 시 과금 없음): $0
합계: ~$30/월 (상시 운영 대비 68% 절약)
```

VM을 중지해도 디스크 비용은 계속 발생한다. 완전히 요금을 0으로 만들려면 인스턴스를 삭제해야 하지만, 그러면 재설정 번거로움이 있다.

---

## 비용 최적화 팁

### 1. VM 자동 중지 스크립트

개발이 끝난 후 VM을 켜놓는 것을 방지하기 위해 자동 종료 스크립트를 설정한다.

```bash
# VM 내에서 crontab 설정 (매일 자정 자동 종료)
crontab -e

# 다음 내용 추가:
0 0 * * * /sbin/shutdown -h now >> /var/log/auto-shutdown.log 2>&1
```

또는 GCP Cloud Scheduler를 사용해 외부에서 VM을 제어할 수 있다:

```bash
# Cloud Scheduler 잡 생성 (매일 밤 11시에 VM 중지)
gcloud scheduler jobs create http stop-openclaw-vm \
  --location=asia-northeast3 \
  --schedule="0 23 * * *" \
  --uri="https://compute.googleapis.com/compute/v1/projects/openclaw-dev-001/zones/asia-northeast3-a/instances/openclaw-vm/stop" \
  --message-body="{}" \
  --oauth-service-account-email=[SERVICE_ACCOUNT_EMAIL] \
  --time-zone="Asia/Seoul"
```

### 2. 스팟(Spot) VM 사용 고려

중단을 허용할 수 있는 작업이라면 스팟 VM을 사용하면 최대 **60-91% 저렴**하다.

```bash
# 스팟 VM 생성 (e2-highmem-2 스팟 가격: ~$0.025/시간)
gcloud compute instances create openclaw-vm-spot \
  --zone=asia-northeast3-a \
  --machine-type=e2-highmem-2 \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --create-disk=auto-delete=yes,boot=yes,size=100,type=pd-balanced,image=projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20250112
```

단, 스팟 VM은 GCP가 언제든 회수할 수 있으므로 중요한 작업 중에 갑자기 종료될 수 있다. 에이전트 배치 작업에는 적합하지만 인터랙티브 개발에는 주의가 필요하다.

### 3. 디스크 스냅샷 정책으로 데이터 보호

```bash
# 매일 오전 3시 스냅샷 생성 정책 (최근 7일 보관)
gcloud compute resource-policies create snapshot-schedule daily-backup \
  --project=openclaw-dev-001 \
  --region=asia-northeast3 \
  --max-retention-days=7 \
  --on-source-disk-delete=keep-auto-snapshots \
  --daily-schedule \
  --start-time=03:00

# VM 디스크에 정책 연결
gcloud compute disks add-resource-policies openclaw-vm \
  --resource-policies=daily-backup \
  --zone=asia-northeast3-a
```

스냅샷 비용: 약 $0.026/GB/월. 100GB 디스크 스냅샷 7일치 = 약 **$18/월** 추가.

---

## 모니터링 및 알림 설정

### 예산 알림 설정 (필수)

GCP 콘솔에서:
1. "결제" > "예산 및 알림" > "예산 만들기"
2. 이름: `openclaw-monthly-budget`
3. 범위: 특정 프로젝트 선택 > `openclaw-dev`
4. 금액: $100/월 (첫 달은 무료 크레딧 고려)
5. 알림 임계값:
   - 50% ($50) - 이메일 알림
   - 90% ($90) - 이메일 알림
   - 100% ($100) - 이메일 + 프로젝트 중지 고려

```bash
# gcloud CLI로 예산 알림 설정
gcloud billing budgets create \
  --billing-account=[BILLING_ACCOUNT_ID] \
  --display-name="OpenClaw Monthly Budget" \
  --budget-amount=100USD \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

### VM CPU/메모리 모니터링

```bash
# VM 내에서 실시간 모니터링
htop

# 또는 간단한 상태 확인
free -h
# 출력 예시:
#               total        used        free      shared  buff/cache   available
# Mem:           15Gi       3.2Gi       8.1Gi       128Mi       4.1Gi        12Gi
# Swap:           0Bi         0Bi         0Bi

df -h /
# 출력 예시:
# Filesystem      Size  Used Avail Use% Mounted on
# /dev/sda1        98G   18G   75G  20% /
```

### Cloud Monitoring 알림 정책 (CLI)

```bash
# 메모리 사용률 80% 초과 시 알림
gcloud alpha monitoring policies create \
  --notification-channels=[CHANNEL_ID] \
  --display-name="High Memory Usage" \
  --condition-display-name="Memory usage > 80%" \
  --condition-filter='resource.type="gce_instance" AND metric.type="agent.googleapis.com/memory/percent_used" AND metric.labels.state="used"' \
  --condition-threshold-value=80 \
  --condition-threshold-comparison=COMPARISON_GT \
  --condition-duration=300s
```

### 간단한 일일 비용 확인 스크립트

```bash
# 로컬 머신에서 실행 (gcloud 설치 필요)
#!/bin/bash
echo "=== GCP 비용 현황 ==="
gcloud billing accounts list
# 이후 GCP 콘솔의 결제 > 비용 관리에서 상세 확인 권장
```

---

## 초기 VM 설정 체크리스트

VM 생성 직후 실행해야 할 명령어들:

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y git curl wget unzip htop tmux build-essential

# Python 3.11 설치 (Ubuntu 22.04 기본은 3.10)
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# pip 최신화
python3 -m pip install --upgrade pip

# Node.js 설치 (Claude Code 실행에 필요)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# 버전 확인
node --version   # v22.x.x 이상
npm --version    # 10.x 이상
python3 --version  # Python 3.11.x

# Claude Code 설치
npm install -g @anthropic-ai/claude-code

# 설치 확인
claude --version
```

예상 소요 시간: 약 5-10분

---

## 자주 발생하는 문제와 해결책

**문제 1: VM 생성 시 "Quota exceeded" 오류**
```
ERROR: (gcloud.compute.instances.create) Could not fetch resource:
- Quota 'CPUS' exceeded. Limit: 8.0 in region asia-northeast3.
```
해결: GCP 콘솔 > IAM 및 관리자 > 할당량 > CPU 할당량 증가 요청 (무료 계정은 제한됨)

**문제 2: SSH 접속 시 "Permission denied (publickey)"**
```
Permission denied (publickey).
```
해결:
```bash
# 키 파일 권한 확인
chmod 600 ~/.ssh/openclaw_gcp
chmod 700 ~/.ssh/
# 디버그 모드로 접속 시도
ssh -v -i ~/.ssh/openclaw_gcp [USER]@[IP]
```

**문제 3: VM 중지 후 외부 IP 변경**

VM을 중지했다가 다시 시작하면 외부 IP가 바뀐다. 이 문제를 방지하려면:
```bash
# 고정 외부 IP 예약 (월 ~$3 추가)
gcloud compute addresses create openclaw-static-ip \
  --region=asia-northeast3

# VM에 고정 IP 연결은 콘솔에서 VM 편집 > 네트워크 인터페이스에서 설정
```

또는 Tailscale을 설치하면 IP 변경과 무관하게 안정적으로 접속할 수 있다 (다음 문서 참고).
