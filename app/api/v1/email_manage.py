from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Query
from typing import List, Optional
from ...services.email_service import GmailService
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.email import (
    EmailSummaryResponse,
    ProcessEmailRequest,
    SendReplyRequest,
    EmailActionItemResponse
)
from ...db.models.email_manage import EmailSummary, EmailActionItem
from ...core.ollama_config import check_ollama_status
from fastapi.responses import StreamingResponse
from ...services.ai_processor import ai_processor

router = APIRouter(prefix='/email', tags=['email'])


@router.get("/unread-list")
async def get_unread_email_list(
    user: user_dependency, 
    db: db_dependency, 
    limit: int = Query(20, ge=1, le=100),
    page_token: Optional[str] = None,
    category: Optional[str] = Query(None, description="Filter by category: primary, social, promotions, updates, forums")
):

    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        gmail_service = GmailService(user, db)
        
        result = gmail_service.list_unread_emails_paginated(
            max_results=limit, 
            page_token=page_token,
            category_filter=category
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_email_categories(
    user: user_dependency,
    db: db_dependency
):

    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    try:
        gmail_service = GmailService(user, db)
        
        # Fetch a larger batch to get accurate counts
        result = gmail_service.list_unread_emails_paginated(max_results=100)
        
        return {
            "category_counts": result['category_counts'],
            "high_priority_count": len(result['categorized']['high_priority']),
            "medium_priority_count": len(result['categorized']['medium_priority']),
            "low_priority_count": len(result['categorized']['low_priority']),
            "total_unread": result['count']
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_single_email(
    request: ProcessEmailRequest,
    user: user_dependency,
    db: db_dependency,
    force: bool = Query(False, description="Force re-processing even if already exists")
):

    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    # Check if already processed
    existing = db.query(EmailSummary).filter(
        EmailSummary.gmail_message_id == request.message_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if existing and not force:
        return {
            "message": "Email already processed (use force=true to re-process)",
            "email_summary": existing,
            "email_summary_id": existing.id
        }
    
    gmail_service = GmailService(user, db)
    
    try:
        processed = gmail_service.process_email_with_ai(request.message_id)
        
        if existing:
            existing.subject = processed['subject']
            existing.sender = processed['sender']
            existing.email_body = processed['body']
            existing.summary = processed['summary']
            existing.drafted_reply = processed['drafted_reply']
            existing.category = processed.get('ai_category', processed.get('category'))
            db.commit()
            db.refresh(existing)
            email_summary = existing
            
            db.query(EmailActionItem).filter(
                EmailActionItem.email_summary_id == existing.id
            ).delete()
        else:
            # Store in database
            email_summary = EmailSummary(
                user_id=user.id,
                gmail_message_id=processed['id'],
                thread_id=processed.get('thread_id'),
                subject=processed['subject'],
                sender=processed['sender'],
                email_body=processed['body'],
                summary=processed['summary'],
                drafted_reply=processed['drafted_reply'],
                category=processed.get('ai_category', processed.get('category'))
            )
            db.add(email_summary)
            db.commit()
            db.refresh(email_summary)
        
        # Add action items
        for action_text in processed.get('action_items', []):
            action_item = EmailActionItem(
                email_summary_id=email_summary.id,
                action_text=action_text
            )
            db.add(action_item)
        
        db.commit()
        
        return {
            "message": "Email processed successfully" if not existing else "Email re-processed successfully",
            "email_summary": email_summary,
            "email_summary_id": email_summary.id,
            "priority": processed.get('priority'),
            "requires_reply": processed.get('category') in ['primary', 'unknown']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-list", response_model=List[EmailSummaryResponse])
async def get_unread_emails(user: user_dependency, db: db_dependency):

    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    raise HTTPException(
        status_code=410, 
        detail="This endpoint is deprecated. Use /email/unread-list to list emails, then /email/process to process individual emails."
    )


@router.get("/summaries", response_model=List[EmailSummaryResponse])
async def get_email_summaries(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 50
):
    summaries = db.query(EmailSummary).filter(
        EmailSummary.user_id == user.id
    ).order_by(EmailSummary.created_at.desc()).offset(skip).limit(limit).all()
    
    return summaries


@router.get("/summary/{email_summary_id}", response_model=EmailSummaryResponse)
async def get_email_summary(
    email_summary_id: int,
    user: user_dependency,
    db: db_dependency
):
    summary = db.query(EmailSummary).filter(
        EmailSummary.id == email_summary_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Email summary not found")
    
    return summary


@router.post("/send-reply")
async def send_reply(
    request: SendReplyRequest,
    user: user_dependency,
    db: db_dependency
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    # Get email summary
    email_summary = db.query(EmailSummary).filter(
        EmailSummary.id == request.email_summary_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not email_summary:
        raise HTTPException(status_code=404, detail="Email summary not found")
    
    gmail_service = GmailService(user, db)
    
    try:
        # Use custom reply if provided, otherwise use drafted reply
        reply_body = request.custom_reply if request.custom_reply else email_summary.drafted_reply
        
        if not reply_body:
            raise HTTPException(status_code=400, detail="No reply body available")
        
        # Extract sender email
        sender_email = email_summary.sender.split('<')[-1].strip('>') if '<' in email_summary.sender else email_summary.sender
        
        # Send email
        gmail_service.send_email(
            to=sender_email,
            subject=f"Re: {email_summary.subject}",
            body=reply_body,
            reply_to_message_id=email_summary.gmail_message_id
        )
        
        # Mark as replied
        email_summary.reply_sent = True
        db.commit()
        
        return {"message": "Reply sent successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-read/{email_summary_id}")
async def mark_email_as_read(
    email_summary_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Mark email as read"""
    email_summary = db.query(EmailSummary).filter(
        EmailSummary.id == email_summary_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not email_summary:
        raise HTTPException(status_code=404, detail="Email summary not found")
    
    if user.google_access_token:
        gmail_service = GmailService(user, db)
        try:
            gmail_service.mark_as_read(email_summary.gmail_message_id)
        except Exception as e:
            print(f"Error marking as read in Gmail: {e}")
    
    email_summary.is_read = True
    db.commit()
    
    return {"message": "Email marked as read"}


@router.get("/action-items", response_model=List[EmailActionItemResponse])
async def get_all_action_items(
    user: user_dependency,
    db: db_dependency,
    completed: bool = False
):
    """Get all action items from emails"""
    action_items = db.query(EmailActionItem).join(EmailSummary).filter(
        EmailSummary.user_id == user.id,
        EmailActionItem.is_completed == completed
    ).all()
    
    return action_items


@router.post("/action-item/{action_item_id}/complete")
async def complete_action_item(
    action_item_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Mark action item as completed"""
    action_item = db.query(EmailActionItem).join(EmailSummary).filter(
        EmailActionItem.id == action_item_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not action_item:
        raise HTTPException(status_code=404, detail="Action item not found")
    
    action_item.is_completed = True
    db.commit()
    
    return {"message": "Action item marked as complete"}


@router.get("/ai-status")
async def get_ai_status():
    status = check_ollama_status()
    return status


@router.post("/summarize")
async def summarize_email(
    request: ProcessEmailRequest,
    user: user_dependency,
    db: db_dependency,
    force: bool = Query(False, description="Force re-summarization even if already exists")
):

    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    try:
        # Check if already summarized
        existing = db.query(EmailSummary).filter(
            EmailSummary.gmail_message_id == request.message_id,
            EmailSummary.user_id == user.id
        ).first()
        
        # If exists and not forcing, return existing
        if existing and not force:
            return {
                "message": "Email already summarized (use force=true to re-summarize)",
                "message_id": request.message_id,
                "email_summary_id": existing.id,
                "subject": existing.subject,
                "sender": existing.sender,
                "summary": existing.summary,
                "category": existing.category
            }
        
        # Fetch email from Gmail
        gmail_service = GmailService(user, db)
        email = gmail_service.get_message(request.message_id)
        
        # Generate new summary
        summary = ai_processor.summarize_email(
            email_content=email['body'],
            sender=email['sender'],
            subject=email['subject']
        )
        
        # Update existing or create new
        if existing:
            # Update existing record
            existing.summary = summary
            existing.category = email.get('category', 'unknown')
            existing.email_body = email['body']
            db.commit()
            db.refresh(existing)
            
            return {
                "message": "Email re-summarized successfully",
                "message_id": request.message_id,
                "email_summary_id": existing.id,
                "subject": existing.subject,
                "sender": existing.sender,
                "summary": summary,
                "category": email.get('category'),
                "priority": email.get('priority')
            }
        else:
            # Create new record
            email_summary = EmailSummary(
                user_id=user.id,
                gmail_message_id=email['id'],
                thread_id=email.get('thread_id'),
                subject=email['subject'],
                sender=email['sender'],
                email_body=email['body'],
                summary=summary,
                category=email.get('category', 'unknown')
            )
            db.add(email_summary)
            db.commit()
            db.refresh(email_summary)
            
            return {
                "message": "Email summarized successfully",
                "message_id": request.message_id,
                "email_summary_id": email_summary.id,
                "subject": email['subject'],
                "sender": email['sender'],
                "summary": summary,
                "category": email.get('category'),
                "priority": email.get('priority')
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/draft-reply")
async def draft_reply_streaming(
    request: ProcessEmailRequest,
    user: user_dependency,
    db: db_dependency
):
    """Draft a reply with streaming - user sees it being typed"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    try:
        gmail_service = GmailService(user, db)
        email = gmail_service.get_message(request.message_id)
        
        from ...services.ai_processor import ai_processor
        
        # Return streaming response
        return StreamingResponse(
            ai_processor.draft_reply_stream(
                email['body'],
                email['sender'],
                email['subject']
            ),
            media_type="text/plain"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))