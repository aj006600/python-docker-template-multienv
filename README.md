# python-docker-template-multienv

多環境（dev / qas / prd）Python 服務容器化的**最精簡**範本：Docker + docker compose + GitHub Actions CI/CD，遵循業界最佳實踐。

> 核心原則（12-factor）：**一份程式碼、一個映像、設定隨環境變**。絕不複製程式碼，環境差異只在設定。

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
├── Makefile                    # make dev / up-separate-hosts / up-port-* / up-domain-*
└── .github/workflows/ci-cd.yml # test → build 一次 → promote dev→qas→prod
```

> 三種部署模式**擇一使用**（不是同時跑）——差別只在「怎麼對外曝露」。
> C 模式用的共用 Traefik 在獨立的 **[`traefik-proxy`](../traefik-proxy)** repo。

## 三根支柱

### A. 設定分環境
每個環境一個 `env/.env.<env>` 檔，`app/config.py` 用 pydantic-settings 讀進來。
**只提交非機密設定**；真正的密鑰放 CI secrets 或 gitignored 的 `env/*.local`。

### B. compose 決定怎麼跑 / 曝露
本機開發用 `make dev`（localhost:8000 熱重載）；部署則有**三種模式擇一**——
同一份 base、同一個映像，只差對外曝露方式（詳見下方〈三種部署模式〉）。

### C. CI/CD promotion（最佳實踐核心）
**build 一次 → 打不可變的 git SHA 標籤 → 同一個 SHA 依序部署到 dev → qas → prod。**
三個環境部署的是**同一個映像檔**（用 SHA 指定），不重 build、不靠 `latest`——保證「dev 測過的就是上 prod 的」。

```
push main ─▶ test ─▶ build(:sha) ─▶ deploy-dev ─▶ deploy-qas ─▶ deploy-prod
                                                                    ▲
                                          GitHub Environment「production」設 required reviewers
                                          → 上 prod 需人工核准
```

> deploy 步驟目前是 placeholder（印出要部署的映像與環境）。promotion 結構與審核閘門已就緒，
> 把 `echo` 換成你的實際部署指令即可（SSH pull + compose up、或 k8s/雲端 CLI）。

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
domain 解析：本機 `*.localhost` 零設定；團隊免 DNS 用 `dev.<機器IP>.nip.io`；正式對外用真實域名 + DNS + TLS。

### 共通提醒
- B、C 三環境同機，沒有真正的故障/安全隔離——prod 若重要選 A。
- B、C 各環境是**獨立的 compose project**（獨立網路/容器）。
- 對外正式 prod 不管哪種模式都還需要：真實域名 + TLS + 對外曝露 + 安全強化。

## 一次性設定（GitHub）

以下設定存在 GitHub、不在程式碼裡，各做一次即可。

### 1. prod 人工核准（Environments）

> **注意：預設行為是測試通過就一路直接部署到 prod，不會停下來等人核准。**
> workflow 裡的 `environment: production` 只是掛了個標籤，本身不會擋部署。

要讓 prod 上線前**卡住等人核准**：

1. 到 repo **Settings → Environments** 建立 `dev`、`qas`、`production` 三個 environment
2. 在 `production` 加上 **Required reviewers**（指定誰能核准）

設定前後的差別：

```
未設定：  test → dev → qas → prod            （一路直接部署，沒人攔）
設定後：  test → dev → qas →（等核准）→ prod  （prod 前停下等指定的人按核准）
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
build(:sha) → 部署 dev→qas→prod   # 6. CI/CD 啟動
```

三個關鍵：

- **測試在 PR 就自動跑**（不用等本機）——當作合併前的守門員。
- **「build + 部署」只在 merge 到 main 時才發生**，PR 階段只跑測試。
- **純文件變更（`.md`）不觸發 build/deploy**（靠 `paths-ignore`）。

對照 `ci-cd.yml` 的觸發設定：

```yaml
on:
  push:
    branches: [main]      # merge 到 main → build + 部署
    paths-ignore:         # 純文件變更不觸發（PR 仍會跑測試）
      - '**.md'
      - 'docs/**'
  pull_request:
    branches: [main]      # 開 PR → 只跑測試（守門）
```

| 時機 | 會跑什麼 |
|------|---------|
| 開 / 更新 PR | 只跑 `test` |
| merge 到 main | `test` → `build`(:sha) → `deploy dev→qas→prod` |

> 環境（dev/qas/prod）是**部署目標**，不是分支——全程只有 `main` 一個分支。
> 要追蹤/回溯「哪個環境跑哪一版」靠 **SHA 映像標籤**（見下方常用指令），不用開環境分支。

## 部署時機：merge 即部署 vs tag 才發版

目前採用**「merge 即部署」**：每次 merge 到 main → 自動 build + 部署到各環境，prod 前用核准閘門把關。
這是**精簡又正確的甜蜜點**，先用這個就好。

等到「不想每次 merge 都上 prod」時，再加 **tag-based 發版**：merge 只部署到 dev，prod 改由打 `git tag`（如 `v1.2.0`）觸發——把「合併程式碼」和「正式發版」分開。屬於**需要再加**，現在不做。

## 常用指令

### 開發（本機，不透過容器）

```bash
uv sync --dev                                      # 建立環境、裝相依
APP_ENV=dev uv run uvicorn app.main:app --reload   # 起服務（熱重載）
uv run pytest -q                                   # 跑測試
uv add <package>                                   # 新增相依（自動更新 uv.lock）
```

### 部署（容器，三種模式擇一）

```bash
make dev                       # 本機開發：localhost:8000 熱重載
make up-separate-hosts ENV=dev # A：每環境獨立主機（標準 80 埠）
make up-port-dev|qas|prod      # B：同機不同 port
make up-domain-dev|qas|prod    # C：同機 Traefik 依 domain（先起 traefik-proxy）
make ps                        # 看容器狀態
```

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

# 2. 直接跑那個舊映像（本機示範；真部署時把部署指令指向這個 tag 即可）
docker pull ghcr.io/<your-account>/python-docker-template-multienv:<old-sha>
docker run -p 8000:8000 ghcr.io/<your-account>/python-docker-template-multienv:<old-sha>
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
