import time
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import requests
import sqlite3
import os
import urllib.parse
from functools import lru_cache

app = FastAPI(title="AI Search Stremio Addon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
)

# Configuration
SEARCH_API_URL = os.environ.get("SEARCH_API_URL", "http://search-api:8080")
MEDIAFLOW_URL = os.environ.get("MEDIAFLOW_URL", "http://mediaflow-proxy:8000") # Internal
FILE_SERVER_URL = os.environ.get("FILE_SERVER_URL", "http://localhost:8090") # Configuration for file server
PUBLIC_DOMAIN = os.environ.get("PUBLIC_DOMAIN", "http://localhost:8080") # Needs to be public for Stremio to play
DB_PATH = "/data/media_library.db"

MANIFEST = {
    "id": "org.antigravity.aisearch",
    "version": "1.0.1",
    "name": "AI Semantic Search",
    "description": "Search your library using natural language and AI.",
    "types": ["movie"],
    "catalogs": [
        {"type": "movie", "id": "ai_search", "name": "AI Search", "extra": [{"name": "search", "isRequired": False}]}
    ],
    "resources": ["catalog", "stream", "meta"],
    "idPrefixes": ["ai_"]
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;") # Enable Write-Ahead Logging for concurrency
    conn.row_factory = sqlite3.Row
    return conn

@lru_cache(maxsize=100)
def cached_search(query: str):
    try:
        response = requests.get(f"{SEARCH_API_URL}/search", params={"q": query, "limit": 10}, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Search API Error: {e}")
        return {"results": []}

@app.get("/manifest.json")
async def get_manifest(response: Response):
    response.headers["Cache-Control"] = "max-age=86400, public" # Cache for 1 day
    return MANIFEST

@app.get("/catalog/movie/ai_search.json")
@app.get("/catalog/movie/ai_search/search={query}.json")
async def get_catalog(response: Response, query: str = ""):
    response.headers["Cache-Control"] = "max-age=3600, public" # Cache for 1 hour
    
    if not query:
        return {"metas": []}

    # Call Search API (Cached)
    data = cached_search(query)

    metas = []
    for item in data.get("results", []):
        metas.append({
            "id": f"ai_{item['id']}",
            "type": "movie",
            "name": item['title'],
            "description": item['description']
        })

    return {"metas": metas}

@app.get("/meta/movie/{id}.json")
async def get_meta(response: Response, id: str):
    response.headers["Cache-Control"] = "max-age=43200, public" # Cache for 12 hours
    
    # Retrieve details from DB
    clean_id = id.replace("ai_", "")
    
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM movies WHERE id = ?", (clean_id,)).fetchone()
    except Exception as e:
        print(f"DB Error: {e}")
        row = None
    finally:
        conn.close()

    if not row:
         return {"meta": {"id": id, "type": "movie", "name": "Unknown"}}

    meta = {
        "id": id,
        "type": "movie",
        "name": row['title'],
        "description": row['description_en'] if 'description_en' in row.keys() else "No description",
    }
    # Optional fields
    if 'year' in row.keys(): meta['releaseInfo'] = str(row['year'])
    if 'poster' in row.keys(): meta['poster'] = row['poster']
    if 'background' in row.keys(): meta['background'] = row['background']

    return {"meta": meta}

@app.get("/stream/movie/{id}.json")
async def get_stream(response: Response, id: str):
    response.headers["Cache-Control"] = "no-cache" # Do not cache streams
    clean_id = id.replace("ai_", "")
    
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM movies WHERE id = ?", (clean_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return {"streams": []}

    stream_url = None
    if 'url' in row.keys() and row['url']:
        stream_url = row['url']
        # If it's a direct link, we might want to proxy it if Mediaflow is set up for that.
        # For now, we return it directly as per standard behavior unless user specifically asked for proxying everything.
    elif 'path' in row.keys() and row['path']:
        # It's a local file path. Stremio CANNOT play local paths from a remote server.
        # We MUST proxy this.
        # Since we don't have a file server set up for /data, but we have Mediaflow...
        # Mediaflow usually proxies HTTP URLs. 
        # Ideally, we should have Caddy serve the /data directory statically if we want to play files.
        # For now, let's assume we return a warning if it's a path, or try to construct a hypothetical URL.
        # As a fallback, we return the path but unlikely to work without a file server.
        stream_url = row['path']

    if not stream_url:
        return {"streams": [{"title": "No URL found in DB"}]}

    # Construct the final URL
    # If it's a remote URL, we use it directly or proxy via Mediaflow
    # If it's a local path, we MUST direct it to the File Server
    
    final_url = stream_url
    title_prefix = "Stream"

    if stream_url.startswith("/"):
        # It's a local path, e.g., /data/movies/movie.mp4
        # We need to prepend the FILE_SERVER_URL
        # Ensure we don't double slash
        clean_path = stream_url.lstrip("/")
        final_url = f"{FILE_SERVER_URL}/{clean_path}"
        title_prefix = "Local File"

    # Optional: Route through Mediaflow if desired (not strictly necessary for simple file serving but good for "God Mode" unification)
    # final_url = f"{MEDIAFLOW_URL}/proxy/stream?url={urllib.parse.quote(final_url)}"

    return {
        "streams": [
            {
                "title": f"{title_prefix} via God Mode",
                "url": final_url
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
