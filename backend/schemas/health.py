from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: float
    database: str
    redis: str
    llm: str
