# ytc-python-docker-template-multienv

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
├── compose.yaml                # base：依 APP_ENV 載入 env/.env.<APP_ENV>
├── compose.dev.yaml            # dev 覆寫：掛載原始碼 + 熱重載
├── env/
│   ├── .env.dev                # 各環境設定（只放非機密）
│   ├── .env.qas
│   └── .env.prod
├── Makefile                    # make dev / qas / prod
└── .github/workflows/ci-cd.yml # test → build 一次 → promote dev→qas→prod
```

## 三根支柱

### A. 設定分環境
每個環境一個 `env/.env.<env>` 檔，`app/config.py` 用 pydantic-settings 讀進來。
**只提交非機密設定**；真正的密鑰放 CI secrets 或 gitignored 的 `env/*.local`。

### B. compose 選環境
用 `APP_ENV` 變數選要載入哪個設定檔（同一份 compose、同一個映像）：

```bash
make dev     # APP_ENV=dev  + 熱重載掛載原始碼
make qas     # APP_ENV=qas
make prod    # APP_ENV=prod
```

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

## 一次性設定（GitHub）— 決定 prod 要不要人工核准

> **注意：預設行為是測試通過就一路直接部署到 prod，不會停下來等人核准。**
> workflow 裡的 `environment: production` 只是掛了個標籤，本身不會擋部署。

要讓 prod 上線前**卡住等人核准**，必須先做這個一次性設定（設定存在 GitHub，不在程式碼裡）：

1. 到 repo **Settings → Environments** 建立 `dev`、`qas`、`production` 三個 environment
2. 在 `production` 加上 **Required reviewers**（指定誰能核准）

設定前後的差別：

```
未設定：  test → dev → qas → prod            （一路直接部署，沒人攔）
設定後：  test → dev → qas →（等核准）→ prod  （prod 前停下等指定的人按核准）
```

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

兩個關鍵：

- **測試在 PR 就自動跑**（不用等本機）——當作合併前的守門員。
- **「build + 部署」只在 merge 到 main 時才發生**，PR 階段只跑測試。

對照 `ci-cd.yml` 的觸發設定：

```yaml
on:
  push:
    branches: [main]      # merge 到 main → build + 部署
  pull_request:
    branches: [main]      # 開 PR → 只跑測試（守門）
```

| 時機 | 會跑什麼 |
|------|---------|
| 開 / 更新 PR | 只跑 `test` |
| merge 到 main | `test` → `build`(:sha) → `deploy dev→qas→prod` |

> 環境（dev/qas/prod）是**部署目標**，不是分支——全程只有 `main` 一個分支。
> 要追蹤/回溯「哪個環境跑哪一版」靠 **SHA 映像標籤**（見下方常用指令），不用開環境分支。

## 常用指令

### 開發（本機，不透過容器）

```bash
uv sync --dev                                      # 建立環境、裝相依
APP_ENV=dev uv run uvicorn app.main:app --reload   # 起服務（熱重載）
uv run pytest -q                                   # 跑測試
uv add <package>                                   # 新增相依（自動更新 uv.lock）
```

### 開發（容器）

```bash
make dev              # dev：熱重載 + 掛載原始碼
make qas / make prod  # 以該環境設定在本機跑
make down             # 停掉
docker compose logs -f    # 看日誌
docker compose ps         # 看容器狀態
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
docker pull ghcr.io/<your-account>/ytc-python-docker-template-multienv:<old-sha>
docker run -p 8000:8000 ghcr.io/<your-account>/ytc-python-docker-template-multienv:<old-sha>
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
