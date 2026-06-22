import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    firm_id: uuid.UUID
    name: str
    status: str
    connected_at: datetime | None
