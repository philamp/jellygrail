### MAIN ONLY
#from ast import arg
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
import requests


# JG MODULES
import jg_services
import nfo_generator
import jfapi
import localimport
from jgscan.jgsql import jellyDB
from jgscan import multiScan
from jgscan.jgsql import staticDB, bdd_install
from jfconfig import jfconfig
from kodi_services.sqlkodi import kodi_mysql_verify
from kodi_services import delta_nfo_refresh_call, get_kodi_instances_by_kodi_version, set_kodi_instance, reset_kodi_instances_refresh, get_kodidb_entry, kodi_marks_will_update, new_send_nfo_to_kodi, new_send_full_nfo_to_kodi, full_nfo_refresh_call, append_batch_to_kodi_instance, new_merge_kodi_versions, getKodiInfo, extract_triplets
#from jg_services import premium_timeleft, test
import jg_services



# JG REFRESHER in main
#from script_runner import refreshByStep
from base.jobmanager import JobManager



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
    delta = True if request.query_params.get("deltamode") == "y" else False

    if not get_kodidb_entry(kdb):
        return JSONResponse({
            "status": 404
        }, status_code=404)
    
    func = new_send_full_nfo_to_kodi if full else new_send_nfo_to_kodi
    func = delta_nfo_refresh_call if delta else func

    
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

    #kdb = request.query_params.get("db") # 
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

async def all_events_ask(request):
    reset_kodi_instances_refresh("toScan")
    reset_kodi_instances_refresh("toNfoRefresh")
    return JSONResponse({
        "status": 201
    }, status_code=201)

async def ask_kodi_refresh(request):
    JobManager.trigger("kodiScan", "manual_refresh_from_api")
    return JSONResponse({
        "status": 201
    }, status_code=201)

async def ask_jf_refresh(request):
    JobManager.trigger("jfScan", "manual_refresh_from_api")
    return JSONResponse({
        "status": 201
    }, status_code=201)

async def askFullNfoRefresh(request):
    kid = request.query_params.get("uid")

    deltamode = True if request.query_params.get("deltamode") == "y" else False

    full_nfo_refresh_call(kid, deltamode=deltamode)

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

    result = {
        "menu": {}
    }

    if mediatype not in ['movie', 'season']:
        result['menu'].update({
            'Error: Please select a movie or a tvshow season': "#NULL",
            '----------': "#NULL"
        })
        

    else:
        result = await asyncio.get_running_loop().run_in_executor(None, localimport.getMenuItems, mediatype, mediaid, uid)
        # return only static menu if no dynamic items
        

    result['menu'].update({
        'Admin actions': '#SUBMENU'
    })
    result['submenu'] = {
        'Trigger full scan': '#FULLSCAN',
        'Trigger full NFO refresh': '#FULLNFOREFRESH',
        'Trigger delta NFO refresh': '#DELTANFOREFRESH',
        'Reset Add-on': '#RESETADDON',
        'Open Add-on settings': '#OPENSETTINGS'
    }

    result['preflang'] = LITPREFLANG


    #logger.info(f"menu data sent to kodi is : {result}")

    return JSONResponse(result, status_code=200)




async def should_refresh(request):
    # long polling call
    db = request.query_params.get("db")

    if not (dbentry := get_kodidb_entry(db)):
        return JSONResponse({
            "nforefresh": False,
            "scan": False,
            "fullNfoRefresh": False,
            "deltaNfoRefresh": False,
            "broken": True
        }, status_code=404)

    tasks = {
        "toNfoRefresh": asyncio.create_task(dbentry["toNfoRefresh"].wait()),
        "toScan": asyncio.create_task(dbentry["toScan"].wait()),
        "toFullNfoRefresh": asyncio.create_task(dbentry["toFullNfoRefresh"].wait()),
        "toDeltaNfoRefresh": asyncio.create_task(dbentry["toDeltaNfoRefresh"].wait())
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
        #logger.info("API       | should_refresh timeout, no event fired.")
        for t in pending:
            t.cancel()
        return JSONResponse({
            "nforefresh": False,
            "scan": False,
            "fullNfoRefresh": False,
            "deltaNfoRefresh": False,
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

            logger.info(f"API       | should_refresh event fired: {name} for db {db}")

            dbentry[name].clear() # mark it done even before it's called by client, easier this way and no real issue unless kodi client stops scanning

            # it breaks so the other event is not checked, perfectly fine
            return JSONResponse({
                "nforefresh": name == "toNfoRefresh",
                "scan": name == "toScan",
                "fullNfoRefresh": name == "toFullNfoRefresh",
                "deltaNfoRefresh": name == "toDeltaNfoRefresh",
                "broken": False
            }, status_code=201)

    # (should never happen)
    return JSONResponse({
        "nforefresh": False,
        "scan": False,
        "fullNfoRefresh": False,
        "deltaNfoRefresh": False,
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

async def setPolicyRoute(request):
    data = await request.json()
    Qpolicy = data.get("Qpolicy", 1)
    Lpolicy = data.get("Lpolicy", 1)

    if parentPaths := data.get("parentPaths", []):
        if await asyncio.get_running_loop().run_in_executor(None, localimport.setPolicy, parentPaths, Qpolicy, Lpolicy):
            return JSONResponse({
                "status": 201
            }, status_code=201)



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
    Route("/trigger_delta_nfo_refresh", askFullNfoRefresh),
    Route("/set_consumed", setConsumed),
    Route("/ask_kodi_refresh", ask_kodi_refresh),
    Route("/get_cmenu_for/{mediatype:str}/{mediaid:int}", getContextMenu),
    Route("/special_ops", doSqlStuffRoute),
    Route("/set_policy", setPolicyRoute, methods=["POST"])
)

# no / route here to let the user put a proxy in front of this and the webdav server # TODO remove bypass below to enable
app = Starlette(
    routes=[
            Route("/getrdincrement/{arg:int}", rdIncrRoute)
        ]
)
app.mount("/api", api_routes) # tokenized paths
#public paths:
app.mount("/app", Router(
    routes=[
        Route("/health", homepage),
        Route("/ask_kodi_refresh", ask_kodi_refresh),
        Route("/testallevents", all_events_ask),
        Route("/ask_jf_refresh", ask_jf_refresh),
        Route("/test", rd_test_api),
        Route("/getrdincrement/{arg:int}", rdIncrRoute)
    ]
))

# toimprove
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
    
    genericClass.stopImport()
    JobManager.stop()
    staticDB.s.sqclose()



async def kodiScanWrapper(ctx, stop):
    reset_kodi_instances_refresh("toScan")


def remoteScanWrapper(ctx, stop):
    # run jgservices.remoteScan
    jg_services.remoteScan(stop)

def computePoliciesWrapper(ctx, stop):
    # run jgservices.remoteScan
    localimport.computePolicies()

def plexScanWrapper(ctx, stop):
    for plex_url in PLEX_URLS_ARRAY:
        if stop.is_set():
            logger.warning("JOBMANAGER| plexScan interrupted by stop signal")
            return

        if not plex_url:
            continue

        try:
            response = requests.get(plex_url, timeout=10)
            if response.ok:
                logger.info(f"JOBMANAGER| Plex scan trigger called: {plex_url}")
            else:
                logger.warning(f"JOBMANAGER| Plex scan trigger returned HTTP {response.status_code}: {plex_url}")
        except Exception as e:
            logger.error(f"JOBMANAGER| Plex scan trigger failed for {plex_url}: {e}")


def trigger_rd_progress(ctx, stop):
    wfid = JobManager.get_new_wfid()
    if jg_services.rd_progress() == "PLEASE_SCAN" or wfid == "wf1":
        JobManager.trigger("jgScanJob", wfid, ctx={"wfid": wfid, "later": False}) # the first job of the WF marks the wfid


def multiScanWrapper(ctx, stop):
    # run the job and take total
    nbitems = multiScan(stop)
    if nbitems == 0 and ctx["wfid"] != "wf1":
        logger.info("JOBMANAGER| No items to scan.")
        return
    
    #else----
    
    if ctx["wfid"] == "wf1":
        logger.info("JOBMANAGER| First workflow triggers the scan")

    JobManager.trigger("computePolicies", ctx["wfid"])

    ctx["later"] = True if nbitems > INCR_KODI_REFR_MAX else False
        
    JobManager.trigger("jfScan", ctx["wfid"])
    JobManager.trigger("plexScan", ctx["wfid"])
    if not ctx["later"]:
        JobManager.trigger("kodiScan", ctx["wfid"])

def lib_refresh_allWrapper(ctx, stop):
    jfapi.lib_refresh_all(stop)
    JobManager.trigger("nfoGenJob", ctx["wfid"])

def importUncompletedWrapper(ctx, stop):
    localimport.importUncompleted(stop)



def nfo_generatorWrapper(ctx, stop):
    willNfoRefresh = False
    firsttime = False

    if ctx.get("wfid", "") == "wf1" or ctx.get("wfid", "") == "twf-nfoGenJob-1":
        logger.info("JOBMANAGER| First workflow or scheduled wf triggers the nfoGen")
        firsttime = True
        
    if nfo_generator.nfo_loop_service(stop) or firsttime:
        willNfoRefresh = True

    #only called if ctx has later (launched from a scan job) ctx is always a dict here
    if ctx.get("later", False):
        JobManager.trigger("kodiScan", ctx["wfid"])

    time.sleep(0.5)
    if willNfoRefresh:
        
        reset_kodi_instances_refresh("toNfoRefresh")
        time.sleep(0.1)



if __name__ == "__main__":

    bdd_install()
    staticDB.sinit()

    # ---------------periodic jobs launched once in startup event
    JobManager.register_job("rdProgressLoop", trigger_rd_progress, is_sync=True, interval=15)
    JobManager.register_job("ssdpBroadcast", SSDPTask, is_sync=False) #ASYNC !


    # ----------------triggered jobs launched on cascade on event
    JobManager.register_job("jgScanJob", multiScanWrapper, is_sync=True)
    #JobManager.register_job("restartApp", restartAppWrapper, is_sync=True)
    JobManager.register_job("jfScan", lib_refresh_allWrapper, is_sync=True, cond=JF_WANTED_ACTUALLY)
    JobManager.register_job("plexScan", plexScanWrapper, is_sync=True, cond=USE_PLEX_ACTUALLY)
    JobManager.register_job("kodiScan", kodiScanWrapper, is_sync=False)
    # WARNING, nfoGenJob and jfscan must be registered AFTER jgscanjob because of the shared lock, if not they will never run because they will wait for a lock that is never released since jgScanJob is not registered
    JobManager.register_job("nfoGenJob", nfo_generatorWrapper, is_sync=True, cond=(USE_KODI_ACTUALLY and JF_WANTED_ACTUALLY), interval=20)
    JobManager.register_job("remoteScan", remoteScanWrapper, is_sync=True, cond=USE_REMOTE_RDUMP_ACTUALLY, interval=60)
    JobManager.register_job("computePolicies", computePoliciesWrapper, is_sync=True, interval=750)
    JobManager.register_job("importMedias", importUncompletedWrapper, is_sync=True, interval=1600)
    #JobManager.register_job("weeklyStopOnWednesday", weeklyStopOnWednesdayWrapper, is_sync=True, interval=20)


    # UNIX sockets thread using uvloop
    t = threading.Thread(target=start_uvloop_thread, name="uvloop-thread", daemon=True)
    t.start()

    # HTTP Server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEBSERVICE_INTERNAL_PORT, loop="asyncio", access_log=False) #careful, loop.sock_sento is not implemented in uvloop
    #asyncio.run(server.serve())

    staticDB.s.sqclose()
