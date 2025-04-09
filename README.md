# GitHub Repository Analyzer

A FastAPI server that verifies if a GitHub repository is TypeScript/JavaScript based.

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Server

```
uvicorn app.main:app --reload
```

The server will start at http://127.0.0.1:8000

## API Endpoints

### GET /

Returns a simple welcome message.

### POST /verify

Verifies if a GitHub repository is TypeScript/JavaScript based.

**Parameters:**
- `github_url`: The GitHub repository URL

**Example Request:**
```
curl -X POST "http://127.0.0.1:8000/verify" -d "github_url=https://github.com/user/repo"
```

**Example Response:**
```json
{
  "repository": "user/repo",
  "is_javascript_typescript": true,
  "languages": {
    "JavaScript": 12345,
    "TypeScript": 54321,
    "HTML": 3456
  }
}
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc 