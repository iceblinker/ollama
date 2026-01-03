import sqlite3
import requests
import json
import time
import chromadb
import os
from chromadb.config import Settings

# --- CONFIGURATION ---
# Check if running in Docker, otherwise use local paths for testing
IN_DOCKER = os.environ.get("AM_I_IN_A_DOCKER_CONTAINER", False)

DB_PATH = "/data/media_library.db"
OLLAMA_URL = "http://ollama:11434"
LLM_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"

# Initialize ChromaDB Client
# We use the http client to connect to the chromadb container
chroma_client = chromadb.HttpClient(host='chromadb', port=8000)
collection = chroma_client.get_or_create_collection(name="movie_descriptions")

def wait_for_services():
    """Ensure Ollama and Chroma are reachable before starting."""
    print("Waiting for services to warm up...")
    while True:
        try:
            # Check Ollama
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            # Check Chroma
            chroma_client.heartbeat()
            print("Services online. Starting worker.")
            break
        except Exception as e:
            print(f"Waiting for services... ({e})")
            time.sleep(5)

def ask_llm(system_prompt, user_input):
    payload = {
        "model": LLM_MODEL,
        "prompt": f"<<SYS>>\n{system_prompt}\n<</SYS>>\n\n[INST]{user_input}[/INST]",
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 4096}
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return ""

def get_embedding(text):
    payload = {"model": EMBED_MODEL, "input": text}
    try:
        response = requests.post(f"{OLLAMA_URL}/api/embed", json=payload, timeout=30)
        return response.json().get("embeddings", [None])[0]
    except Exception as e:
        print(f"Embedding Error: {e}")
        return None

    try:
        cursor.execute('''CREATE TABLE IF NOT EXISTS movies (
            id TEXT PRIMARY KEY,
            title TEXT,
            description_en TEXT,
            year TEXT,
            poster TEXT,
            background TEXT,
            genres TEXT,
            description_it TEXT,
            ai_classified INTEGER DEFAULT 0,
            phobia_warnings TEXT,
            url TEXT,
            path TEXT
        )''')
        cursor.execute("ALTER TABLE movies ADD COLUMN description_it TEXT")
        cursor.execute("ALTER TABLE movies ADD COLUMN ai_classified INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE movies ADD COLUMN phobia_warnings TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Columns already exist

def ingest_from_api(conn):
    """Downloads catalog data from the external Vixsrc Addon API."""
    print("--- Starting API Ingestion ---")
    base_url = "http://vixsrc-addon:3000/catalog/movie/vixsrc_movies"
    skip = 0
    total_ingested = 0
    
    while True:
        url = f"{base_url}/skip={skip}.json" if skip > 0 else f"{base_url}.json"
        try:
            print(f"Fetching: {url}")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 404: # End of catalog
                break
            resp.raise_for_status()
            data = resp.json()
            metas = data.get('metas', [])
            
            if not metas:
                print("No more items found.")
                break
                
            print(f"Ingesting batch of {len(metas)} items...")
            cursor = conn.cursor()
            for m in metas:
                # Upsert movie
                cursor.execute("""
                    INSERT INTO movies (id, title, description_en, year, poster, background, genres)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    description_en=excluded.description_en,
                    poster=excluded.poster
                """, (
                    m.get('id'),
                    m.get('name'),
                    m.get('description'),
                    m.get('releaseInfo'),
                    m.get('poster'),
                    m.get('background'),
                    ", ".join(m.get('genres', [])) if isinstance(m.get('genres'), list) else m.get('genres')
                ))
            conn.commit()
            total_ingested += len(metas)
            skip += len(metas)
            
            # Safety break for dev
            # if total_ingested > 1000: break 
            
        except Exception as e:
            print(f"Ingestion Error: {e}")
            break
    
    print(f"--- Ingestion Complete. Total: {total_ingested} ---")

def process_library():
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    
    # Ensure Schema Exists
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS movies (
            id TEXT PRIMARY KEY,
            title TEXT,
            description_en TEXT,
            year TEXT,
            poster TEXT,
            background TEXT,
            genres TEXT,
            description_it TEXT,
            ai_classified INTEGER DEFAULT 0,
            phobia_warnings TEXT
        )''')
    except Exception as e:
        print(f"Schema Init Error: {e}")

    # 1. Run Ingestion (New Logic)
    ingest_from_api(conn)

    cursor = conn.cursor()

    # 1. TRANSLATION & CLASSIFICATION TASK
    # Select movies that haven't been classified yet
    cursor.execute("SELECT id, title, description_en, genres FROM movies WHERE ai_classified = 0")
    movies = cursor.fetchall()

    for m_id, title, desc_en, genres in movies:
        print(f"Processing: {title}")

        if not desc_en:
            print(f"Skipping {title} (No description)")
            continue

        # Task A: Translate to Italian
        it_prompt = "Translate the following movie description into natural, professional Italian. Return ONLY the translation."
        desc_it = ask_llm(it_prompt, desc_en)

        # Task B: Animal Horror Check
        horror_prompt = (
            "Analyze if this movie belongs to the 'Animal Horror' sub-genre (animals or creatures as antagonists). "
            "Answer ONLY with 'YES' or 'NO'."
        )
        is_horror = ask_llm(horror_prompt, desc_en)
        
        # Task B.2: Phobia Filter
        phobias = ["spiders", "snakes", "clowns", "heights", "blood"]
        phobia_prompt = (
            f"Analyze the movie description for these triggers: {', '.join(phobias)}. "
            "Return a comma-separated list of triggers found. If none, return 'NONE'. "
            "Return ONLY the list."
        )
        phobia_tags = ask_llm(phobia_prompt, desc_en)
        if "NONE" in phobia_tags.upper():
            phobia_tags = ""

        # Task C: Semantic Indexing
        # We index the English description so we can search by meaning
        vector = get_embedding(desc_en)
        if vector:
            collection.upsert(
                ids=[str(m_id)],
                embeddings=[vector],
                metadatas={"title": title, "year": "2024"}, # Simplified metadata
                documents=[desc_en]
            )

        # Update Genres if it's Animal Horror
        new_genres = genres
        if is_horror and "YES" in is_horror.upper():
            new_genres = f"{genres}, Animal Horror" if genres else "Animal Horror"

        # Save to DB
        # Ensure column exists handled in main loop setup (or manually added) - adding to query
        try:
             cursor.execute(
                "UPDATE movies SET description_it = ?, genres = ?, ai_classified = 1, phobia_warnings = ? WHERE id = ?",
                (desc_it, new_genres, phobia_tags, m_id)
            )
        except sqlite3.OperationalError:
            # Fallback if column missing (should be added in setup)
            cursor.execute(
                "UPDATE movies SET description_it = ?, genres = ?, ai_classified = 1 WHERE id = ?",
                (desc_it, new_genres, m_id)
            )

        conn.commit()
        print(f"Finished {title}. (Animal Horror: {is_horror} | Phobias: {phobia_tags})")

    conn.close()

if __name__ == "__main__":
    # Wait for other containers to be ready
    wait_for_services()
    
    # Main Loop
    while True:
        process_library()
        print("Batch complete. Sleeping for 5 minutes...")
        time.sleep(300) # Check for new movies every 5 minutes
