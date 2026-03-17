from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dingtalk_app_secret: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    openclaw_webhook_url: str = "http://localhost:3000/webhook"

    model_config = {"env_file": ".env"}


settings = Settings()
