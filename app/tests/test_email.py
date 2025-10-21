"""
Test script for AI email processing
Run this after starting the server to test email AI features
"""
import requests
import json
from pprint import pprint

# Configuration
BASE_URL = "http://127.0.0.1:8000"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"  # Replace with your actual token

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


def test_list_unread_emails():
    """Test listing unread emails with categories"""
    print("\n" + "="*50)
    print("TEST 1: List Unread Emails")
    print("="*50)
    
    response = requests.get(
        f"{BASE_URL}/email/unread-list",
        headers=headers,
        params={"limit": 5}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {data['count']} unread emails")
        print(f"✓ Total estimate: {data['total_estimate']}")
        print(f"\nCategory Counts:")
        pprint(data['category_counts'])
        
        print(f"\nHigh Priority Emails: {len(data['categorized']['high_priority'])}")
        print(f"Medium Priority Emails: {len(data['categorized']['medium_priority'])}")
        print(f"Low Priority Emails: {len(data['categorized']['low_priority'])}")
        
        if data['emails']:
            print(f"\nFirst email:")
            email = data['emails'][0]
            print(f"  ID: {email['id']}")
            print(f"  Subject: {email['subject']}")
            print(f"  Sender: {email['sender']}")
            print(f"  Category: {email['category']}")
            print(f"  Priority: {email['priority']}")
            print(f"  Requires Reply: {email['requires_reply']}")
            return email['id']  # Return first message ID for next test
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.json())
        return None


def test_get_categories():
    """Test getting email category summary"""
    print("\n" + "="*50)
    print("TEST 2: Get Email Categories")
    print("="*50)
    
    response = requests.get(
        f"{BASE_URL}/email/categories",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Category Summary:")
        pprint(data)
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.json())


def test_process_email_with_ai(message_id):
    """Test AI processing of a single email"""
    print("\n" + "="*50)
    print("TEST 3: Process Email with AI")
    print("="*50)
    print(f"Processing message ID: {message_id}")
    
    response = requests.post(
        f"{BASE_URL}/email/process",
        headers=headers,
        json={"message_id": message_id}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ {data['message']}")
        
        email_summary = data['email_summary']
        print(f"\n📧 Email Summary:")
        print(f"  Subject: {email_summary['subject']}")
        print(f"  Sender: {email_summary['sender']}")
        print(f"  Category: {email_summary['category']}")
        
        print(f"\n📝 AI Summary:")
        print(f"  {email_summary['summary']}")
        
        print(f"\n✍️ Drafted Reply:")
        print(f"  {email_summary['drafted_reply']}")
        
        if email_summary['action_items']:
            print(f"\n✅ Action Items:")
            for item in email_summary['action_items']:
                print(f"  - {item['action_text']}")
        else:
            print(f"\n✅ No action items found")
            
        return email_summary['id']
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.json())
        return None


def test_get_email_summaries():
    """Test retrieving stored email summaries"""
    print("\n" + "="*50)
    print("TEST 4: Get Stored Email Summaries")
    print("="*50)
    
    response = requests.get(
        f"{BASE_URL}/email/summaries",
        headers=headers,
        params={"limit": 5}
    )
    
    if response.status_code == 200:
        summaries = response.json()
        print(f"✓ Found {len(summaries)} stored summaries")
        
        for summary in summaries[:3]:  # Show first 3
            print(f"\n  Subject: {summary['subject']}")
            print(f"  Category: {summary['category']}")
            print(f"  Processed: {summary['created_at']}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.json())


def main():
    print("\n🚀 Starting Email AI Processing Tests")
    print("="*50)
    
    # Test 1: List unread emails
    message_id = test_list_unread_emails()
    
    # Test 2: Get category summary
    test_get_categories()
    
    # Test 3: Process email with AI (if we have a message)
    if message_id:
        test_process_email_with_ai(message_id)
    else:
        print("\n⚠️ No unread emails found to process")
    
    # Test 4: Get stored summaries
    test_get_email_summaries()
    
    print("\n" + "="*50)
    print("✅ All tests completed!")
    print("="*50)


if __name__ == "__main__":
    # Instructions
    print("""
    📋 INSTRUCTIONS:
    1. Make sure your server is running (python main.py)
    2. Replace ACCESS_TOKEN with your actual token
    3. Make sure you have unread emails in your Gmail
    4. Run this script: python test_email_ai.py
    """)
    
    # Uncomment the line below after setting your ACCESS_TOKEN
    # main()
    
    print("\n⚠️ Please update ACCESS_TOKEN in the script before running!")