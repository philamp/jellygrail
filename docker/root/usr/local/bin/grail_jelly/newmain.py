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
from starlette.routing import Route, Router
import time
import threading


# JG MODULES
import jg_services
import nfo_generator
import jfapi
from jgscan import multiScan
from jgscan.jgsql import staticDB, bdd_install
from jfconfig import jfconfig
from kodi_services.sqlkodi import kodi_mysql_verify
from kodi_services import get_kodi_instances_by_kodi_version, set_kodi_instance, reset_kodi_instances_refresh, get_kodidb_entry
from jg_services import premium_timeleft



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
    return JSONResponse({"status": "ok", "registered_jobs": "BETA"})


async def get_compatible_kodiDBs(request):
    kodi_version = request.query_params.get("kodi_version")
    uid = request.query_params.get("uid")
    if not kodi_version or not uid:
        return JSONResponse({"error": "Missing parameters"}, status_code=400)

    return JSONResponse(get_kodi_instances_by_kodi_version(int(kodi_version), uid), status_code=201)

async def create_or_update_kodi_instance(request):

    choice = request.query_params.get("choice")

    if set_kodi_instance(request.query_params.get("uid"), choice, request.query_params.get("ip"), int(request.query_params.get("kodi_version"))):
        
        if kodi_mysql_verify(str=choice):
            return JSONResponse({"status": 201}, status_code=201) #db is here
        else:
            return JSONResponse({"status": 200}, status_code=200) #db not here yet




# ------------ TOKEN HANDLING -----------------
async def verify_token(request):
    token = request.query_params.get("token")
    if token != SSDP_TOKEN:
        return JSONResponse({"error": "Invalid token"}, status_code=401)
    return None

def tokenize(*routes):
    
    wrapped_routes = []
    
    def make_wrapped(original):
        async def wrapped(request, *args, **kwargs):
            error = await verify_token(request)
            if error:
                return error
            return await original(request, *args, **kwargs)
        return wrapped

    for route in routes:
        wrapped_endpoint = make_wrapped(route.endpoint)
        wrapped_routes.append(Route(route.path, wrapped_endpoint, methods=route.methods, name=route.name))

    return Router(routes=wrapped_routes)


api_routes = tokenize(
    Route("/health", homepage),
    Route("/get_compatible_kodiDBs", get_compatible_kodiDBs),
    Route("/set_db_for_this_kodi", create_or_update_kodi_instance),
    Route("/what_should_do", should_refresh)
)

# no / route here to let the user put a proxy in front of this and the webdav server
app = Starlette()
app.mount("/api", api_routes) # tokenized paths
#public paths:
app.mount("/app", Router(
    routes=[
        Route("/health", homepage)
    ]
))

# === État global pour suivre les tâches et l’événement d’arrêt ===
#app.state.tasks = []

# === Startup hook ===
@app.on_event("startup")
async def startup_event():

    
    
    play_splash()
    play_config_check()
    kodi_mysql_verify(logit = True)
    if RD_API_SET:
        logger.warning(f"REALDEBRID/ Premium days remaining: {str(premium_timeleft()/86400)[:4]}")

    if JF_WANTED:
        jfconfig()
            
    # START ALL ROOT TRIGGERED/PERIODIC JOBS
    asyncio.create_task(JobManager.run_all())
    await asyncio.sleep(0)
    JobManager.trigger("ssdpBroadcast", "🔁 5s, in thread, silent") #5s is handled in the job itself not in the jobmanager
    JobManager.trigger("rdProgressLoop", "periodic_rdProgressLoop") #ticker handled by jobmanager periodic also set the job not to print the start message each time



# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    
    JobManager.stop()
    staticDB.s.sqclose()


async def should_refresh(request):
    # long polling call
    db = request.query_params.get("db")

    if dbentry := get_kodidb_entry(db):

        event = dbentry["toRefresh"]

        try:
            # Attend un signal ou timeout de 30s
            await asyncio.wait_for(event.wait(), timeout=30)
            event.clear()  # Reset pour la prochaine fois
            return JSONResponse({"refresh": True, "broken": False})
        except asyncio.TimeoutError:
            return JSONResponse({"refresh": False, "broken": False})
        
    else:
        return JSONResponse({"refresh": False, "broken": True}) # should not happen unless DB is deleted externally db is verified at choice

async def kodiScanWrapper(ctx, stop):
    reset_kodi_instances_refresh()


def trigger_rd_progress(ctx, stop):
    if 1 == 0 and jg_services.rd_progress() == "PLEASE_SCAN": #TODO remove
        wf_id = JobManager.get_new_wfid()
        JobManager.trigger("jgScanJob", wf_id, ctx={"wf_id": wf_id, "later": False}) # the first job of the WF marks the wf_id

def multiScanWrapper(ctx, stop):
    # run the job and take total
    nbitems = multiScan(stop)
    if nbitems == 0 and ctx["wf_id"] != "wf-1":
        logger.info("JOBMANAGER| No items to scan.")
        return
        
    ctx["later"] = True if nbitems > INCR_KODI_REFR_MAX else False
        
    JobManager.trigger("jfScan", ctx["wf_id"])
    JobManager.trigger("plexScan", ctx["wf_id"])
    if not ctx["later"]:
        JobManager.trigger("kodiScan", ctx["wf_id"])

def lib_refresh_allWrapper(ctx, stop):
    jfapi.lib_refresh_all(stop)
    JobManager.trigger("nfoGenJob", ctx["wf_id"])

def nfo_generatorWrapper(ctx, stop):
    nfo_generator.nfo_loop_service(stop)
    if ctx["later"]:
        JobManager.trigger("kodiScan", ctx["wf_id"])

    # send nfos TODO
    # nfo gen knows wether there is work to do or not, but let the event consumption do it

    



if __name__ == "__main__":

    bdd_install()
    staticDB.sinit()
    # periodic jobs started in main
    # check that each one supports stop event
    JobManager.register_job("rdProgressLoop", trigger_rd_progress, is_sync=True, interval=30)
    JobManager.register_job("ssdpBroadcast", SSDPTask, is_sync=False) #ASYNC !


    # triggered jobs
    
    # !!!!!!!!!!!!!!!!!! check that each one supports stop event !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    JobManager.register_job("jgScanJob", multiScanWrapper, is_sync=True)
    JobManager.register_job("jfScan", lib_refresh_allWrapper, is_sync=True, cond=JF_WANTED_ACTUALLY)
    #JobManager.register_job("plexScan", plexScanWrapper, is_sync=True)
    JobManager.register_job("kodiScan", kodiScanWrapper, is_sync=False)
    JobManager.register_job("nfoGenJob", nfo_generatorWrapper, is_sync=True, cond=(USE_KODI_ACTUALLY and JF_WANTED_ACTUALLY))



    
    # UNIX sockets thread using uvloop
    t = threading.Thread(target=start_uvloop_thread, name="uvloop-thread", daemon=True)
    t.start()

    # HTTP Server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio") #careful, loop.sock_sento is not implemented in uvloop
    #asyncio.run(server.serve())

    staticDB.s.sqclose()
