import os
from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Vera"
    bot_version: str = os.getenv("BOT_VERSION", "1.0.0")
    team_name: str = os.getenv("TEAM_NAME", "Team Antigravity")
    team_members: List[str] = [
        m.strip()
        for m in os.getenv("TEAM_MEMBERS", "Lead AI Engineer").split(",")
        if m.strip()
    ]
    contact_email: str = os.getenv("CONTACT_EMAIL", "team@magicpin.in")
    model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    approach: str = os.getenv(
        "APPROACH",
        "4-Context Grounded Composition Engine with Intent State Machine, Dynamic Versioning & Hallucination Guard",
    )
    llm_provider: str = os.getenv("LLM_PROVIDER", "rule_engine")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    port: int = int(os.getenv("PORT", "8080"))
    host: str = os.getenv("HOST", "0.0.0.0")


settings = Settings()
