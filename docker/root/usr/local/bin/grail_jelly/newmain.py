### MAIN ONLY
from ast import arg
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
from starlette.responses import HTMLResponse
from starlette.routing import Route, Router
from starlette.middleware.base import BaseHTTPMiddleware
import time
import threading
import re


# JG MODULES
import jg_services
import nfo_generator
import jfapi
from jgscan.jgsql import jellyDB
from jgscan import multiScan
from jgscan.jgsql import staticDB, bdd_install
from jfconfig import jfconfig
from kodi_services.sqlkodi import kodi_mysql_verify
from kodi_services import get_kodi_instances_by_kodi_version, set_kodi_instance, reset_kodi_instances_refresh, get_kodidb_entry, kodi_marks_will_update, new_send_nfo_to_kodi, new_send_full_nfo_to_kodi, full_nfo_refresh_call, append_batch_to_kodi_instance, new_merge_kodi_versions, getKodiInfo
#from jg_services import premium_timeleft, test
import jg_services



# JG REFRESHER in main
#from script_runner import refreshByStep
from base.jobmanager import JobManager



'''
def trigger_nfo_refresh():
    return refreshByStep.run(steps_to_run=[3,5,6])

    #call the refresh step scheduler with a given step (nfo_loop_service)

    

# TODO maybe deprecated to removve
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





class QuietRouteMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, ignored_paths):
        super().__init__(app)
        self.ignored_paths = set(ignored_paths)

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if request.url.path not in self.ignored_paths:
            # This is a normal logger, uses normal formatter, no special args shape
            logger.info(f"HTTPSERVER| {MAGENTA}{request.method}| {request.url.path}?{request.url.query}| {response.status_code}{RESET}")

        return response



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


async def gimmeNfos(request):
    kdb = request.query_params.get("db")
    kid = request.query_params.get("uid")
    full = True if request.query_params.get("full") == "y" else False

    if not get_kodidb_entry(kdb):
        return JSONResponse({
            "status": 404
        }, status_code=404)
    
    func = new_send_full_nfo_to_kodi if full else new_send_nfo_to_kodi

    # call new_send_nfo_batch in a thread
    result = await asyncio.get_running_loop().run_in_executor(None, func, kid, kdb)

    if result == {}:
        return JSONResponse({
            "status": 404
        }, status_code=404)
    
    #else
    return JSONResponse({
        "payload": result,
        "status": 201
    }, status_code=201)

async def setConsumed(request):

    #kdb = request.query_params.get("db") # TODO later use to get all kodi instances for this db
    kid = request.query_params.get("uid")
    batchid = request.query_params.get("batchid")

    if not append_batch_to_kodi_instance(kid, batchid):
        return JSONResponse({
            "status": 404
        }, status_code=404)
    # else
    return JSONResponse({
        "status": 201
    }, status_code=201)

async def ask_kodi_refresh(request):
    JobManager.trigger("kodiScan", "manual_refresh_from_api")
    return JSONResponse({
        "status": 201
    }, status_code=201)

async def askFullNfoRefresh(request):
    kid = request.query_params.get("uid")

    full_nfo_refresh_call(kid)

    return JSONResponse({
        "status": 201
    }, status_code=201)
    

async def rd_test_api(request):
    result = await asyncio.get_running_loop().run_in_executor(None, jg_services.test)
    return HTMLResponse(result)

async def rdIncrRoute(request):
    arg = request.path_params["arg"]
    if not (result := await asyncio.get_running_loop().run_in_executor(None, jg_services.getrdincrement, arg)):
        return JSONResponse({"status": 503}, status_code=503)
    #else
    return JSONResponse(result, status_code=200)

async def getContextMenu(request):
    mediaid = int(request.path_params["mediaid"])
    mediatype = request.path_params["mediatype"]
    uid = request.query_params.get("uid")

    local_prefLangPresent = False
    remote_prefLangPresent = False

    ctMenu = {}

    if not (result := await asyncio.get_running_loop().run_in_executor(None, getKodiInfo, uid, mediaid, mediatype)):
        return JSONResponse({"status": 404}, status_code=404)
    #else
    # RETURN a metadata menu used in kodi context menu with all actions provided:
    # - keep locally with url /keep_local?token=XXX&uid=YYY&mediatype=ZZZ&mediaid=NNN
    # - remove locally with url /remove_local?token=XXX&uid=YYY&mediatype=ZZZ&mediaid=NNN

    # find the actual_path in sqlite result
    jgDB = jellyDB()

    for item in result:
        vpath = item.get("virtualPath", "")
        vfn = item.get("virtualFilename", "")
        for (actual_path,) in jgDB.get_path_actual(vpath):
            if "remote" not in actual_path.split("/", 2)[2]:
                # construct menu actions based on actual_path
                
                # if find INTERESTED_LANGUAGES is present str values in [] and {} in the filename:
                # use regexp to extract them from filename

                if USED_LANGS_JF[0] in re.findall(r'[A-Z][a-z]{2}', vfn):
                    local_prefLangPresent = True

                    # be sure to compare Fre == Fra etc..

            else:
                if USED_LANGS_JF[0] in re.findall(r'[A-Z][a-z]{2}', vfn):
                    remote_prefLangPresent = True

    jgDB.sqclose()
    
    # return a partial contextual menu for the item provided
    # find data in all mediatype cases

    # construct menu actions based on actual_path


    # add other media entries for generic actions

    ctMenu['Full NFO refresh'] = f'/trigger_full_nfo_refresh'


    return JSONResponse({"status": 404}, status_code=404)

    # movie / tvshow / season / episode




async def should_refresh(request):
    # long polling call
    db = request.query_params.get("db")

    if not (dbentry := get_kodidb_entry(db)):
        return JSONResponse({
            "nforefresh": False,
            "scan": False,
            "fullNfoRefresh": False,
            "broken": True
        }, status_code=404)

    tasks = {
        "toNfoRefresh": asyncio.create_task(dbentry["toNfoRefresh"].wait()),
        "toScan": asyncio.create_task(dbentry["toScan"].wait()),
        "toFullNfoRefresh": asyncio.create_task(dbentry["toFullNfoRefresh"].wait())
    }

    # first completed task waiter
    done, pending = await asyncio.wait(
        tasks.values(),
        return_when=asyncio.FIRST_COMPLETED,
        timeout=14
    )

    # Timeout handling (= no event fired)
    if not done:
        # Annule les tasks restantes
        for t in pending:
            t.cancel()
        return JSONResponse({
            "nforefresh": False,
            "scan": False,
            "fullNfoRefresh": False,
            "broken": False
        }, status_code=200)

    # Clean other waiting tasks
    for t in pending:
        t.cancel()

    # Find the triggered task
    for name, task in tasks.items():
        if task in done:

            if name == "toScan":
                kodi_marks_will_update(request.query_params.get("uid"))

            dbentry[name].clear() # mark it done even before it's called by client, easier this way and no real issue unless kodi client stops scanning

            # it breaks so the other event is not checked, perfectly fine
            return JSONResponse({
                "nforefresh": name == "toNfoRefresh",
                "scan": name == "toScan",
                "fullNfoRefresh": name == "toFullNfoRefresh",
                "broken": False
            }, status_code=201)

    # (should never happen)
    return JSONResponse({
        "nforefresh": False,
        "scan": False,
        "fullNfoRefresh": False,
        "broken": True
    }, status_code=503)

async def doSqlStuffRoute(request):
    # get kdb from query
    kdb = request.query_params.get("db")
    kver = int(request.query_params.get("kodi_version"))
    if not (dbentry := get_kodidb_entry(kdb)):
        return JSONResponse({
            "status": 404
        }, status_code=404)

    # call sync func new_merge_kodi_versions in a thread
    if await asyncio.get_running_loop().run_in_executor(None, new_merge_kodi_versions, kdb, kver):
        return JSONResponse({
            "status": 201
        }, status_code=201)
    else:
        return JSONResponse({
            "status": 200
        }, status_code=200)

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
    Route("/what_should_do", should_refresh),
    Route("/gimme_nfos", gimmeNfos),
    Route("/trigger_full_nfo_refresh", askFullNfoRefresh),
    Route("/set_consumed", setConsumed),
    Route("/get_cmenu_for/{mediatype:str}/{mediaid:int}", getContextMenu),
    Route("/special_ops", doSqlStuffRoute)
)

# no / route here to let the user put a proxy in front of this and the webdav server
app = Starlette(
    routes=[
            Route("/getrdincrementBYPASSTODO/{arg:int}", rdIncrRoute)
        ]
)
app.mount("/api", api_routes) # tokenized paths
#public paths:
app.mount("/app", Router(
    routes=[
        Route("/health", homepage),
        Route("/ask_kodi_refresh", ask_kodi_refresh),
        Route("/test", rd_test_api),
        Route("/getrdincrement/{arg:int}", rdIncrRoute)
    ]
))


app.add_middleware(
    QuietRouteMiddleware,
    ignored_paths=["/apdsfi/speciasdfl_ops"]
)

# === État global pour suivre les tâches et l’événement d’arrêt ===
#app.state.tasks = []

# === Startup hook ===
@app.on_event("startup")
async def startup_event():

    
    
    play_splash()
    play_config_check()
    kodi_mysql_verify(logit = True)
    if RD_API_SET:
        logger.warning(f"REALDEBRID/ Premium days remaining: {str(jg_services.premium_timeleft()/86400)[:4]}")

    if JF_WANTED:
        jfconfig()
            
    # START ALL ROOT TRIGGERED/PERIODIC JOBS
    await asyncio.sleep(0)
    asyncio.create_task(JobManager.run_all())
    await asyncio.sleep(0)
    JobManager.trigger("ssdpBroadcast", "🔁 5s loop in thread") #5s is handled in the job itself not in the jobmanager
    
    #----BELOW DEPRECATED
    #JobManager.trigger("rdProgressLoop", "null") #ticker handled by jobmanager periodic also set the job not to print the start message each time
    #JobManager.trigger("nfoGenJob", "null", ctx={"wfid": "null"})
    #JobManager.trigger("remoteScan", "null")
    #-----

# === Stopping hook ===
@app.on_event("shutdown")
async def shutdown_event():
    
    JobManager.stop()
    staticDB.s.sqclose()



async def kodiScanWrapper(ctx, stop):
    reset_kodi_instances_refresh("toScan")


def remoteScanWrapper(ctx, stop):
    # run jgservices.remoteScan
    jg_services.remoteScan(stop)

def trigger_rd_progress(ctx, stop):
    if jg_services.rd_progress() == "PLEASE_SCAN_TODO": # or ctx["wfid"] == "wf1"  #TODO remove 1==1
        wfid = JobManager.get_new_wfid()
        JobManager.trigger("jgScanJob", wfid, ctx={"wfid": wfid, "later": False}) # the first job of the WF marks the wfid

    #else: #TODO temp toremove
    #    JobManager.trigger("kodiScan", ctx["wfid"])


def multiScanWrapper(ctx, stop):
    # run the job and take total
    nbitems = multiScan(stop)
    if nbitems == 0 and ctx["wfid"] != "wf1":
        logger.info("JOBMANAGER| No items to scan.")
        return
    
    if ctx["wfid"] == "wf1":
        logger.info("JOBMANAGER| First workflow triggers the scan")

    ctx["later"] = True if nbitems > INCR_KODI_REFR_MAX else False
        
    JobManager.trigger("jfScan", ctx["wfid"])
    #JobManager.trigger("plexScan", ctx["wfid"]) 
    if not ctx["later"]:
        JobManager.trigger("kodiScan", ctx["wfid"])

def lib_refresh_allWrapper(ctx, stop):
    jfapi.lib_refresh_all(stop)
    JobManager.trigger("nfoGenJob", ctx["wfid"])

def nfo_generatorWrapper(ctx, stop):
    willNfoRefresh = False
    if nfo_generator.nfo_loop_service(stop) or ctx.get("wfid", "") == "wf1" or ctx.get("wfid", "") == "twf-nfoGenJob-1":
        willNfoRefresh = True

        logger.info("JOBMANAGER| First workflow or scheduled wf triggers the nfoGen")


    #only called if ctx has later (launched from a scan job) ctx is always a dict here
    if ctx.get("later", False):
        JobManager.trigger("kodiScan", ctx["wfid"])

    time.sleep(0.5)
    if willNfoRefresh:
        
        reset_kodi_instances_refresh("toNfoRefresh")
        time.sleep(0.1)

    # send nfos TODO
    # nfo gen knows wether there is work to do or not, but let the event consumption do it

    



if __name__ == "__main__":

    bdd_install()
    staticDB.sinit()
    # ---------------periodic jobs launched once in startup event
    # !!!!!!!!!!!!!!!!!! check that each one supports stop event !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    JobManager.register_job("rdProgressLoop", trigger_rd_progress, is_sync=True, interval=11)
    JobManager.register_job("ssdpBroadcast", SSDPTask, is_sync=False) #ASYNC !


    # ----------------triggered jobs launched on cascade on event
    # !!!!!!!!!!!!!!!!!! check that each one supports stop event !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    JobManager.register_job("jgScanJob", multiScanWrapper, is_sync=True)
    JobManager.register_job("jfScan", lib_refresh_allWrapper, is_sync=True, cond=JF_WANTED_ACTUALLY)
    #JobManager.register_job("plexScan", plexScanWrapper, is_sync=True)
    JobManager.register_job("kodiScan", kodiScanWrapper, is_sync=False)
    # WARNING, nfoGenJob must be register AFTER jfScan
    JobManager.register_job("nfoGenJob", nfo_generatorWrapper, is_sync=True, cond=(USE_KODI_ACTUALLY and JF_WANTED_ACTUALLY), interval=10)
    JobManager.register_job("remoteScan", remoteScanWrapper, is_sync=True, cond=USE_REMOTE_RDUMP_ACTUALLY, interval=60)

    



    
    # UNIX sockets thread using uvloop
    t = threading.Thread(target=start_uvloop_thread, name="uvloop-thread", daemon=True)
    t.start()

    # HTTP Server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio", access_log=False) #careful, loop.sock_sento is not implemented in uvloop
    #asyncio.run(server.serve())

    staticDB.s.sqclose()
