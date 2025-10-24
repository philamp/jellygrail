### MAIN ONLY
from dotenv import load_dotenv
load_dotenv('/jellygrail/config/settings.env')
from base import logger_setup
logger = logger_setup.log_setup() # other modules will get the same logger instance by calling logging.getLogger("jellygrail") via "from base import *"
from base.splashandchecks import play_config_check, play_splash
### ---------

# CONSTANTS EVERYWHERE + stop event
from base.constants import *
from base.SSDPandsockets import SSDPTask, start_uvloop_thread

# LIBS
import asyncio
#from concurrent.futures import ThreadPoolExecutor
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import time


# JG MODULES
import jg_services
import nfo_generator
import jfapi
from jgscan import multiScan
from jgscan.jgsql import jellyDB, staticDB, bdd_install
from jfconfig import jfconfig





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

    
    play_config_check()
    play_splash()

    if JF_WANTED:
        jfconfig()
            
    # START ALL TRIGGERED/PERIODIC JOBS
    asyncio.create_task(JobManager.run_all())
    await asyncio.sleep(0)
    JobManager.trigger("ssdpBroadcast", "🔁 5s included") #5s is handled in the job itself not in the jobmanager
    JobManager.trigger("rdProgressLoop", "periodic") #ticker handled by jobmanager



# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    
    JobManager.stop()
    staticDB.s.sqclose()


def trigger_rd_progress(ctx, stop):
    if jg_services.rd_progress == "PLEASE_SCAN":
        wf_id = JobManager.get_new_wfid()
        JobManager.trigger("jgScanJob", wf_id, ctx={"wf_id": wf_id}) # the first job of the WF marks the wf_id

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

    bdd_install()
    staticDB.sinit()
    # periodic jobs started in main
    # check that each one supports stop event
    JobManager.register_job("rdProgressLoop", trigger_rd_progress, is_sync=True, interval=30)
    JobManager.register_job("ssdpBroadcast", SSDPTask, is_sync=False) #ASYNC !


    # triggered jobs
    # check that each one supports stop event
    JobManager.register_job("jgScanJob", multiScanWrapper, is_sync=True)
    JobManager.register_job("jfScan", lib_refresh_allWrapper, is_sync=True, cond=JF_WANTED_ACTUALLY)
    #JobManager.register_job("plexScan", plexScanWrapper, is_sync=True)
    #JobManager.register_job("kodiScanNow", kodiScanWrapper, is_sync=True)
    JobManager.register_job("nfoGenJob", nfo_generatorWrapper, is_sync=True, cond=(USE_KODI_ACTUALLY and JF_WANTED_ACTUALLY))
    #JobManager.register_job("kodiScanLater", kodiScanWrapper, is_sync=True)


    
    # UNIX sockets thread using uvloop
    t = threading.Thread(target=start_uvloop_thread, name="uvloop-thread", daemon=True)
    t.start()

    # HTTP Server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio") #careful, loop.sock_sento is not implemented in uvloop
    #asyncio.run(server.serve())

    staticDB.s.sqclose()
