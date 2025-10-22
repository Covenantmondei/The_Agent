from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from datetime import date, timedelta
from ...services.summary_service import SummaryService
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.summary import DailySummaryResponse, SummaryRangeResponse

router = APIRouter(prefix='/summary', tags=['summary'])


@router.get("/today", response_model=DailySummaryResponse)
async def get_today_summary(
    user: user_dependency,
    db: db_dependency
):
    """Get today's daily summary"""
    try:
        summary_service = SummaryService(db)
        summary = summary_service.get_user_summary(user)
        
        if not summary:
            # Generate on-demand if doesn't exist
            summary = summary_service.create_or_update_daily_summary(user)
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/date/{target_date}", response_model=DailySummaryResponse)
async def get_summary_by_date(
    target_date: date,
    user: user_dependency,
    db: db_dependency
):
    """Get daily summary for a specific date"""
    try:
        summary_service = SummaryService(db)
        summary = summary_service.get_user_summary(user, target_date)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this date")
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/range", response_model=List[DailySummaryResponse])
async def get_summaries_range(
    user: user_dependency,
    db: db_dependency,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back")
):
    try:
        summary_service = SummaryService(db)
        end_date = summary_service.get_wat_date()
        start_date = end_date - timedelta(days=days - 1)
        
        summaries = summary_service.get_user_summaries_range(user, start_date, end_date)
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=DailySummaryResponse, status_code=status.HTTP_201_CREATED)
async def generate_summary(
    user: user_dependency,
    db: db_dependency,
    target_date: Optional[date] = None
):
    try:
        summary_service = SummaryService(db)
        summary = summary_service.create_or_update_daily_summary(user, target_date)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))