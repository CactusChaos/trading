from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Project
from app.schemas import ProjectCreate, Project as ProjectSchema, ProjectWithDetails

router = APIRouter()

@router.post("/", response_model=ProjectSchema)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    db_proj = Project(**project.model_dump())
    db.add(db_proj)
    await db.commit()
    await db.refresh(db_proj)
    return db_proj

@router.get("/", response_model=list[ProjectSchema])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return result.scalars().all()

@router.get("/{project_id}", response_model=ProjectWithDetails)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.attempts), selectinload(Project.comments))
        .where(Project.id == project_id)
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj
