import os
import json
from flask import Flask, request, jsonify
from google.cloud import storage
import google.generativeai as genai

# --------------------
# CONFIG
# --------------------
BUCKET_NAME = "sisl-connect-content"
MODEL_NAME = "gemini-2.0-flash-lite"

# Gemini API configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    # Fallback to Application Default Credentials
    genai.configure()

app = Flask(__name__)

# --------------------
# CORS SUPPORT
# --------------------
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response
def load_section(section: str):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"{section}/content.json")
    data = json.loads(blob.download_as_text())
    return data

def detect_sections(query: str):
    q = query.lower()
    sections = set()

    # Services and solutions
    if any(k in q for k in ["service", "services", "solution", "solutions", "offering", "offerings"]):
        sections.add("services")
    
    # Company information and about
    if any(k in q for k in ["vision", "mission", "about", "company", "sisl", "organization", "team", "people"]):
        sections.add("about-us")
    
    # Case studies and portfolio
    if any(k in q for k in ["case study", "case-study", "project", "portfolio", "work", "client", "success"]):
        sections.add("case-studies")
    
    # Partners and partnerships
    if any(k in q for k in ["partner", "partners", "partnership", "collaboration"]):
        sections.add("our-partners")
        sections.add("growth-partners")
    
    # Contact information
    if any(k in q for k in ["contact", "email", "phone", "address", "location", "reach"]):
        sections.add("contact")
    
    # Events and webinars
    if any(k in q for k in ["event", "events", "webinar", "conference", "seminar", "training"]):
        sections.add("events")
    
    # Growth and expansion
    if any(k in q for k in ["growth", "expand", "develop", "scale"]):
        sections.add("growth-partners")
    
    # General inquiry
    if any(k in q for k in ["help", "question", "info", "information", "how"]):
        sections.add("home")

    # Safe fallback - include main sections
    if not sections:
        sections.update(["home", "services", "about-us"])

    return list(sections)

def build_context(sections):
    texts = []
    sources = []

    for s in sections:
        try:
            data = load_section(s)
            texts.extend(data.get("chunks", [])[:3])  # cap per section
            sources.append(data.get("source_url"))
        except Exception:
            continue

    context = "\n\n".join(texts)
    return context, list(set(sources))

# --------------------
# ROUTES
# --------------------
@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400

    sections = detect_sections(question)
    context, sources = build_context(sections)

    prompt = f"""
You are SISL Connect Bot, an official information assistant for SISL Infotech Pvt. Ltd.
Answer ONLY using the provided content.
If the answer is not present, say:
"The requested information is not available on SISL Infotech's knowledge base."

CONTENT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Be concise and factual
- Do not infer or add external knowledge
- Be professional and helpful
- If you mention specific services or products, cite them accurately
"""

    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)

    return jsonify({
        "answer": response.text,
        "sources": sources
    })

@app.route("/")
def health():
    return "SISL Connect Bot is running", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))