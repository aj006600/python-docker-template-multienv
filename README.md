# python-docker-template-multienv

多環境（dev / qas / prod）Python 服務容器化範本：Docker + docker compose + GitHub Actions CI/CD、三種部署模式，遵循業界最佳實踐。
（想要更簡單的單環境起點，見 [`python-docker-template-minimal`](../python-docker-template-minimal)）

> 核心原則（12-factor）：**一份程式碼、一個映像、設定隨環境變**。絕不複製程式碼，環境差異只在設定。

> 刻意留白、上 production 前依需要再加的項目（實裝部署、Secrets、TLS、DB、健康檢查、可觀測性、安全掃描、多架構）見 **[docs/roadmap.md](docs/roadmap.md)**。

## 結構

```
.
├── app/
│   ├── main.py                 # / 顯示目前環境；/health
│   └── config.py               # pydantic-settings：從環境變數讀設定
├── tests/
├── Dockerfile                  # 單階段 uv + 非 root
├── pyproject.toml · uv.lock
├── compose.yaml                # base：只定義服務與內部設定
├── compose.dev.yaml            # 本機開發：開 localhost:8000 + 熱重載
├── deploy/                     # 三種部署模式（同一個 app、只差怎麼曝露）
│   ├── compose.separate-hosts.yaml     # A：每環境各自一台主機（最佳實踐）
│   ├── compose.same-host-by-port.yaml  # B：同機、不同 port
│   └── compose.same-host-by-domain.yaml # C：同機、Traefik 依 domain
├── env/{.env.dev,.env.qas,.env.prod}   # 各環境設定 + HTTP_PORT(B) + DOMAIN(C)
├── Makefile                    # make dev（開發）/ up-*（本機預覽）/ deploy（拉映像部署）/ down-* / ps
└── .github/workflows/ci-cd.yml # merge→build+dev/qas 自動；打 v* tag→prod
```

> 三種部署模式**擇一使用**（不是同時跑）——差別只在「怎麼對外曝露」。
> C 模式用的共用 Traefik 在獨立的 **[`traefik-proxy`](../traefik-proxy)** repo。

## 三根支柱

### 設定分環境
每個環境一個 `env/.env.<env>` 檔，`app/config.py` 用 pydantic-settings 讀進來。
**只提交非機密設定**；真正的密鑰放 CI secrets 或 gitignored 的 `env/*.local`。

### compose 決定怎麼跑 / 曝露
本機開發用 `make dev`（localhost:8000 熱重載，前景執行）；收工用 `make dev-down` 停止並清理
（或直接 `Ctrl+C` 停止——但只停不移除容器/網路，`make dev-down` 才會移除）。
部署則有**三種模式擇一**——同一份 base、同一個映像，只差對外曝露方式（詳見下方〈三種部署模式〉），
且部署模式是背景 `-d` 執行，**一定要對應的 `make down-*` 才會停**。

### CI/CD promotion（最佳實踐核心）
**build 一次 → 打不可變的 git SHA 標籤 → 同一個映像一路 promote。** dev/qas 靠 merge 自動、prod 靠打 tag——
各環境跑的都是**同一個映像檔**（用 SHA 指定），不重 build、不靠 `latest`——保證「dev 測過的就是上 prod 的」。

```
merge main ─▶ test ─▶ build(:sha) ─▶ deploy-dev ─▶ deploy-qas      （自動）
git tag v* ─▶ test ─▶ release(:sha→:v*) ─▶ deploy-prod             （發版才觸發）
                                              ▲
                    GitHub Environment「production」設 required reviewers → 上 prod 需人工核准
```

> deploy-dev/qas/prod job 目前只**印出**「該在主機上執行的 `make deploy` 指令」，尚未連線主機。
> promotion 結構與審核閘門已就緒，接上 SSH / docker context 讓 CI 真的在主機執行該指令即可（見 [docs/roadmap.md](docs/roadmap.md)）。

**映像自動清理**：`.github/workflows/cleanup.yml` 每週跑一次——`:sha` 建置**只留最近 10 個**、**保護 `latest` 與 `v*` 正式版**、刪 untagged。避免映像無限累積。

## 三種部署模式（擇一）

同一個 app，三種「怎麼把環境跑起來/曝露」的做法。**選一種用**，不是同時跑。

| 模式 | 拓撲 | 隔離/最佳實踐 | 何時選 |
|------|------|--------------|--------|
| **A. separate-hosts** | 每環境**各自一台主機**，標準 80 埠 | 最佳實踐、完整隔離 | 有多台機器 / 在意 prod 隔離 |
| **B. same-host-by-port** | 三環境**同機、不同 port** | 最簡妥協、無隔離 | 只有一台機器、想最快 |
| **C. same-host-by-domain** | 三環境**同機、Traefik 依 domain** | 同機但用 domain（貼近真實） | 只有一台機器、要 domain |

### A. separate-hosts（最佳實踐）
在每個環境自己的主機上跑單一環境，佔標準 80 埠：
```bash
make up-separate-hosts ENV=dev    # 在 dev 主機（qas / prod 同理）
```
存取：`http://<該主機位址>`。

### B. same-host-by-port（最簡妥協）
三環境擠一台，用不同 port 區分（埠由 env 檔 `HTTP_PORT` 決定）：
```bash
make up-port-dev     # → http://<host>:8000
make up-port-qas     # → http://<host>:8001
make up-port-prod    # → http://<host>:8002
```

### C. same-host-by-domain（同機 + Traefik）
三環境擠一台，用 domain 區分（同 80 埠、Traefik 導流）：
```bash
cd ../traefik-proxy && make up && cd -   # 前置（整台機器一次）：啟動共用 Traefik
make up-domain-dev   # → http://dev.pyapp.localhost
make up-domain-qas   # → http://qas.pyapp.localhost
make up-domain-prod  # → http://pyapp.localhost
```
**domain 怎麼被解析（重要）**——網址由 env 檔的 `DOMAIN` 決定：

| 誰要連 | `DOMAIN` 寫法 | 說明 |
|--------|--------------|------|
| **只有你自己（本機）** | `dev.pyapp.localhost` | `*.localhost` 指的是**執行瀏覽器那台機器自己**（127.0.0.1）。**隊友打這個只會連到他自己的電腦、連不到你。** |
| **團隊（同網路、免 DNS）** | `dev.pyapp.<你的IP>.nip.io` | nip.io 把 `*.<IP>.nip.io` 自動解析到該 IP。隊友需在同一網路、且能連外網。查你的 IP 見下方 |
| **正式對外** | 你的真實域名 | 正規 DNS + TLS + 機器對外曝露 |

> **要給團隊連**：**執行時傳入** `DOMAIN`（**別改 `env/.env.*`**——它被 git 追蹤，IP 一旦 commit 就會進**公開 repo**，而且 IP 會變）：
>
> ```bash
> DOMAIN=dev.pyapp.<你的IP>.nip.io make up-domain-dev   # qas/prod 同理
> ```
>
> 查本機對外 IP（活躍介面**不一定**是 `en0`，別寫死）：`ipconfig getifaddr "$(route get default | awk '/interface:/{print $2}')"`

### 共通提醒
- B、C 三環境同機，沒有真正的故障/安全隔離——prod 若重要選 A。
- B、C 各環境是**獨立的 compose project**（獨立網路/容器）。
- 對外正式 prod 不管哪種模式都還需要：真實域名 + TLS + 對外曝露 + 安全強化。

## 疑難排解：埠衝突

各模式用到的 host 埠：

| 指令 | 綁的 host 埠 |
|------|------------|
| `make dev` | 8000 |
| A `make up-separate-hosts` | 80 |
| B `make up-port-dev\|qas\|prod` | 8000 / 8001 / 8002（env 的 `HTTP_PORT`） |
| C `make up-domain-*` | 80（由 traefik-proxy 佔用） |

若看到 `Bind for 0.0.0.0:<port> failed: port is already allocated`，代表該埠被占用。排查：

```bash
lsof -nP -iTCP:<port> -sTCP:LISTEN     # 看什麼程式占用
docker ps --filter publish=<port>       # 或看是哪個容器占用
```

解法：
- 停掉占用者：`docker stop <容器>`（之後 `docker start <容器>` 可原樣復活）。
- **B 模式**：改 `env/.env.*` 的 `HTTP_PORT` 換一個沒被占的埠。
- **A / C**：改用別台主機，或先停掉占 80 的服務。

## 一次性設定（GitHub）

以下設定存在 GitHub、不在程式碼裡，各做一次即可。

### 1. prod 人工核准（Environments）

> **注意：prod 只在打 `v*` tag 時才部署（merge 不會碰 prod）。但即使打了 tag，`environment: production`**
> **本身也不會擋——要設 required reviewers，發版才會停下等人核准。**

要讓 prod 上線前**卡住等人核准**：

1. 到 repo **Settings → Environments** 建立 `dev`、`qas`、`production` 三個 environment
2. 在 `production` 加上 **Required reviewers**（指定誰能核准）

設定前後的差別：

```
未設定：  git tag v* → prod                （打 tag 就直接上 prod，沒人攔）
設定後：  git tag v* →（等核准）→ prod       （打 tag 後停下等指定的人按核准）
```

### 2. 分支保護（require PR + CI 綠燈才能進 main）

**本 repo 已啟用**：`main` 禁止直接 push，任何修改（含只改 README）都必須**走 PR** 且 `test` 綠燈才能 merge；並開了 **enforce admins**，連 repo 擁有者也一樣受限、沒有例外。

> 實務結果：**不能再 `git push origin main`**，會被擋。一律走下方 PR 流程：
>
> ```bash
> git checkout -b fix/xxx
> # 改東西、commit、git push -u origin fix/xxx
> gh pr create --fill        # 開 PR
> # 等 CI 綠燈
> gh pr merge --squash        # 自己就能 merge（required approvals = 0）
> ```

若要在新 repo 重現這組設定（**Settings → Branches** 對 `main` 加規則）：

- **Require a pull request before merging**（禁止直接 push；單人可把 required approvals 設 **0**）
- **Require status checks to pass** → 勾 `test`（PR 上會跑的測試 job）
- **Do not allow bypassing the above settings**（= enforce admins，連 owner 也受限）

> 注意：免費方案的**私有** repo 無法用分支保護，需 GitHub Pro 或改為 **public**。

## 開發流程（trunk-based / GitHub flow）

只有一個長期分支 `main`。開發走「短命功能分支 → PR → 合併 main」：

```
git checkout -b feature/xxx   # 1. 從 main 開功能分支
（開發、commit）               # 2. 在分支上做事
git push + 開 PR              # 3. 推上去、開 Pull Request
（審查 + CI 綠燈）             # 4. 通過審查與 CI
merge 到 main                # 5. 合併回 main
   ↓ 自動觸發
build(:sha) → 部署 dev、qas    # 6. CI/CD（prod 要另外打 tag，見〈部署流程〉）
```

三個關鍵：

- **測試在 PR 就自動跑**（不用等本機）——當作合併前的守門員。
- **「build + 部署」只在 merge 到 main 時才發生**，PR 階段只跑測試。
- **純文件變更（`.md`）不觸發 build/deploy**（靠 `paths-ignore`）。

對照 `ci-cd.yml` 的觸發設定：

```yaml
on:
  push:
    branches: [main]      # merge → build + 部署 dev/qas
    paths-ignore:         # 純文件變更不觸發（PR 仍會跑測試）
      - '**.md'
      - 'docs/**'
    tags: ['v*']          # 打 v* tag → 部署 prod
  pull_request:
    branches: [main]      # 開 PR → 只跑測試（守門）
```

| 時機 | 會跑什麼 |
|------|---------|
| 開 / 更新 PR | 只跑 `test` |
| merge 到 main | `test` → `build`(:sha) → `deploy dev、qas` |
| 打 `v*` tag | `test` → `release`(:sha→:v*) → `deploy prod` |

> 環境（dev/qas/prod）是**部署目標**，不是分支——全程只有 `main` 一個分支。
> 要追蹤/回溯「哪個環境跑哪一版」靠 **SHA 映像標籤**（見下方常用指令），不用開環境分支。

## 部署流程：merge 到 dev/qas、打 tag 才上 prod

「合併程式碼」和「正式上 prod」分開——日常 merge 只碰 dev/qas，prod 只在你**刻意打 tag 發版**時才動。

```
merge main ─▶ build(:sha) ─▶ deploy dev ─▶ deploy qas          （自動，不含 prod）
git tag v1.2.0 ─▶ release(:sha→:v1.2.0) ─▶ deploy prod          （發版才觸發）
```

- **merge 到 `main`** → build 映像（`:sha`）+ 自動部署 **dev、qas**
- **打 `v*` tag** → 部署 **prod**：把測試過的 `:sha` **加上版本標籤 `:v1.2.0`（不重 build）**再上

### 怎麼發版（操作教學）

```bash
git checkout main && git pull          # 1. 要發的 commit 已在 main、dev/qas 驗過（:sha 已 build）
git tag v1.2.0                         # 2. 打版本 tag
git push origin v1.2.0                 # 3. 推 tag → 觸發 prod 發版
```

> - prod 前的 `production` environment 若設了 required reviewers，發版會**停下等人核准**（見上方〈一次性設定〉）。
> - tag 要打在**已在 main、已 build** 的 commit（否則找不到對應的 `:sha` 映像）。

## 三個「dev」別搞混：`make dev`、`make up-*`、CI/CD

同樣叫 dev/qas/prod，散在三處、目的完全不同。

### `make dev` vs 部署模式 `make up-*`（都在你本機）

只是寫 code 用 `make dev` 就好；要把環境實際跑起來（給人用 / 模擬部署）才用 `make up-*`。

| | `make dev` | `make up-separate-hosts` / `up-port-*` / `up-domain-*` |
|---|-----------|--------------------------------------------------------|
| 目的 | **本機開發**（寫 code） | **部署環境**（跑起來給人用 / 模擬部署） |
| 環境數 | 只有 **dev 一個** | **dev / qas / prod** 可同時並存 |
| 跑什麼 | 掛載原始碼 + **熱重載** | **建好的映像**（改 code 不反映，需重建） |
| 執行方式 | 前景（`Ctrl+C` 停、`make dev-down` 清） | 背景 `-d`（**一定要 `make down-*`** 才會停） |
| 怎麼連 | `localhost:8000` | 依模式（80 埠 / `IP:port` / domain） |

### dev / qas / prod 怎麼區分——靠 env 檔，不是不同 image

**三個環境跑的是同一個映像**（同一份 source `build:` 出來的），差別只在**載入哪份 `env/.env.<env>` 設定**（12-factor 核心：一份 code、一個 image、設定隨環境變）。接線（以 qas 為例）：

```bash
make up-domain-qas
#  = COMPOSE_PROJECT_NAME=python-qas docker compose … --env-file env/.env.qas up -d --build
```

1. `--env-file env/.env.qas` 讀進 `env/.env.qas` → 其中 `APP_ENV=qas`
2. `compose.yaml` 的 `env_file: env/.env.${APP_ENV:-dev}` 用這個 `APP_ENV` 解析成 `env/.env.qas`
3. 容器載入 `env/.env.qas`（`APP_ENV`、`LOG_LEVEL`、`DOMAIN`、`HTTP_PORT`…）

> 「是哪個環境」= **哪份 env 檔被載入**，不是哪個 image。CI/CD 部署時也一樣：build 一次打 `:sha`，dev/qas/prod promote **同一顆** `:sha`——這才保證「dev 測過的就是上 prod 的那顆」。

### 「本機 `make up-*`」和「CI/CD 部署」是兩個世界

常見誤解是「merge 一下、本機 `make up-*` 的環境就變新」——**不會**。

- **本機（你這台機器）→ 靠重跑 `make up-*`**：用**當下本機 code** 現場 `--build`；merge PR **不會**更新它們，改了 code 想變新要**自己重跑**。改完 code **直接重跑就好、不用先 `make down-*`**——`up -d --build` 會重建映像並自動把舊容器換成新的（recreate，僅幾秒短暫中斷）；只有改了 compose 結構（網路/volume/service）或想全新乾淨重來時才先 down。**本機這顆 ≠ 最近 merge 那顆 `:sha`**：`make up-*` 建的是你**本機當前 code**（連未 commit 的都算），不會去 registry 拉——`git pull` 且無改動則內容相同、有未 commit 改動則更新、落後 main 則更舊；要跑「最近 merge 那顆」用拉取式部署指令 **`make deploy`**（拉 CI 建好的 `:sha`、不重 build，見下方）。
- **遠端（CI/CD 部署）→ 靠 merge / 打 tag**：`gh pr merge` 部署 dev+qas、`git tag v*` 部署 prod（需核准）。

| 指令 | 更新哪裡 | 更新哪個環境 |
|------|---------|-------------|
| `make up-*`（**重跑**） | 你**本機** | 你指定的那一個 |
| `gh pr merge`（merge main） | **遠端 CI 部署** | **dev + qas**（不含 prod） |
| `git tag v* && git push` | **遠端 CI 部署** | **prod**（需核准） |

> CI 的 deploy 步驟目前只會**印出「該在主機上執行的 `make deploy` 指令」**，尚未真的連線主機——接上 SSH / docker context 後（見 [docs/roadmap.md](docs/roadmap.md)），「遠端」那兩列才會真的部署到伺服器。

### 本機 `make up-*` 是「預覽」，真部署用 `make deploy`

**在你機器上跑 `make up-*` ≠ 部署。** 它 `--build` 用你當前 code 現場建，用途是**預覽/測試「該環境的 `env/.env.*` 設定 + 曝露拓撲」**。三種拓撲的預覽能力不同：

- **B（port）/ C（domain）**：可在本機**同時起三個環境**，驗證各環境設定與導流（埠配置、Traefik 路由）。
- **A（separate-hosts）**：多機拓撲**無法單機模擬**；本機跑 `up-separate-hosts` 只能**一次預覽一個環境**（都綁 80）。

用詞澄清：`deploy/compose.*.yaml` 是**曝露拓撲**（部署時用哪種對外方式）；**在本機跑它們是預覽，不等於部署**。

真部署 = 在**目標主機**上拉 **CI 測過的那顆 `:sha`** 跑（不重 build），用 `make deploy`：

```bash
make deploy MODE=same-host-by-domain ENV=dev \
    IMAGE=ghcr.io/<your-account>/python-docker-template-multienv TAG=<git-sha>
# MODE = separate-hosts | same-host-by-port | same-host-by-domain
# TAG  = <git-sha>（dev/qas）或 vX.Y.Z（prod）
```

| 指令 | 職責 | 映像來源 |
|------|------|---------|
| `make dev` | 開發（熱重載） | 本機 code（掛載） |
| `make up-*` | **本機預覽** env 設定 / 拓撲 | 本機 code 現場 build |
| `make deploy` | **部署執行**（目標主機上跑；CI 與人工共用同一條） | **拉 CI 測過的 `:sha`**，不重 build |

> 環境不「知道」自己該用哪顆映像——**版本（`TAG`）是傳入的**，由 promotion 流程決定：merge → CI 以該 commit 的 sha 部署 dev+qas；打 `v*` tag → prod。人工部署 / 回溯就自己指定 `TAG`。「哪個環境跑哪顆」的紀錄 = GitHub Environments 部署歷史 + `docker ps` 的 image tag。

## 常用指令

### 開發（本機，不透過容器）

```bash
uv sync --dev                                      # 建立環境、裝相依
APP_ENV=dev uv run uvicorn app.main:app --reload   # 起服務（熱重載）
uv run pytest -q                                   # 跑測試
uv add <package>                                   # 新增相依（自動更新 uv.lock）
```

### 查看現在起了哪些東西（容器 / 專案）

```bash
docker compose ls        # 有哪些 compose 專案在跑（一眼看出起了哪些環境/模式）
make ps                  # 模板內建：正在跑的容器（名稱 / 狀態 / 埠）
docker ps -a             # 連「停掉但殘留」（exited）也列
```

> 每個部署環境是獨立的 compose 專案（`python-dev` / `python-qas` / `python-prod`）；`make dev` 則以資料夾名當專案名。用 `docker compose ls` 對照專案名，就知道哪個模式/環境正開著。

### 查看「現在跑的是哪一版」

映像用 **git SHA** 當標籤，所以「哪個環境跑哪一版」= 「跑哪個 SHA」。

```bash
git log --oneline -10                 # 看最近的 commit 與其 SHA
git show <sha>                        # 看某個 SHA 改了什麼
git checkout <sha>                    # 切過去看該版 code（看完 git switch - 回來）

docker ps --format '{{.Image}}'       # 看正在跑的容器用哪個映像
```

> GitHub 網頁 → repo → **Environments**：可看每個環境「部署了哪個 SHA、何時、由誰」的完整歷史。

### 回溯（rollback）到舊版

映像不可變且都留在 registry，所以**回溯 = 重新部署上一個好的 SHA，不用重 build**（超快）。

```bash
git log --oneline                     # 1. 找出要回到的舊 SHA

# 2. 在目標主機上把該環境部署回舊 SHA（一行，不重 build）
make deploy MODE=<擇一> ENV=prod \
    IMAGE=ghcr.io/<your-account>/python-docker-template-multienv TAG=<old-sha>
```

### 版本標記（可選，讓紀錄更清楚）

```bash
git tag v1.0.0 && git push origin v1.0.0   # 發版時打 tag
git checkout v1.0.0                          # 之後要看該版 code
```

## 備註：雙邊託管 GitLab + GitHub（尚未實作，之後需要再加）

CI 設定檔是**平台專屬**的，兩份可並存、各讀各的；`app/`、`Dockerfile`、`compose.yaml` 完全共用：

| 平台 | CI 設定檔 |
|------|----------|
| GitHub Actions | `.github/workflows/*.yml`（現有） |
| GitLab CI | `.gitlab-ci.yml`（放根目錄，之後再加） |

真的要做時，先決定三件事（不然容易踩雷）：

1. **選一邊當真相來源**，用倉庫鏡像（mirror）自動同步另一邊——避免兩邊各自 push 造成分岔。
2. **避免兩邊都跑 CI／都部署**（除非故意，例如各部署到不同雲）。
3. **secrets 與 registry 各平台各設**（GHCR vs GitLab Container Registry）。
