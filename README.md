# AI Media Stack

A completely self-hosted, intelligent media ecosystem.

## Overview
This stack integrates **Ollama** and **ChromaDB** to enable semantic search and automated metadata tagging for your media library. It allows you to search by meaning (e.g., "movies about time travel") rather than just keywords.

## Key Features
- **Semantic Search**: Powered by local LLM inference (Llama 3.1) and vector storage.
- **Automated Metadata**: Background worker auto-classifies, tags, and translates content.
- **Unified Playback**: Custom Stremio addon providing a single interface for all media.
- **High-Performance**: Mediaflow Proxy ensures smooth streaming.
- **Local Support**: Dedicated Nginx server for reliable local file playback.

## Setup
1. Copy `.env.example` to `.env`.
2. Run `docker compose up -d`.
3. Add `http://localhost:8083/manifest.json` to Stremio.

## License
MIT
