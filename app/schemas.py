from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    market_slug: Optional[str] = None
    token_id: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class Project(ProjectBase):
    id: str
    created_at: datetime
    class Config:
        from_attributes = True

class AttemptBase(BaseModel):
    name: str
    model_code: str
    parameters: Optional[dict] = None
    backtest_config: Optional[dict] = None

class AttemptCreate(AttemptBase):
    pass

class AttemptUpdate(AttemptBase):
    pass

class RunAttemptRequest(BaseModel):
    initial_capital: float = 100.0
    blocks_to_fetch: Optional[int] = 5000
    start_block: Optional[int] = None
    end_block: Optional[int] = None
    auto_range: bool = False
    period_hours: Optional[float] = None  # If set, fetch last N hours of trading

class Attempt(AttemptBase):
    id: str
    project_id: str
    results: Optional[dict] = None
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class CommentBase(BaseModel):
    author: str
    body: str

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: str
    project_id: str
    created_at: datetime
    class Config:
        from_attributes = True

class ProjectWithDetails(Project):
    attempts: List[Attempt] = []
    comments: List[Comment] = []
