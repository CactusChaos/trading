from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models import Comment, Project
from app.schemas import CommentCreate, Comment as CommentSchema

router = APIRouter()

@router.post("/projects/{project_id}/comments", response_model=CommentSchema)
async def add_comment(project_id: str, comment: CommentCreate, db: AsyncSession = Depends(get_db)):
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_comment = Comment(project_id=project_id, **comment.model_dump())
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)
    return db_comment

@router.get("/projects/{project_id}/comments", response_model=list[CommentSchema])
async def list_comments(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment)
        .where(Comment.project_id == project_id)
        .order_by(Comment.created_at.desc())
    )
    return result.scalars().all()
