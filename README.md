# Agentic Honey-Pot for Scam Detection & Intelligence Extraction

An AI-powered honeypot system that detects scam messages and autonomously engages scammers to extract intelligence.

## Features

- 🔍 **Scam Detection**: Advanced pattern matching and AI-based detection
- 🤖 **Multi-Agent System**: Specialized agents for persona, strategy, and intelligence extraction
- 💬 **Multi-Turn Conversations**: Handles complex conversation flows
- 🎭 **Believable Personas**: Human-like responses that don't reveal detection
- 📊 **Intelligence Extraction**: Extracts bank accounts, UPI IDs, phishing links, phone numbers
- 🔒 **API Key Authentication**: Secure access control
- 📡 **Automatic Reporting**: Sends final results to GUVI evaluation endpoint

## Architecture

```
┌─────────────────────────────────────────┐
│         Incoming Message                │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Scam Detection Module              │
│  • Pattern matching                     │
│  • Keyword analysis                     │
│  • AI classification                    │
└────────────────┬────────────────────────┘
                 │
        (if scam detected)
                 │
┌────────────────▼────────────────────────┐
│     Multi-Agent System                  │
│                                         │
│  ┌─────────────────────────────┐      │
│  │  Persona Agent              │      │
│  │  • Maintains personality    │      │
│  │  • Generates responses      │      │
│  └─────────────────────────────┘      │
│                                         │
│  ┌─────────────────────────────┐      │
│  │  Strategy Agent             │      │
│  │  • Engagement tactics       │      │
│  │  • Question selection       │      │
│  └─────────────────────────────┘      │
│                                         │
│  ┌─────────────────────────────┐      │
│  │  Extractor Agent            │      │
│  │  • Pattern extraction       │      │
│  │  • Intelligence gathering   │      │
│  └─────────────────────────────┘      │
│                                         │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│    JSON Response + GUVI Callback        │
└─────────────────────────────────────────┘
```

## Installation

### 1. Clone and Setup

```bash
cd honeypot-api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `API_KEY`: Your secret API key for authentication
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: Your LLM provider API key

### 3. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Usage

### Endpoint

```
POST /api/v1/honeypot
```

### Authentication

```
x-api-key: YOUR_SECRET_API_KEY
Content-Type: application/json
```

### Request Format

**First Message:**
```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Your bank account will be blocked today. Verify immediately.",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

**Follow-up Message:**
```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Share your UPI ID to avoid account suspension.",
    "timestamp": 1770005528731
  },
  "conversationHistory": [
    {
      "sender": "scammer",
      "text": "Your bank account will be blocked today. Verify immediately.",
      "timestamp": 1770005528731
    },
    {
      "sender": "user",
      "text": "Why will my account be blocked?",
      "timestamp": 1770005528731
    }
  ],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

### Response Format

```json
{
  "status": "success",
  "reply": "Why is my account being suspended?"
}
```

## Testing

### Example with cURL

```bash
curl -X POST http://localhost:8000/api/v1/honeypot \
  -H "x-api-key: your_secret_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-123",
    "message": {
      "sender": "scammer",
      "text": "Your bank account will be blocked. Click here: http://fake-bank.com",
      "timestamp": 1770005528731
    },
    "conversationHistory": [],
    "metadata": {
      "channel": "SMS",
      "language": "English",
      "locale": "IN"
    }
  }'
```

## Project Structure

```
honeypot-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── persona_agent.py    # Victim persona agent
│   │   ├── strategy_agent.py   # Engagement strategy
│   │   └── extractor_agent.py  # Intelligence extraction
│   ├── detection/
│   │   ├── __init__.py
│   │   └── scam_detector.py    # Scam detection logic
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── patterns.py         # Regex patterns for extraction
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models
│   └── utils/
│       ├── __init__.py
│       ├── llm_client.py       # LLM API client
│       ├── session_manager.py  # Session state management
│       └── guvi_callback.py    # GUVI API callback
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## How It Works

1. **Scam Detection**: Incoming messages are analyzed for scam indicators (urgent language, financial keywords, suspicious links)

2. **Agent Activation**: If scam is detected, the multi-agent system activates

3. **Persona Agent**: Generates human-like responses using LLM, maintains consistent personality

4. **Strategy Agent**: Determines engagement tactics to extract maximum information

5. **Extractor Agent**: Continuously monitors conversation for intelligence (bank accounts, UPI IDs, links, phone numbers)

6. **Final Callback**: When conversation ends or sufficient intelligence is gathered, sends results to GUVI endpoint

## Agent Behavior

The AI agent is designed to:
- ✅ Respond naturally like a confused/curious victim
- ✅ Ask clarifying questions to keep scammer engaged
- ✅ Show hesitation and concern (human-like behavior)
- ✅ Gradually build apparent trust
- ✅ Extract information without raising suspicion
- ❌ Never reveal it's a bot or honeypot
- ❌ Never use obviously technical language
- ❌ Never be too eager or compliant

## Evaluation Criteria

The system is evaluated on:
1. **Scam Detection Accuracy**: How well it identifies scam messages
2. **Engagement Quality**: Naturalness and believability of responses
3. **Intelligence Extraction**: Amount and quality of extracted data
4. **API Stability**: Response time and reliability
5. **Ethical Behavior**: Responsible handling of data

## Ethics & Constraints

- ❌ No impersonation of real individuals
- ❌ No illegal instructions
- ❌ No harassment
- ✅ Responsible data handling
- ✅ Only engage detected scammers
- ✅ Extract intelligence for law enforcement

## Deployment

### Local Development
```bash
uvicorn app.main:app --reload --port 8000
```

### Production (with Gunicorn)
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (Optional)
```bash
docker build -t honeypot-api .
docker run -p 8000:8000 --env-file .env honeypot-api
```

## License

MIT License - See LICENSE file for details

## Contact

For questions or issues, please open an issue on the repository.
