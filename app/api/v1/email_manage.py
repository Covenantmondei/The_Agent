from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import List
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

router = APIRouter(prefix='/email', tags=['email'])


@router.get("/unread", response_model=List[EmailSummaryResponse])
async def get_unread_emails(user: user_dependency, db: db_dependency):
    """Fetch and process unread emails from Gmail"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        gmail_service = GmailService(user, db)  # Pass db
        
        processed_emails = gmail_service.fetch_and_process_unread_emails(max_results=20)
        
        # Store in database
        stored_emails = []
        for email_data in processed_emails:
            # Check if already exists
            existing = db.query(EmailSummary).filter(
                EmailSummary.gmail_message_id == email_data['id']
            ).first()
            
            if not existing:
                email_summary = EmailSummary(
                    user_id=user.id,
                    gmail_message_id=email_data['id'],
                    thread_id=email_data.get('thread_id'),
                    subject=email_data['subject'],
                    sender=email_data['sender'],
                    email_body=email_data['body'],
                    summary=email_data['summary'],
                    drafted_reply=email_data['drafted_reply'],
                    category=email_data['category']
                )
                db.add(email_summary)
                db.commit()
                db.refresh(email_summary)
                
                # Add action items
                for action_text in email_data.get('action_items', []):
                    action_item = EmailActionItem(
                        email_summary_id=email_summary.id,
                        action_text=action_text
                    )
                    db.add(action_item)
                
                db.commit()
                stored_emails.append(email_summary)
            else:
                stored_emails.append(existing)
        
        return stored_emails
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summaries", response_model=List[EmailSummaryResponse])
async def get_email_summaries(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 50
):
    """Get stored email summaries"""
    summaries = db.query(EmailSummary).filter(
        EmailSummary.user_id == user.id
    ).offset(skip).limit(limit).all()
    
    return summaries


@router.get("/summary/{email_summary_id}", response_model=EmailSummaryResponse)
async def get_email_summary(
    email_summary_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Get specific email summary"""
    summary = db.query(EmailSummary).filter(
        EmailSummary.id == email_summary_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Email summary not found")
    
    return summary


@router.post("/process")
async def process_single_email(
    request: ProcessEmailRequest,
    user: user_dependency,
    db: db_dependency
):
    """Process a single email with AI"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    gmail_service = GmailService(user)
    
    try:
        processed = gmail_service.process_email_with_ai(request.message_id)
        
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
            category=processed['category']
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
            "message": "Email processed successfully",
            "email_summary_id": email_summary.id,
            "summary": processed['summary'],
            "drafted_reply": processed['drafted_reply']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-reply")
async def send_reply(
    request: SendReplyRequest,
    user: user_dependency,
    db: db_dependency
):
    """Send drafted reply to email"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    
    # Get email summary
    email_summary = db.query(EmailSummary).filter(
        EmailSummary.id == request.email_summary_id,
        EmailSummary.user_id == user.id
    ).first()
    
    if not email_summary:
        raise HTTPException(status_code=404, detail="Email summary not found")
    
    gmail_service = GmailService(user)
    
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
        gmail_service = GmailService(user)
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