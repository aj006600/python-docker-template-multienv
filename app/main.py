from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="python-docker-template-multienv", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    # 顯示目前環境，證明設定隨環境切換
    return {"env": settings.app_env, "log_level": settings.log_level}
