# src/main.py
import logging
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

# Import the router objects from your route files
from src.routes import index, search, libraries, servicenow, finance

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 1. Create the application instance
app = FastAPI(title="Semantic Search API")

# 2. Define allowed origins
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://lex-chatbot.epfl.ch",
    "https://lex-chatbot-test.epfl.ch",
    # Add any other origins you need
]

# 3. Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include the routers
# This is where the magic happens. We mount the routers from other files.
# The prefix makes all routes in `index.router` start with `/index`.
# The tags group the routes nicely in the OpenAPI docs (/docs).
app.include_router(index.router, prefix="/index", tags=["Indexing"])
app.include_router(search.router, prefix="/search", tags=["Searching"])
app.include_router(libraries.router, prefix="/libraries", tags=["libraries"])
app.include_router(servicenow.router, prefix="/servicenow", tags=["ServiceNow"])
app.include_router(finance.router, prefix="/finance", tags=["Finance Hybrid"])

# 5. Main execution block
if __name__ == '__main__':
    # Note the path to the app object: "src.main:app"
    uvicorn.run("src.main:app", host="0.0.0.0", port=8079, reload=False)