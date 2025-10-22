from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from ...services.task_service import TaskService
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskStats

router = APIRouter(prefix='/tasks', tags=['tasks'])


@router.post("/new", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        task = task_service.create_task(task_data)
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=List[TaskResponse])
async def get_tasks(
    user: user_dependency,
    db: db_dependency,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    filter: Optional[str] = Query(None, regex="^(due_today|overdue|completed|pending)$"),
    priority: Optional[str] = Query(None, regex="^(low|medium|high)$"),
    search: Optional[str] = None
):

    try:
        task_service = TaskService(db, user)
        tasks = task_service.get_tasks(
            skip=skip,
            limit=limit,
            filter_type=filter,
            priority=priority,
            search=search
        )
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=TaskStats)
async def get_task_stats(
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        stats = task_service.get_task_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/get", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        task = task_service.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{task_id}/update", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        task = task_service.update_task(task_id, task_data)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def mark_task_completed(
    task_id: int,
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        task = task_service.mark_as_completed(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    user: user_dependency,
    db: db_dependency
):
    try:
        task_service = TaskService(db, user)
        deleted = task_service.delete_task(task_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))