import os
import re
import html
import time
import urllib.request
import xml.etree.ElementTree as ET
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
FEED_FALLBACK_URL = "https://cloud.google.com/feeds/bigquery-release-notes.xml"

# In-memory cache for feed data
feed_cache = {
    "data": None,
    "last_fetched": 0,
    "ttl": 300  # 5 minutes cache TTL
}

def fetch_raw_feed():
    """Fetch XML content from BigQuery release notes Atom feed."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BigQueryReleaseApp/1.0'}
    urls = [FEED_URL, FEED_FALLBACK_URL]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read()
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
            continue
    return None

def clean_text_from_html(html_str):
    """Strip HTML tags and unescape entities for clean plain text."""
    if not html_str:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_str)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_atom_feed(xml_bytes):
    """Parse Atom XML feed bytes into structured release notes entries."""
    if not xml_bytes:
        return {"items": [], "categories": {}, "total": 0}
        
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"XML parse error: {e}")
        return {"items": [], "categories": {}, "total": 0}

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', ns)
    
    parsed_items = []
    category_counts = {}
    item_counter = 1

    for entry in entries:
        title = entry.findtext('atom:title', '', ns).strip()
        updated = entry.findtext('atom:updated', '', ns).strip()
        entry_id_raw = entry.findtext('atom:id', '', ns).strip()
        
        link_elem = entry.find('atom:link', ns)
        link = link_elem.attrib.get('href', '') if link_elem is not None else ''
        if not link and '#' in entry_id_raw:
            anchor = entry_id_raw.split('#')[-1]
            link = f"https://docs.cloud.google.com/bigquery/docs/release-notes#{anchor}"

        content_html = entry.findtext('atom:content', '', ns).strip()
        
        # Split entry by <h3> category headers if available
        parts = re.split(r'<h3>(.*?)</h3>', content_html, flags=re.IGNORECASE)
        
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                cat = parts[i].strip()
                # Capitalize nicely
                cat = cat.capitalize() if cat else "General"
                body_html = parts[i+1].strip() if i+1 < len(parts) else ''
                clean_text = clean_text_from_html(body_html)
                
                item_id = f"item-{item_counter}"
                item_counter += 1
                
                category_counts[cat] = category_counts.get(cat, 0) + 1
                
                parsed_items.append({
                    "id": item_id,
                    "date": title,
                    "updated": updated,
                    "link": link,
                    "category": cat,
                    "html": body_html,
                    "text": clean_text
                })
        else:
            clean_text = clean_text_from_html(content_html)
            cat = "General"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            item_id = f"item-{item_counter}"
            item_counter += 1
            
            parsed_items.append({
                "id": item_id,
                "date": title,
                "updated": updated,
                "link": link,
                "category": cat,
                "html": content_html,
                "text": clean_text
            })

    return {
        "items": parsed_items,
        "categories": category_counts,
        "total": len(parsed_items),
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }

@app.route("/")
def index():
    """Render main web application interface."""
    return render_template("index.html")

@app.route("/api/release-notes")
def get_release_notes():
    """API endpoint to get BigQuery release notes.
    Query param `refresh=true` or `force=true` bypasses cache.
    """
    force_refresh = request.args.get("refresh", "").lower() in ("true", "1") or request.args.get("force", "").lower() in ("true", "1")
    now = time.time()
    
    if force_refresh or feed_cache["data"] is None or (now - feed_cache["last_fetched"] > feed_cache["ttl"]):
        raw_xml = fetch_raw_feed()
        if raw_xml:
            feed_cache["data"] = parse_atom_feed(raw_xml)
            feed_cache["last_fetched"] = now
        elif feed_cache["data"] is None:
            return jsonify({"status": "error", "message": "Failed to fetch release notes feed."}), 502
            
    res_data = dict(feed_cache["data"])
    res_data["cached"] = not force_refresh
    res_data["cache_age_seconds"] = int(now - feed_cache["last_fetched"])
    return jsonify(res_data)

@app.route("/api/generate-tweet", methods=["POST"])
def generate_tweet():
    """API endpoint to generate formatted tweet text for a release note update."""
    data = request.get_json() or {}
    text = data.get("text", "")
    date = data.get("date", "")
    category = data.get("category", "")
    link = data.get("link", "")
    hashtags = data.get("hashtags", ["#BigQuery", "#GoogleCloud", "#DataEngineering"])
    
    prefix = f"🚀 BigQuery Update ({date}) [{category}]: " if category else f"🚀 BigQuery Update ({date}): "
    tags_str = " " + " ".join(hashtags) if hashtags else ""
    link_str = f"\n🔗 {link}" if link else ""
    
    # 280 char max limit for X / Twitter
    available_len = 280 - len(prefix) - len(tags_str) - len(link_str) - 5
    if available_len < 20:
        available_len = 50
        
    truncated_text = text
    if len(text) > available_len:
        truncated_text = text[:available_len].rsplit(' ', 1)[0] + "..."
        
    tweet_text = f"{prefix}{truncated_text}{link_str}{tags_str}".strip()
    
    return jsonify({
        "tweet": tweet_text,
        "length": len(tweet_text),
        "is_valid": len(tweet_text) <= 280
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
