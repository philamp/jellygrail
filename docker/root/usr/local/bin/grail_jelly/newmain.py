from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')
from base.constants import *

# setup the logger once
from base import logger_setup
logger = logger_setup.log_setup()


import time
# --- TBC....

# ---- new starlette related ----
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

'''
# === Configuration du logger ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jobs")
'''

# === Exécuteur pour les tâches CPU ===
executor = ThreadPoolExecutor(max_workers=3)

# === Exemple de jobs lourds ===
def heavy_job_a():
    logger.info("[A] Calcul d’un rapport…")
    time.sleep(2)
    return "[A] Rapport terminé"

def heavy_job_b():
    logger.info("[B] Compression de fichiers…")
    time.sleep(3)
    return "[B] Compression terminée"

def heavy_job_c():
    logger.info("[C] Analyse de logs système…")
    time.sleep(1.5)
    return "[C] Analyse terminée"

# === Worker générique ===
async def worker(name, interval, func, stop_event: asyncio.Event):
    loop = asyncio.get_running_loop()
    while not stop_event.is_set():
        try:
            result = await loop.run_in_executor(None, func)
            print(f"{name}: {result}")
        except Exception as e:
            print(f"{name}: erreur {e}")

        # Attente du prochain cycle, mais annulable si stop_event est déclenché
        sleep_task = asyncio.create_task(asyncio.sleep(interval))
        stop_task = asyncio.create_task(stop_event.wait())
        done, pending = await asyncio.wait(
            {sleep_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED
        )

        # On annule la tâche restante pour éviter les warnings
        for t in pending:
            t.cancel()

# === Routes Starlette ===
async def homepage(request):
    return JSONResponse({"status": "ok", "active_jobs": len(request.app.state.tasks)})

routes = [
    Route("/", homepage),
]

app = Starlette(routes=routes)

# === État global pour suivre les tâches et l’événement d’arrêt ===
app.state.stop_event = asyncio.Event()
app.state.tasks = []

# === Startup hook ===
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Démarrage du serveur Starlette et des jobs périodiques")

    stop_event = app.state.stop_event
    app.state.tasks = [
        asyncio.create_task(worker("A", 5, heavy_job_a, stop_event)),
        asyncio.create_task(worker("B", 10, heavy_job_b, stop_event)),
        asyncio.create_task(worker("C", 15, heavy_job_c, stop_event)),
    ]

# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Arrêt du serveur demandé. Signal aux workers…")
    stop_event = app.state.stop_event
    stop_event.set()

    # Attendre la fin propre des tâches
    await asyncio.gather(*app.state.tasks, return_exceptions=True)
    logger.info("✅ Tous les workers ont été arrêtés proprement.")



# === Launching the app with Uvicorn ===
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio")
    #asyncio.run(server.serve())
