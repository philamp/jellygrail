### MAIN ONLY
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')
from base import logger_setup
logger = logger_setup.log_setup() # other modules will get the same logger instance by calling logging.getLogger("jellygrail") via "from base import *"
from base.splashandchecks import play_config_check, play_splash
### ---------

# CONSTANTS EVERYWHERE + stop event
from base.constants import *

# LIBS
import asyncio
from concurrent.futures import ThreadPoolExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import time


# JG MODULES
import jg_services
import nfo_generator
import jfapi
from jgscan import multiScan




# JG REFRESHER in main
#from script_runner import refreshByStep
from base.jobmanager import JobManager



'''
def trigger_nfo_refresh():
    return refreshByStep.run(steps_to_run=[3,5,6])

    #call the refresh step scheduler with a given step (nfo_loop_service)
'''
    




# TODO maybe deprecated to removve
async def periodic_trigger_launcher(func, interval: int, stop_event: threading.Event):
    loop = asyncio.get_running_loop()
    while not stop_event.is_set():
        # Launch not async job
        try:
            await loop.run_in_executor(None, func)
        except Exception as e:
            logger.error(f" SCHEDULER| ❌ In job run by {func.__name__} : {e}")

        # Pause period or stop, using timeout error raise as a continue tool
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
    return JSONResponse({"status": "ok", "registered_jobs": len(request.app.state.tasks)})

routes = [
    Route("/", homepage),
]

app = Starlette(routes=routes)

# === État global pour suivre les tâches et l’événement d’arrêt ===
#app.state.tasks = []

# === Startup hook ===
@app.on_event("startup")
async def startup_event():
    #logger.info("🚀 JellyGrail launched")
    
    play_config_check()
    play_splash()
    # START ALL TRIGGERED/PERIODIC JOBS
    asyncio.create_task(JobManager.run_all())

    #stop_event = app.state.stop_event
    #app.state.tasks = [
    #    asyncio.create_task(periodic_trigger_launcher(trigger_rd_progress, 120, stop_event)),
    #]

# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    #logger.info("🛑 JellyGrail shutdown requested")
    #stop_event = app.state.stop_event
    #stop_event.set()
    # STOP ALL TRIGGERED/PERIODIC JOBS
    JobManager.stop()
    # Attendre la fin propre des tâches
    #await asyncio.gather(*app.state.tasks, return_exceptions=True)

async def SSDPTask(ctx, stop):
    # ctx not used, would be elegant to put sock in ctx and to use integrated timeout handling in jobmanager
    
    # testablée with nc -ul 
    pause = 5

    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)  # <-- important

    #       0    1         2        3                          4                                  5                      6
    msg = f"JGx|{VERSION}|{LAN_IP}|{WEBSERVICE_INTERNAL_PORT}|{KODI_MYSQL_CONFIG.get('port', 0)}|{WEBDAV_INTERNAL_PORT}|{SSDP_TOKEN}"

    logger.info(f"      SSDP| Broadcasting (every {pause}secs) this SSDP msg: {msg} ")
    try:
        while not stop.is_set():
            await loop.sock_sendto(sock, msg.encode("ascii"), ("<broadcast>", SSDP_PORT))
            try:
                await asyncio.wait_for(stop.wait(), timeout=pause)
            except asyncio.TimeoutError:
                pass
    finally:
        sock.close()
        logger.info("      SSDP| Broadcast socket closed.")

def trigger_rd_progress(ctx, stop):
    if jg_services.rd_progress != "PLEASE_SCAN":
        wf_id = JobManager.get_new_wfid()
        JobManager.trigger("jgScanJob", wf_id, ctx={"wf_id": wf_id}) # the first job that inits the wf id

def multiScanWrapper(ctx, stop):
    # run the job and take total
    nbitems = multiScan(stop)
    if nbitems == 0 and ctx["wf_id"] != "wf-1":
        logger.info("JOBMANAGER| No items to scan.")
        return
        
    ctx["later"] = True if nbitems > INCR_KODI_REFR_MAX else False
        
    JobManager.trigger("jfScan", ctx["wf_id"])
    JobManager.trigger("plexScan", ctx["wf_id"])
    JobManager.trigger("kodiScanNow", ctx["wf_id"]) # and inside it is depending on later or not

def lib_refresh_allWrapper(ctx, stop):
    jfapi.lib_refresh_all(stop)
    JobManager.trigger("nfoGenJob", ctx["wf_id"])

def nfo_generatorWrapper(ctx, stop):
    nfo_generator.nfo_loop_service(stop)
    JobManager.trigger("kodiScanLater", ctx["wf_id"])


if __name__ == "__main__":
    

    # periodic jobs started in main
    # check that each one supports stop event
    JobManager.register_job("rdProgressLoop", trigger_rd_progress, is_sync=True, interval=15)

    # triggered jobs
    # check that each one supports stop event
    JobManager.register_job("jgScanJob", multiScanWrapper, is_sync=True)
    JobManager.register_job("jfScan", lib_refresh_allWrapper, is_sync=True, cond=JF_WANTED_ACTUALLY)
    #JobManager.register_job("plexScan", plexScanWrapper, is_sync=True)
    #JobManager.register_job("kodiScanNow", kodiScanWrapper, is_sync=True)
    JobManager.register_job("nfoGenJob", nfo_generatorWrapper, is_sync=True, cond=(USE_KODI_ACTUALLY and JF_WANTED_ACTUALLY))
    #JobManager.register_job("kodiScanLater", kodiScanWrapper, is_sync=True)


    # HTTP Server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio") #careful, loop.sock_sento is not implemented in uvloop
    #asyncio.run(server.serve())
