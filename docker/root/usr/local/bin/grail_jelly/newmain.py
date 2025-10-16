from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')

# all computed constants + stop event
from base.constants import * 

# logger
from base import logger_setup
logger = logger_setup.log_setup()
# other modules will get the same logger instance by calling logging.getLogger("jellygrail") via "from base import *"

from script_runner import refreshByStep
refresher = refreshByStep()

# jg connect points
import jg_services
# ...
# --- TBC....

# ---- new starlette related ----
import asyncio
from concurrent.futures import ThreadPoolExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def trigger_nfo_refresh():
    refresher.run(start_at=2)

    #call the refresh step scheduler with a given step (nfo_loop_service)

def trigger_rd_progress():
    if jg_services.rd_progress == "PLEASE_SCAN":
        refresher.run(start_at=0)  
    

async def periodic_job_launcher(func, interval: int, stop_event: threading.Event):
    loop = asyncio.get_running_loop()
    while not stop_event.is_set():
        # Lance ton job bloquant
        try:
            await loop.run_in_executor(None, func)
        except Exception as e:
            logger.error(f" SCHEDULER| ❌ In job run by {func.__name__} : {e}")

        # Attente périodique (6 min) interrompable
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, stop_event.wait),
                interval
            )
        except asyncio.TimeoutError:
            continue
        else:
            break

'''
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
'''

# === Routes Starlette ===
async def homepage(request):
    return JSONResponse({"status": "ok", "active_jobs": len(request.app.state.tasks)})

routes = [
    Route("/", homepage),
]

app = Starlette(routes=routes)

# === État global pour suivre les tâches et l’événement d’arrêt ===
app.state.stop_event = stopEvent
app.state.tasks = []

# === Startup hook ===
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 JellyGrail launched")

    stop_event = app.state.stop_event
    app.state.tasks = [
        asyncio.create_task(periodic_job_launcher(trigger_rd_progress, 5, stop_event)),
    ]

# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 JellyGrail shutdown requested")
    stop_event = app.state.stop_event
    stop_event.set()

    # Attendre la fin propre des tâches
    await asyncio.gather(*app.state.tasks, return_exceptions=True)
    logger.info("🔁 Periodic triggers stopped.")

# === Launching the app with Uvicorn ===
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="uvloop")
    #asyncio.run(server.serve())
