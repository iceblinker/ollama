from fastapi import FastAPI, Response
import json

app = FastAPI()

SAMPLE_DATA = {
    "metas": [
        {
            "id": "vix_1",
            "name": "Big Buck Bunny",
            "description": "A large and lovable rabbit deals with three tiny bullies, led by a flying squirrel, who are determined to squelch his happiness.",
            "releaseInfo": "2008",
            "poster": "https://upload.wikimedia.org/wikipedia/commons/c/c5/Big_buck_bunny_poster_big.jpg",
            "background": "https://upload.wikimedia.org/wikipedia/commons/c/c5/Big_buck_bunny_poster_big.jpg",
            "genres": ["Animation", "Short", "Comedy"]
        },
        {
            "id": "vix_2",
            "name": "Sintel",
            "description": "A lonely young woman, Sintel, helps and befriends a dragon, whom she calls Scales. But when he is kidnapped by an adult dragon, Sintel decides to embark on a dangerous quest to find her lost friend Scales.",
            "releaseInfo": "2010",
            "poster": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Sintel_poster.jpg/800px-Sintel_poster.jpg",
            "background": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Sintel_poster.jpg/800px-Sintel_poster.jpg",
            "genres": ["Animation", "Fantasy", "Action"]
        },
        {
            "id": "vix_3",
            "name": "Tears of Steel",
            "description": "In an apocalyptic future, a group of soldiers and scientists takes refuge in the Oude Kerk in Amsterdam to stage a desperate mission to save the world from destructive robots.",
            "releaseInfo": "2012",
            "poster": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Tears_of_Steel_poster.jpg/800px-Tears_of_Steel_poster.jpg",
            "background": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Tears_of_Steel_poster.jpg/800px-Tears_of_Steel_poster.jpg",
            "genres": ["Sci-Fi", "Short"]
        }
    ]
}

@app.get("/catalog/movie/vixsrc_movies.json")
def get_catalog():
    return SAMPLE_DATA

@app.get("/catalog/movie/vixsrc_movies/skip={skip}.json")
def get_catalog_skip(skip: int):
    # Retrieve skip logic
    if skip >= len(SAMPLE_DATA["metas"]):
        return {"metas": []}
    return SAMPLE_DATA

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
