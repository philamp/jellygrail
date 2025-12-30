import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Coroutine, Optional

# JG BASE LIBS
from base import *

class JobManager:
    main_loop: Optional[asyncio.AbstractEventLoop] = None
    jobs: dict[str, dict] = {}
    job_order: list[str] = []
    running: bool = True
    executor = ThreadPoolExecutor()
    stop_event = asyncio.Event()
    stop_flag = threading.Event()
    wfidincr = 0

    # Nouveau : contexte partagé par wfid
    contexts: dict[str, dict] = {}

    @staticmethod
    def get_new_wfid():
        JobManager.wfidincr += 1
        return f"wf{JobManager.wfidincr}"

    # === Enregistrement ===
    @staticmethod
    def register_job(
        name: str,
        coro: Callable[..., Coroutine] | Callable[..., None],
        *,
        is_sync: bool = False,
        interval: Optional[float] = None,
        cond: bool = True
    ):
        
        if not cond:
            return
        
        # special case for jobs sharing same lock

        JobManager.jobs[name] = {
            "name": name,
            "coro": coro,
            "iter": 0,
            "is_sync": is_sync,
            "interval": interval,
            "event": asyncio.Queue(maxsize=1),     # remplace asyncio.Event pour transporter wfid
            "lock": JobManager.jobs["jfScan"]["lock"] if name == "nfoGenJob" else asyncio.Lock(),       # self-lock uniquement
        }
        JobManager.job_order.append(name)

    # === Déclenchement ===
    @staticmethod
    def trigger(name: str, wfid: str, ctx: Optional[dict] = None):
        """Déclenche un job pour un workflow donné (wfid)."""
        if name not in JobManager.jobs:
            logger.info(f"JOBMANAGER| Job {name} disabled due to configuration")
            return
        # créer ou récupérer le contexte partagé
        if wfid not in JobManager.contexts:
            JobManager.contexts[wfid] = ctx or {"wfid": wfid}
        loop = JobManager.main_loop
        if loop is None:
            raise RuntimeError("JobManager main_loop not initialized")
        loop.call_soon_threadsafe(
            lambda job=JobManager.jobs[name]: (
                job["event"].put_nowait(wfid)
                if not job["event"].full()
                else logger.info(f"JOBMANAGER | event [{name}/{wfid}] redondant, ignored")
            )
        )

    # carefull: when putting a wf-id in the trigger
    # === Boucle d’exécution des jobs ===
    @staticmethod
    async def _run_job(job: dict, wfid = None):
        name = job["name"]
        queue = job["event"]
        lock = job["lock"]
        coro = job["coro"]
        is_sync = job["is_sync"]
        interval = job["interval"]

        while JobManager.running:
            tctx = False
            try:
                # attente d’un wfid ou d’un tick périodique
                if interval:
                    
                    try:
                        wfid = await asyncio.wait_for(queue.get(), timeout=interval)
                    except asyncio.TimeoutError:
                        JobManager.jobs[name]['iter'] = JobManager.jobs[name]['iter']+1
                        tctx = True
                        
                        #wfid = f"twf-{name}-{JobManager.jobs[name]['iter']}"
                        #ctx = {"wfid": f"{wfid}"}
                        pass
                else:
                    wfid = await queue.get()
            except asyncio.CancelledError:
                break

            if JobManager.stop_event.is_set():
                logger.info(f"JOBMANAGER| 🛑 Stop signal before starting {name}")
                return

            async with lock:
                
                if not wfid or tctx:
                    wfid = f"twf-{name}-{JobManager.jobs[name]['iter']}"
                    log_info = f"twf{JobManager.jobs[name]['iter']}|"
                else:
                    log_info = f"{wfid}|"

                ctx = JobManager.contexts.get(wfid, {"wfid": wfid})
                # overwrite or crerate a onthefly context for ticking jobs 

                if is_sync:
                    log_info += " thread|"
                else:
                    log_info += " async|"

                if interval:
                    log_info += f" 🔁{interval}s"

                
                
                logger.info(f"JOBMANAGER| ▶ {name}| {log_info}")
                try:
                    if is_sync:
                        await asyncio.get_event_loop().run_in_executor(
                            JobManager.executor, coro, ctx, JobManager.stop_flag
                        )
                    else:
                        await coro(ctx, JobManager.stop_event)
                    logger.info(f"JOBMANAGER| ✅ {name}| {log_info}")
                except Exception as e:
                    import traceback
                    logger.error(f"JOBMANAGER| 💥 Exception in job {name}: {e}")
                    traceback.print_exc()

            if JobManager.stop_event.is_set():
                logger.info(f"JOBMANAGER| 🛑 Stop detected after {name}")
                break

    # === Lancement global ===
    @staticmethod
    async def run_all():
        JobManager.main_loop = asyncio.get_running_loop()
        await asyncio.gather(
            *(JobManager._run_job(job) for job in JobManager.jobs.values()),
            return_exceptions=True,
        )

    # === Arrêt global ===
    @staticmethod
    def stop():
        logger.info("JOBMANAGER| 🛑 Stopping all jobs...")
        JobManager.running = False
        JobManager.stop_flag.set()
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(JobManager.stop_event.set)
        except RuntimeError:
            JobManager.stop_event.set()
