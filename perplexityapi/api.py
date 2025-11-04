from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from starlette.responses import RedirectResponse

from perplexityapi.container.default_container import DefaultContainer


# Creazione dell'istanza dell'applicazione FastAPI
app = FastAPI(
    title="API",
    description="API per la gestione",
    version="1.0.0"
)

default_container: DefaultContainer = DefaultContainer.getInstance()

# Istanziamo il controller tramite il container di dipendenze
# first_controller = default_container.get(FirstController)
# Includiamo il router del controller nell'app
# app.include_router(first_controller.router)

# Configurazione CORS per consentire richieste da altre origini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione, specificare le origini consentite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint di base
@app.get("/", include_in_schema=False)
async def root():
    # redirect to /docs
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

# Per eseguire il server direttamente quando si esegue questo file
if __name__ == "__main__":
    uvicorn.run(
        "perplexityapi.api:app",  # Percorso completo del modulo
        host=default_container.get_var("api_host"),
        port=default_container.get_var("api_port"),
        reload=True
    )