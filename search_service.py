from fastapi import FastAPI, Query
import requests
import chromadb
from typing import List
import os

app = FastAPI(title="AI Media Search API")

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = "nomic-embed-text"
CHROMA_HOST = os.environ.get("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8000))

# Initialize Chroma Client
client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
collection = client.get_or_create_collection(name="movie_descriptions")

def get_query_embedding(text: str):
    """Convert search query into a vector using Ollama."""
    payload = {"model": EMBED_MODEL, "input": text}
    try:
        response = requests.post(f"{OLLAMA_URL}/api/embed", json=payload)
        response.raise_for_status()
        return response.json().get("embeddings", [None])[0]
    except Exception as e:
        print(f"Embedding error: {e}")
        return None

@app.get("/search")
async def search_movies(q: str = Query(..., description="Natural language search query"), limit: int = 5):
    """
    Perform semantic search. 
    Example: /search?q=movies about giant sharks in Italy
    """
    vector = get_query_embedding(q)
    if not vector:
        return {"error": "Could not generate embedding for query"}

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[vector],
        n_results=limit,
        include=["documents", "metadatas", "distances"]
    )

    # Format output for the addon
    formatted_results = []
    if results["ids"]:
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "title": results["metadatas"][0][i].get("title"),
                "score": 1 - results["distances"][0][i], # Convert distance to similarity score
                "description": results["documents"][0][i]
            })

    return {"query": q, "results": formatted_results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
