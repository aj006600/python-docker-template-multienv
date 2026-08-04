# Local Development

[← README](../README.md) ｜ 觀念先修：[concepts.md](concepts.md)

## Quickstart

`make dev` 用於**本機開發**：起服務、掛載 source code 並開啟 hot reload，直接連 `localhost`，不經任何 proxy。

```bash
make dev          # APP_ENV=dev：服務起來、hot reload（前景執行，佔住終端機）
# → http://localhost:8000（會顯示目前環境）；/health
make dev-down     # 停止並清理：移除本機開發的 container 與 network
```

`make dev` 用 `compose.dev.yaml`：開 8000、掛載 source code + hot reload。

> 收工用 **`make dev-down`** 停止並清理。`make dev` 是前景執行，也可直接按 **`Ctrl+C`** 停止——但 `Ctrl+C` 只是停止 container（仍殘留為 exited 狀態），`make dev-down` 會進一步**移除**殘留的 container 與 network。

## Testing changes (hot reload)

`make dev` 已掛載 source code 並開啟 `uvicorn --reload`，所以測試一個改動**不需進 container、也不需 rebuild**：

1. 在**本機**編輯 `app/*.py`（用你的編輯器）。
2. Container 內的 uvicorn 偵測到變更、**自動 reload**。
3. 直接打 API 驗證：

```bash
curl http://localhost:8000/          # 或 /health
```

注意：

- **Hot reload 只適用 `make dev`**（只有它掛載了 source code + `--reload`）。
- **Preview / deploy（`make up-*`）不掛載 source code**，跑的是 build 好的 image——改本機程式碼不會反映，需 rebuild（重跑 `make up-*` 即可，見 [concepts.md](concepts.md)）。

## Entering containers (docker exec)

承上，改程式碼靠 hot reload 即可、**不需進 container**。進 container 是為了「在 container 內執行指令 / 檢查 / 除錯」——例如查看環境變數、執行一次性腳本、確認相依安裝，或在 container 的環境裡跑測試（`docker exec -it <容器名> uv run pytest`）。

用 compose 的 **service 名**進入（免查容器名，在專案根目錄執行）：

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec app bash
```

或用容器名（先以 `docker ps` / `make ps` 查名稱）：

```bash
docker exec -it <容器名> bash
```

Container 內：工作目錄為 `/app`、程式在 `/app/app`、venv 在 `/app/.venv`（`uvicorn`、`pytest` 等已在 PATH）。**以非 root 的 `appuser` 執行**。需要安裝系統套件時，改用 root 進入：

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec -u root app bash
```

> 上述指令針對 `make dev`。若跑的是 preview（`make up-*`），各環境 project 名不同（如 `python-dev`），用 `docker ps` 查容器名後以 `docker exec -it <容器名> …` 進入最直接。

## Working without containers

更快的內層迴圈（inner loop）：

```bash
uv sync --dev                                      # 建立環境、裝相依
APP_ENV=dev uv run uvicorn app.main:app --reload   # 起服務（hot reload，:8000）
uv run pytest -q                                   # 跑測試
uv add <package>                                   # 新增相依（自動更新 uv.lock）
```

## Inspecting what's running

```bash
docker compose ls        # 有哪些 compose project 在跑（一眼看出起了哪些環境/topology）
make ps                  # 模板內建：正在跑的 container（名稱 / 狀態 / 埠）
docker ps                # 同上，未美化
```

看更完整（含停掉殘留、network）：

```bash
docker ps -a             # 連「停掉但殘留」的 container 也列（exited 狀態）
docker compose ls -a     # 連停掉的 compose project 也列
docker network ls        # 有哪些 network（proxy、各 project network）
```

> 每個 preview/deploy 環境是獨立的 compose project（`python-dev` / `python-qas` / `python-prod`）；`make dev` 則以資料夾名當 project 名。用 `docker compose ls` 對照 project 名，就知道哪個 topology/環境正開著。
