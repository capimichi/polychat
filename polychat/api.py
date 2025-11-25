from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from starlette.responses import RedirectResponse

from polychat.container.default_container import DefaultContainer
from polychat.controller.deepseek_controller import DeepseekController
from polychat.controller.kimi_controller import KimiController
from polychat.controller.perplexity_controller import PerplexityController
from polychat.controller.chat_gpt_controller import ChatGptController


# Creazione dell'istanza dell'applicazione FastAPI
app = FastAPI(
    title="API",
    description="API per la gestione",
    version="1.0.0"
)

default_container: DefaultContainer = DefaultContainer.getInstance()

# Istanziamo i controller tramite il container di dipendenze
perplexity_chat_controller: PerplexityController = default_container.get(PerplexityController)
kimi_chat_controller: KimiController = default_container.get(KimiController)
deepseek_chat_controller: DeepseekController = default_container.get(DeepseekController)
chatgpt_chat_controller: ChatGptController = default_container.get(ChatGptController)

# Includiamo i router dei controller nell'app
app.include_router(perplexity_chat_controller.router)
app.include_router(kimi_chat_controller.router)
app.include_router(deepseek_chat_controller.router)
app.include_router(chatgpt_chat_controller.router)

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
        "polychat.api:app",  # Percorso completo del modulo
        host=default_container.get_var("api_host"),
        port=default_container.get_var("api_port"),
        reload=False
    )
