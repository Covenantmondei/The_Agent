# Productivity Assistant API

A comprehensive AI-powered productivity platform with email management, task/calendar integration, and **live Google Meet transcription** for mobile devices.

## 🌟 Features

- **Email Management**: AI-powered email summarization and reply drafting
- **Task & Calendar Integration**: Google Calendar sync with task management
- **Live Meeting Transcription**: Real-time Google Meet transcription using Whisper
- **Mobile-First Audio Streaming**: Capture device audio and stream to backend via WebSocket
- **AI Summaries**: Structured meeting summaries with key points, decisions, and action items
- **Background Processing**: Auto-detect calendar meetings and start transcription
- **Grace Period Handling**: 90-second grace period for unexpected disconnections

## 📋 Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Environment Setup](#environment-setup)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Mobile Integration](#mobile-integration)
- [WebSocket Protocol](#websocket-protocol)
- [Database Models](#database-models)
- [Testing](#testing)
- [Docker Deployment](#docker-deployment)
- [Troubleshooting](#troubleshooting)
- [Security & Privacy](#security--privacy)

## 🏗️ Architecture

```
Mobile App (React Native/Flutter)
    ↓ (Audio Capture: MediaProjection/ReplayKit)
    ↓ (WebSocket: Binary audio chunks)
FastAPI Backend
    ↓ (Whisper: Real-time transcription)
    ↓ (WebSocket: JSON transcript chunks)
Mobile App (Live transcript display)
    ↓ (Meeting ends)
Backend (LLM: Structured summary)
    ↓ (Database: Store transcript + summary)
```

**Key Components:**
- **Whisper** (local): Real-time speech-to-text transcription
- **LLM** (Ollama/OpenAI-compatible): Structured meeting summaries
- **PostgreSQL**: Persistent data storage
- **WebSocket**: Bidirectional real-time streaming
- **Background Tasks**: Calendar polling, inactive session cleanup

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL
- ffmpeg (for audio processing)
- Google Cloud Project with OAuth credentials
- Ollama (for local LLM) or OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/Covenantmondei/The_Agent.git
cd AI_Agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Whisper
pip install openai-whisper
```

## ⚙️ Environment Setup

Create a `.env` file in the project root:

```env
# Security
SECRET_KEY=your-super-secret-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/productivity_db

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# AI Services
OPENAI_API_KEY=your-openai-key  # If using OpenAI cloud
OLLAMA_BASE_URL=http://localhost:11434  # If using local Ollama

# Whisper
WHISPER_DEVICE=cpu  # or 'cuda' for GPU
```

### Database Setup

```bash
# Run migrations
alembic upgrade head

# Create new migration (if models changed)
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 🏃 Running the Application

### Development Mode

```bash
# Start the server
uvicorn main:app --reload

# Or using the main.py directly
python main.py
```

The application will:
- Start on `http://localhost:8000`
- Initialize database tables
- Start background services:
  - Task scheduler
  - Calendar poller (checks every 60s)
  - Inactive session checker (checks every 30s)

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📡 API Reference

### Authentication

Most endpoints require JWT authentication via `Authorization: Bearer <token>` header.

### Email Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/email/unread-list` | GET | List unread emails with pagination |
| `/email/summarize` | POST | Summarize email (supports `?force=true`) |
| `/email/process` | POST | Full email processing (summary + draft reply) |
| `/email/draft-reply` | POST | Generate reply (streaming) |
| `/email/send-reply` | POST | Send drafted or custom reply |

### Meeting Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/meetings/join` | POST | Start ad-hoc meeting session |
| `/meetings/live` | GET | Get active and upcoming meetings |
| `/meetings/{id}/stop` | POST | Stop meeting and generate summary |
| `/meetings/{id}/transcript` | GET | Get full transcript and summary |
| `/meetings/{id}/summary` | GET | Get summary only |
| `/meetings/{id}/summary/retry` | POST | Retry failed summarization |
| `/meetings/{id}/status` | GET | Get meeting status and stats |
| `/meetings/` | GET | List all meetings (with filters) |
| `/meetings/{id}` | DELETE | Delete meeting |

### WebSocket Endpoint

```
ws://<host>/ws/meeting/{meeting_id}?token=<jwt>
```

## 📱 Mobile Integration

### Meeting Flow (React Native/Flutter)

#### 1. Start Meeting Session

```javascript
// Ad-hoc join
const response = await fetch('http://localhost:8000/meetings/join', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    meet_url: 'https://meet.google.com/abc-defg-hij',
    title: 'Project Sync'
  })
});

const { session_id, websocket_url } = await response.json();
// Returns: { session_id: 123, websocket_url: "/ws/meeting/123", ... }
```

#### 2. Connect WebSocket

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/meeting/${session_id}?token=${token}`);

ws.onopen = () => {
  console.log('Connected to meeting transcription');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'transcript') {
    // Display transcript
    console.log(`[${data.sequence_number}] ${data.text}`);
  }
};
```

#### 3. Stream Audio

```javascript
// React Native example with expo-av
import { Audio } from 'expo-av';

const { recording } = await Audio.Recording.createAsync({
  android: {
    extension: '.m4a',
    outputFormat: Audio.RECORDING_OPTION_ANDROID_OUTPUT_FORMAT_MPEG_4,
    audioEncoder: Audio.RECORDING_OPTION_ANDROID_AUDIO_ENCODER_AAC,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
  },
  ios: {
    extension: '.m4a',
    audioQuality: Audio.RECORDING_OPTION_IOS_AUDIO_QUALITY_HIGH,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
  },
});

// Send chunks every 3 seconds
setInterval(async () => {
  const uri = recording.getURI();
  const response = await fetch(uri);
  const blob = await response.blob();
  const arrayBuffer = await blob.arrayBuffer();
  
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(arrayBuffer);
  }
}, 3000);
```

#### 4. Stop Meeting

```javascript
// Close WebSocket
ws.close();

// Or call API
await fetch(`http://localhost:8000/meetings/${session_id}/stop`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` }
});
```

#### 5. Fetch Summary

```javascript
const response = await fetch(`http://localhost:8000/meetings/${session_id}/transcript`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

const { meeting, transcripts, summary } = await response.json();
console.log('Key Points:', summary.key_points);
console.log('Action Items:', summary.action_items);
```

## 🔌 WebSocket Protocol

### Client → Server

**Audio Chunks (Binary)**
```
Send raw audio bytes every 1-3 seconds
Format: PCM, WAV, WebM, M4A
Preferred: 16kHz, mono, 16-bit
```

**Control Messages (JSON)**
```json
{"action": "ping"}
{"action": "status"}
```

### Server → Client

**Connection Confirmation**
```json
{
  "type": "connection",
  "message": "Connected to meeting transcription",
  "meeting_id": 123,
  "status": "active"
}
```

**Transcript Chunks**
```json
{
  "type": "transcript",
  "meeting_id": 123,
  "timestamp": "2025-10-26T10:30:00Z",
  "text": "Let's discuss the Q4 roadmap.",
  "sequence_number": 5,
  "is_final": true
}
```

**Status Response**
```json
{
  "type": "status",
  "meeting_id": 123,
  "is_recording": true,
  "sequence_number": 42,
  "buffer_size": 48000
}
```

## 🗄️ Database Models

### Meeting
```python
- id: int (PK)
- user_id: int (FK)
- meet_link: str
- title: str
- start_time: datetime
- end_time: datetime (nullable)
- status: str (scheduled, active, finalizing, completed, failed)
- is_manual: bool
- last_activity: datetime
- calendar_event_id: str (nullable)
```

### MeetingTranscript
```python
- id: int (PK)
- meeting_id: int (FK)
- timestamp: datetime
- text: str
- sequence_number: int
- is_final: bool
- speaker: str (nullable)
```

### MeetingSummary
```python
- id: int (PK)
- meeting_id: int (FK)
- full_transcript: text
- key_points: text
- decisions: text
- action_items: json (array)
- follow_ups: text
- summary_unavailable: bool
- error_message: text (nullable)
```

## 🧪 Testing

### Run Tests

```bash
# Unit tests
pytest

# Integration test
python test_meeting.py
```

### Manual WebSocket Testing

```bash
# Install wscat
npm install -g wscat

# Connect and test
wscat -c "ws://localhost:8000/ws/meeting/123?token=YOUR_JWT_TOKEN"

# Send ping
> {"action": "ping"}

# Send audio (from file)
# Use a tool to send binary data or modify wscat
```

### API Testing with cURL

```bash
# Start meeting
curl -X POST http://localhost:8000/meetings/join \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"meet_url":"https://meet.google.com/test","title":"Test Meeting"}'

# Get status
curl http://localhost:8000/meetings/123/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Stop meeting
curl -X POST http://localhost:8000/meetings/123/stop \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🐳 Docker Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/productivity_db
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - db
      - ollama
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: productivity_db
    volumes:
      - postgres_data:/var/lib/postgresql/data

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  postgres_data:
  ollama_data:
```

### Run with Docker

```bash
# Build and start
docker-compose up --build

# Stop
docker-compose down

# View logs
docker-compose logs -f api
```

## 🔧 Troubleshooting

### Common Issues

**1. Google OAuth Errors**
```
Error: Token refresh failed
Solution: 
- Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env
- User may need to re-authenticate
- Verify OAuth scopes match those in auth.py
```

**2. Whisper Model Load Failures**
```
Error: Model not found
Solution:
- Ensure internet connection for first-time download
- Check ~/.cache/whisper/ for model files
- For GPU: ensure CUDA installed and fp16=True in code
```

**3. LLM Connection Issues**
```
Error: Invalid URL 'None/api/tags'
Solution:
- Set OLLAMA_BASE_URL in .env
- Verify Ollama is running: curl http://localhost:11434/api/tags
- Check firewall/Docker network configuration
```

**4. WebSocket Disconnections**
```
Error: WebSocket closed unexpectedly
Solution:
- Verify token passed as query parameter: ?token=JWT
- Check logs/transcription.log for errors
- Ensure mobile maintains network connection
- Grace period (90s) allows reconnection
```

**5. No Summary Generated**
```
Error: summary_unavailable = true
Solution:
- Check logs for AI summarization errors
- Verify transcript has sufficient content (>10 chars)
- Use POST /meetings/{id}/summary/retry to regenerate
- Check LLM service is accessible
```

**6. Audio Processing Errors**
```
Error: Could not detect audio format
Solution:
- Install ffmpeg: sudo apt install ffmpeg (Linux) or brew install ffmpeg (Mac)
- Ensure pydub is installed: pip install pydub
- Check audio chunk format from mobile (prefer 16kHz WAV/PCM)
```

### Logs Location

```
logs/
├── app.log              # General application logs
├── meeting.log          # Meeting service logs
└── transcription.log    # Whisper transcription logs
```

### Debug Mode

Enable detailed logging in `main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## 🔒 Security & Privacy

### Best Practices

1. **Transport Security**
   - Use TLS/SSL in production (`wss://` for WebSocket)
   - Enable HTTPS for all API endpoints
   - Never send tokens in URL paths (use headers/query params over secure connection)

2. **Data Protection**
   - Encrypt database at rest
   - Implement data retention policies
   - Provide transcript deletion endpoints
   - Redact PII from logs

3. **Authentication**
   - Use short-lived JWT tokens (1-24 hours)
   - Implement token refresh mechanism
   - Validate WebSocket token on connect
   - Rate limit API endpoints

4. **Audio Privacy**
   - Audio chunks are processed and discarded (not stored permanently)
   - Only transcripts are persisted
   - Implement GDPR-compliant data export/deletion

### Environment Security

```bash
# Never commit .env file
echo ".env" >> .gitignore

# Use strong SECRET_KEY (generate with)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📁 Project Structure

```
AI_Agent/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── alembic.ini               # Alembic configuration
├── .env                      # Environment variables (not in git)
├── alembic/
│   ├── env.py                # Alembic environment
│   └── versions/             # Database migrations
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py       # Authentication endpoints
│   │       ├── email_manage.py   # Email endpoints
│   │       ├── meeting.py        # Meeting REST API
│   │       ├── meeting_ws.py     # WebSocket handler
│   │       ├── task.py           # Task endpoints
│   │       ├── calendar.py       # Calendar endpoints
│   │       └── summary.py        # Summary endpoints
│   ├── core/
│   │   ├── config.py         # Configuration
│   │   ├── security.py       # Security utilities
│   │   └── oauth.py          # OAuth handlers
│   ├── db/
│   │   ├── base.py           # Database base
│   │   ├── session.py        # DB session
│   │   └── models/
│   │       ├── meeting.py    # Meeting models
│   │       ├── email_manage.py   # Email models
│   │       ├── user.py       # User model
│   │       └── task.py       # Task model
│   ├── schemas/
│   │   ├── meeting.py        # Meeting Pydantic schemas
│   │   ├── email.py          # Email schemas
│   │   └── ...
│   ├── services/
│   │   ├── ai_processor.py          # LLM integration
│   │   ├── meeting_service.py       # Meeting business logic
│   │   ├── transcription_service.py # Whisper transcription
│   │   ├── email_service.py         # Gmail integration
│   │   ├── calendar_service.py      # Google Calendar
│   │   └── scheduler.py             # Background tasks
│   └── utils/
│       ├── logger.py         # Logging utilities
│       └── notifications.py  # Notification helpers
├── logs/                     # Application logs
├── tests/                    # Unit tests
└── test_meeting.py          # Integration test
```

## 🚀 Next Steps & Extensibility

### Potential Enhancements

1. **Speaker Diarization**
   - Identify and label different speakers
   - Update `MeetingTranscript.speaker` field

2. **Partial Results**
   - Stream non-final transcripts for ultra-low latency
   - Add confidence scores

3. **Multi-language Support**
   - Auto-detect language with Whisper
   - Translate summaries

4. **Advanced Audio Processing**
   - Noise reduction
   - Echo cancellation
   - Audio quality metrics

5. **Analytics Dashboard**
   - Meeting duration statistics
   - Word clouds from transcripts
   - Action item tracking

6. **Integrations**
   - Slack notifications for summaries
   - Export to Google Docs/Notion
   - Calendar event updates with summary

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Whisper Documentation](https://github.com/openai/whisper)
- [Ollama Documentation](https://ollama.ai/)
- [Google Calendar API](https://developers.google.com/calendar)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

## 📝 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines]

## 👥 Authors

[Add authors/maintainers]

---

**Built with ❤️ using FastAPI, Whisper, and Ollama**

