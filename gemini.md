Gunakan variable environment untuk API key Gemini.
Contoh:

GOOGLE_API_KEY=YOUR_GEMINI_API_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash-lite

Contoh curl aman (PowerShell, tanpa hardcode key di source code):
$env:GOOGLE_API_KEY="YOUR_GEMINI_API_KEY_HERE"
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent" `
  -H "Content-Type: application/json" `
  -H "X-goog-api-key: $env:GOOGLE_API_KEY" `
  -X POST `
  -d '{
    "contents": [
      {
        "parts": [
          {
            "text": "Explain how AI works in a few words"
          }
        ]
      }
    ]
  }'
