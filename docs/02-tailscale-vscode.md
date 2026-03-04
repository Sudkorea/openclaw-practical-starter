# 02. Tailscale + VSCode Remote 완전 가이드

## 왜 Tailscale + VSCode Remote가 최선인가

### nano 편집의 한계

GCP VM에서 직접 `nano`나 `vim`으로 코드를 편집하는 방식은 단기적으로는 돌아가지만, 다음과 같은 문제가 빠르게 쌓인다:

- **자동완성 없음**: OpenClaw의 복잡한 에이전트 코드를 타이핑할 때 오타가 곱절로 늘어난다.
- **디버깅 불편**: 오류를 보고 코드로 바로 이동하는 흐름이 없다.
- **멀티 파일 편집 불가**: 여러 파일을 동시에 보면서 작업하기가 매우 힘들다.
- **Git 통합 없음**: 변경사항을 시각적으로 확인하고 stage/commit 하는 워크플로가 없다.
- **확장 생태계 없음**: Ruff, Pylance, GitLens 같은 도구들이 전혀 없다.

### Tailscale이 필요한 이유

단순히 SSH를 쓰면 되는 것 아닌가? 라고 생각할 수 있지만, Tailscale을 추가하면:

- **고정 IP 불필요**: VM을 재시작해도 Tailscale IP(100.x.x.x)는 변하지 않는다.
- **방화벽 구멍 최소화**: GCP의 SSH 포트(22)를 인터넷에 열지 않아도 된다.
- **어디서나 접속**: 카페 WiFi, 사무실 NAT 뒤, 모바일 핫스팟 어디서든 동일한 명령어로 접속된다.
- **WireGuard 기반 암호화**: 엔터프라이즈급 VPN 수준의 보안이 설정 5분 만에 완성된다.
- **팀 협업**: 팀원을 Tailscale 네트워크(tailnet)에 초대하면 VM 접근 권한을 간단히 공유할 수 있다.

### VSCode Remote-SSH의 장점

VSCode Remote-SSH는 **코드 실행 및 파일 시스템 접근은 전부 VM에서** 하면서, **UI만 로컬에서** 렌더링한다. 즉:

- 로컬에 Python, Node.js를 설치하지 않아도 된다.
- VM의 CPU/RAM 전부를 개발에 활용한다.
- 로컬 머신의 확장 프로그램 설정과 키바인딩을 그대로 VM에서 사용한다.
- 파일을 다운로드/업로드 없이 VM 파일을 직접 편집한다.

---

## 1단계: VM에 Tailscale 설치

먼저 GCP VM에 SSH로 접속한다 (기존 방법 사용):

```bash
gcloud compute ssh openclaw-vm --zone=asia-northeast3-a
# 또는
ssh -i ~/.ssh/openclaw_gcp [USER]@[EXTERNAL_IP]
```

VM 내에서 Tailscale 설치:

```bash
# Tailscale 공식 설치 스크립트 실행
curl -fsSL https://tailscale.com/install.sh | sh

# 예상 출력:
# Installing Tailscale for ubuntu focal, using method apt
# + sudo apt-get install -y tailscale
# Installation complete! Log in to start using Tailscale by running:
# tailscale up
```

Tailscale 시작 및 인증:

```bash
sudo tailscale up

# 예상 출력:
# To authenticate, visit:
# https://login.tailscale.com/a/1a2b3c4d5e6f
```

출력된 URL을 **로컬 브라우저**에서 열어 Tailscale 계정으로 로그인한다. Tailscale 계정이 없다면 이 시점에 무료로 가입한다.

인증 완료 후 VM에서 확인:

```bash
tailscale ip -4

# 예상 출력:
# 100.96.45.12   (이 IP가 이제 영구적인 VM 주소)

tailscale status

# 예상 출력:
# 100.96.45.12   openclaw-vm         [your-account]@ linux   -
```

### Tailscale 자동 시작 설정

VM 재시작 시 Tailscale이 자동으로 올라오도록:

```bash
sudo systemctl enable tailscaled
sudo systemctl status tailscaled

# 예상 출력:
# ● tailscaled.service - Tailscale node agent
#      Loaded: loaded (/lib/systemd/system/tailscaled.service; enabled; ...)
#      Active: active (running) since ...
```

### SSH 서버 확인

Tailscale 접속을 위해 VM에 SSH 서버가 실행 중이어야 한다:

```bash
sudo systemctl status ssh

# 실행 중이 아니라면:
sudo apt install -y openssh-server
sudo systemctl enable ssh
sudo systemctl start ssh
```

---

## 2단계: 로컬 머신에 Tailscale 설치

### macOS

```bash
# Homebrew 사용
brew install tailscale

# 또는 App Store에서 "Tailscale" 검색 후 설치
# App Store 버전 권장 (자동 업데이트)
```

설치 후 메뉴바에서 Tailscale 아이콘 클릭 > "Log in" > 계정 로그인

### Linux (로컬)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### Windows

[https://tailscale.com/download/windows](https://tailscale.com/download/windows) 에서 설치 파일 다운로드 후 실행.

설치 후 시스템 트레이의 Tailscale 아이콘으로 로그인.

### 연결 확인

로컬 머신에서:

```bash
tailscale status

# 예상 출력:
# 100.101.102.103  my-laptop           [your-account]@ macOS   -
# 100.96.45.12     openclaw-vm         [your-account]@ linux   -
```

이제 VM의 Tailscale IP로 SSH 접속 테스트:

```bash
ssh [USER]@100.96.45.12

# 예상 출력:
# Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 5.15.0-xxx-generic x86_64)
# ...
# [USER]@openclaw-vm:~$
```

---

## 3단계: VSCode Remote-SSH 설정

### VSCode 설치

[https://code.visualstudio.com](https://code.visualstudio.com) 에서 운영체제에 맞게 설치.

### Remote-SSH 확장 설치

VSCode를 열고:

1. 왼쪽 사이드바에서 Extensions 아이콘 클릭 (또는 `Ctrl+Shift+X`)
2. 검색창에 `Remote - SSH` 입력
3. Microsoft가 만든 "Remote - SSH" 확장 > "Install" 클릭

추가로 설치 권장:
- **Remote - SSH: Editing Configuration Files** (SSH config 파일 편집 편의성)

### SSH config 파일 설정

`~/.ssh/config` 파일에 다음을 추가한다:

```
Host openclaw-vm
    HostName 100.96.45.12       # Tailscale IP (tailscale ip -4 로 확인)
    User [your_username]        # VM의 사용자명 (보통 Gmail 계정 앞부분)
    IdentityFile ~/.ssh/google_compute_engine
    ServerAliveInterval 30
    ServerAliveCountMax 10
    TCPKeepAlive yes
```

`ServerAliveInterval 30`과 `ServerAliveCountMax 10` 설정은 연결이 끊기지 않도록 30초마다 keepalive 패킷을 보내는 설정이다. 장시간 작업 중 갑자기 연결이 끊기는 것을 방지한다.

VSCode에서 SSH config 파일 수정:
1. `F1` 또는 `Ctrl+Shift+P` 눌러 커맨드 팔레트 열기
2. `Remote-SSH: Open SSH Configuration File...` 입력 > Enter
3. `~/.ssh/config` 선택

### VM에 연결

1. `F1` > `Remote-SSH: Connect to Host...`
2. `openclaw-vm` 선택
3. 새 VSCode 창이 열리고 "SSH: openclaw-vm" 표시 확인
4. 좌하단에 `><` 모양 파란색 아이콘에 `SSH: openclaw-vm` 표시가 나타나면 연결 성공

처음 연결 시 VSCode Server가 VM에 자동으로 설치된다 (약 1-2분 소요):

```
[2025-02-18 10:30:01.234] > Waiting for server log...
[2025-02-18 10:30:03.891] > Downloading VS Code Server...
[2025-02-18 10:30:08.442] > Starting server...
[2025-02-18 10:30:09.110] > Server started
```

---

## 4단계: OpenClaw 개발 환경 구성

### 폴더 열기

VSCode Remote 연결 후:
1. `File` > `Open Folder...`
2. VM의 프로젝트 경로 입력: `/home/[USER]/openclaw` 또는 해당 경로
3. "OK" 클릭

### VM 측 필수 확장 프로그램 설치

Remote 연결 상태에서 Extensions 탭을 열면 "LOCAL - INSTALLED"와 "SSH: OPENCLAW-VM - INSTALLED" 두 섹션이 나뉜다. VM 측에 설치할 확장들:

```
# 필수
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)

# 강력 권장
- GitLens (eamodio.gitlens)
- GitHub Copilot (선택, 유료)
- YAML (redhat.vscode-yaml)
- Even Better TOML (tamasfe.even-better-toml)
- Thunder Client (rangav.vscode-thunder-client) — API 테스트용
```

커맨드 팔레트로 일괄 설치:

```bash
# VM SSH 세션에서 code CLI 사용 가능 (VSCode Server 설치 후)
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
code --install-extension eamodio.gitlens
```

### Python 인터프리터 설정

1. `Ctrl+Shift+P` > `Python: Select Interpreter`
2. VM의 가상환경 경로 선택: `/home/[USER]/openclaw/.venv/bin/python`
   - 또는 수동 입력: `Enter interpreter path...`

가상환경이 없다면 먼저 생성:

```bash
# VM 내에서
cd ~/openclaw
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### VSCode settings.json 설정 (프로젝트별)

프로젝트 루트에 `.vscode/settings.json` 생성:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    },
    "python.analysis.typeCheckingMode": "basic",
    "files.watcherExclude": {
        "**/.git/objects/**": true,
        "**/.venv/**": true,
        "**/node_modules/**": true,
        "**/airlock/**": true
    },
    "search.exclude": {
        "**/.venv": true,
        "**/airlock": true
    }
}
```

`files.watcherExclude`에 `.venv`와 `airlock` 디렉토리를 추가하면 불필요한 파일 감시로 인한 성능 저하를 방지할 수 있다.

### 터미널에서 Claude Code 실행

VSCode의 통합 터미널(`` Ctrl+` ``)을 열면 VM에서 바로 명령어를 실행할 수 있다:

```bash
# 가상환경 활성화
source .venv/bin/activate

# Claude Code 실행
claude

# 또는 특정 작업 지시
claude "현재 프로젝트의 에이전트 코드를 분석하고 버그를 찾아줘"
```

---

## 안정적인 연결을 위한 팁

### 1. tmux로 세션 유지

VSCode Remote가 끊겨도 VM에서 실행 중인 에이전트가 계속 돌아가도록:

```bash
# VM 내에서 tmux 설치
sudo apt install -y tmux

# tmux 세션 시작
tmux new -s openclaw

# 에이전트 실행
claude "장시간 작업..."

# 세션 분리 (작업은 계속 실행됨)
# Ctrl+B, 그 다음 D 키

# 나중에 세션 재연결
tmux attach -t openclaw
```

### 2. SSH ControlMaster로 다중 연결 최적화

`~/.ssh/config`에 추가:

```
Host openclaw-vm
    HostName 100.96.45.12
    User [USER]
    IdentityFile ~/.ssh/google_compute_engine
    ServerAliveInterval 30
    ServerAliveCountMax 10
    TCPKeepAlive yes
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 600
```

`ControlMaster`는 첫 연결 후 소켓을 재사용하므로, 이후 SSH 명령들이 인증 없이 즉시 연결된다. `ControlPersist 600`은 마지막 연결 종료 후 600초(10분) 동안 마스터 연결을 유지한다.

### 3. Tailscale MagicDNS 활용

Tailscale의 MagicDNS 기능을 켜면 IP 대신 호스트명으로 접속할 수 있다:

1. [https://login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns) 접속
2. "MagicDNS" 토글 켜기

이후 `~/.ssh/config`에서:

```
Host openclaw-vm
    HostName openclaw-vm        # IP 대신 호스트명 사용
    User [USER]
    ...
```

```bash
# 접속 테스트
ping openclaw-vm
ssh openclaw-vm
```

### 4. VSCode 재연결 자동화

VSCode가 연결을 잃었을 때 자동으로 재시도하도록:

VSCode 설정(`Ctrl+,`) > "remote.SSH.connectTimeout"을 `60`으로 설정:

```json
// settings.json (로컬)
{
    "remote.SSH.connectTimeout": 60,
    "remote.SSH.maxReconnectionAttempts": 5
}
```

### 5. 대역폭 절약 설정

느린 네트워크에서 VSCode Remote의 응답성을 높이려면:

```json
// 로컬 settings.json
{
    "remote.SSH.compression": true,
    "extensions.experimental.affinity": {
        "vscodevim.vim": 1
    }
}
```

---

## 자주 발생하는 문제와 해결책

**문제 1: "Could not establish connection to openclaw-vm"**

```
[Error] Failed to connect to remote.
Could not establish connection to "openclaw-vm".
```

원인 및 해결:
```bash
# 1. 로컬에서 Tailscale 상태 확인
tailscale status
# openclaw-vm이 목록에 없다면 VM의 Tailscale이 꺼진 것

# 2. VM SSH에서 Tailscale 재시작
gcloud compute ssh openclaw-vm --zone=asia-northeast3-a
sudo systemctl restart tailscaled
sudo tailscale up

# 3. 연결 테스트
ping 100.96.45.12
ssh -v [USER]@100.96.45.12
```

**문제 2: "Remote host key has changed"**

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
```

VM을 재생성했거나 다른 VM에 같은 IP를 사용할 때 발생한다:

```bash
# known_hosts에서 해당 항목 제거
ssh-keygen -R 100.96.45.12
ssh-keygen -R openclaw-vm

# 재연결
ssh [USER]@100.96.45.12
```

**문제 3: VSCode Server 설치 실패**

```
Installing VS Code Server...
Error: 28 out of disk space
```

해결: VM 디스크 여유 공간 확인 및 정리

```bash
# VM 내에서
df -h /
# /dev/sda1 사용률이 90% 이상이면 정리 필요

# 불필요한 apt 캐시 정리
sudo apt clean
sudo apt autoremove -y

# VSCode Server 캐시 정리 (문제 시)
rm -rf ~/.vscode-server/bin/*
```

**문제 4: Python 확장이 인터프리터를 찾지 못함**

```
"No Python interpreter is selected"
```

해결:
```bash
# VM 내에서 Python 경로 확인
which python3
# /usr/bin/python3

# 또는 가상환경 경로
ls ~/openclaw/.venv/bin/python
```

VSCode에서 `Ctrl+Shift+P` > `Python: Select Interpreter` > 경로 직접 입력

---

## 대안: Cursor를 VSCode 대신 사용하기

### Cursor란

Cursor는 VSCode를 포크(fork)한 에디터로, AI 코드 어시스턴트 기능이 네이티브로 통합되어 있다. OpenClaw와 함께 쓸 때의 차별점:

- **Claude, GPT-4, Gemini 선택 가능**: 에디터 내에서 직접 여러 모델과 대화
- **Composer 기능**: 여러 파일에 걸친 코드 변경을 한 번에 제안하고 적용
- **기존 VSCode 설정 가져오기**: 확장 프로그램, 키바인딩, 테마 마이그레이션 지원

### Cursor 설치 및 Remote-SSH 설정

[https://cursor.sh](https://cursor.sh) 에서 운영체제에 맞게 설치.

Cursor도 VSCode와 동일하게 Remote-SSH를 지원한다:

1. `Ctrl+Shift+P` > `Remote-SSH: Connect to Host...`
2. `openclaw-vm` 선택 (동일한 `~/.ssh/config` 파일 공유)
3. 연결 완료 후 Cursor의 AI 기능이 VM 코드베이스에 직접 접근 가능

### Cursor에서 OpenClaw 활용 팁

VM에 연결된 Cursor에서 Claude Code(CLI)와 Cursor AI를 병렬로 활용하는 워크플로:

```
Cursor Composer      → 여러 파일에 걸친 리팩토링, 새 기능 초안 작성
Claude Code (터미널) → 에이전트 실행, 테스트, 반복 작업 자동화
```

두 도구를 상호보완적으로 쓰면 생산성이 크게 오른다. Composer로 코드 구조를 잡고, Claude Code로 실제 실행 및 검증을 맡기는 방식이 효과적이다.

### Cursor에서 Claude API 직접 연결

Cursor Settings > Models > Add Model:
- Provider: Anthropic
- API Key: `sk-ant-...`
- Model: `claude-opus-4-5` 또는 `claude-sonnet-4-5`

이렇게 하면 VM 내의 OpenClaw 코드를 Cursor AI가 직접 읽고 분석하며, Claude Code CLI와 다른 방식으로 대화형 개발이 가능하다.

---

## 전체 설정 요약 체크리스트

```
[ ] GCP VM(e2-highmem-2)에 SSH로 초기 접속
[ ] VM에 Tailscale 설치 및 인증 (tailscale up)
[ ] VM Tailscale IP 확인 (tailscale ip -4)
[ ] 로컬 머신에 Tailscale 설치 및 동일 계정 로그인
[ ] tailscale status로 양쪽 모두 온라인 확인
[ ] ~/.ssh/config에 openclaw-vm 항목 추가 (Tailscale IP 사용)
[ ] ssh openclaw-vm 으로 접속 테스트
[ ] VSCode 설치 + Remote-SSH 확장 설치
[ ] VSCode에서 Remote-SSH로 openclaw-vm 연결
[ ] 프로젝트 폴더 열기
[ ] Python, Pylance, Ruff 확장 VM 측에 설치
[ ] .vscode/settings.json 설정
[ ] tmux 설치 및 세션 관리 익히기
[ ] (선택) Cursor 설치 및 동일 설정 적용
```

설정이 모두 완료되면 GCP VM이 사실상 로컬 개발 머신처럼 동작한다. 인터넷이 되는 곳이라면 어디서든 동일한 환경에서 OpenClaw 에이전트를 개발하고 실행할 수 있다.
