import requests
import json
import datetime
from bs4 import BeautifulSoup
from google.cloud import storage
from urllib.parse import urljoin

BUCKET_NAME = "sisl-connect-content"

# SISL Infotech website sections to index
BASE_URL = "https://www.sislinfotech.com"

URLS = {
    "home": "https://www.sislinfotech.com/",
    "services": "https://www.sislinfotech.com/services/",
    "case-studies": "https://www.sislinfotech.com/case-study/",
    "our-partners": "https://www.sislinfotech.com/our-partners/",
    "about-us": "https://www.sislinfotech.com/about-us/",
    "contact": "https://www.sislinfotech.com/contact/",
    "events": "https://www.sislinfotech.com/events/",
    "growth-partners": "https://www.sislinfotech.com/growth-partners/",
}

def clean_html(html):
    """Clean HTML content by removing scripts, styles, and navigation elements"""
    soup = BeautifulSoup(html, "html.parser")

    # Remove unnecessary elements
    for tag in soup(["script", "style", "nav", "footer", "header", "meta"]):
        tag.decompose()

    # Get text with proper separation
    text = soup.get_text(separator="\n")
    
    # Clean up excessive whitespace
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)

def chunk_text(text, chunk_size=500):
    """Split text into chunks by word count"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk.strip():  # Only add non-empty chunks
            chunks.append(chunk)
    return chunks

def upload_json(section, data):
    """Upload JSON data to Google Cloud Storage"""
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"{section}/content.json")
        blob.upload_from_string(
            json.dumps(data, indent=2),
            content_type="application/json"
        )
        print(f"✅ Successfully indexed: {section}")
    except Exception as e:
        print(f"❌ Error uploading {section}: {e}")

def scrape_section(section, url):
    """Scrape a single section from the website"""
    try:
        print(f"📥 Scraping {section} from {url}...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        
        clean_text = clean_html(response.text)
        chunks = chunk_text(clean_text)

        if not chunks:
            print(f"⚠️  No content found for {section}")
            return None

        payload = {
            "section": section,
            "source_url": url,
            "last_updated": datetime.datetime.now(datetime.UTC).isoformat(),
            "total_words": sum(len(chunk.split()) for chunk in chunks),
            "chunk_count": len(chunks),
            "chunks": chunks
        }

        return payload
        
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout while scraping {section}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error while scraping {section}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"🔗 HTTP Error {e.response.status_code} for {section}: {url}")
        return None
    except Exception as e:
        print(f"❌ Error scraping {section}: {e}")
        return None

def discover_pages():
    """Test base URL to discover available pages"""
    try:
        print(f"🔍 Testing connection to {BASE_URL}...")
        response = requests.get(BASE_URL, timeout=10)
        if response.status_code == 200:
            print(f"✅ Successfully connected to {BASE_URL}")
            return True
        else:
            print(f"❌ Base URL returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to {BASE_URL}: {e}")
        return False

def run_indexer(request=None):
    """Main indexer function - scrapes all sections and uploads to GCS"""
    print("🚀 Starting SISL Connect Bot Indexing...")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"📦 Storage Bucket: {BUCKET_NAME}")
    print("-" * 60)
    
    # Check if website is accessible
    if not discover_pages():
        print("\n⚠️  IMPORTANT: Update the URLS dictionary with correct paths!")
        print(f"   Current URLs: {list(URLS.keys())}")
        if request:
            return ("Unable to connect to website. Check BASE_URL and URLS configuration.", 400)
        else:
            return "Unable to connect to website."
    
    print("-" * 60)
    
    if len(URLS) <= 1:
        print("\n⚠️  ERROR: URLS dictionary is empty or contains only the base URL!")
        print("   Please update the URLS dictionary with actual page paths.")
        print("   Example:")
        print('       "about": f"{BASE_URL}/about-us/",')
        print('       "services": f"{BASE_URL}/services/",')
        if request:
            return ("URLS configuration is empty. Please configure page URLs.", 400)
        else:
            return "URLS configuration is empty."
    
    successful = 0
    failed = 0
    
    for section, url in URLS.items():
        payload = scrape_section(section, url)
        
        if payload:
            upload_json(section, payload)
            successful += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"🎯 Indexing Summary:")
    print(f"   ✅ Successful: {successful}/{len(URLS)}")
    print(f"   ❌ Failed: {failed}/{len(URLS)}")
    print(f"   ⏰ Completed at: {datetime.datetime.now(datetime.UTC).isoformat()}")
    
    if request:
        return (f"SISL Connect Bot indexing completed. {successful} sections indexed.", 200)
    else:
        return f"SISL Connect Bot indexing completed. {successful} sections indexed."

if __name__ == "__main__":
    # Allow direct execution for testing
    run_indexer()