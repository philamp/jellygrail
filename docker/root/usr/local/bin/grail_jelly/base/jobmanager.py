import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Coroutine, Optional

# JG MODULES
from base import *

class JobManager:
    jobs: dict[str, dict] = {}
    job_order: list[str] = []
    running: bool = True
    executor = ThreadPoolExecutor()
    stop_event = asyncio.Event()          # utilisé dans les coroutines
    stop_flag = threading.Event()         # équivalent pour les jobs sync

    # === Enregistrement ===
    @staticmethod
    def register_job(
        name: str,
        coro: Callable[..., Coroutine] | Callable[..., None],
        *,
        dependencies: Optional[list[str]] = None,
        is_sync: bool = False,
        interval: Optional[float] = None,
    ):
        JobManager.jobs[name] = {
            "name": name,
            "coro": coro,
            "dependencies": dependencies or [],
            "is_sync": is_sync,
            "interval": interval,
            "event": asyncio.Event(),
            "lock": asyncio.Lock(),
        }
        JobManager.job_order.append(name)

    # === Déclenchement ===
    @staticmethod
    def trigger(name: str):
        if name in JobManager.jobs:
            JobManager.jobs[name]["event"].set()

    # === Résolution des dépendances transitives ===
    @staticmethod
    def _resolve_dependencies(name: str, seen=None) -> set[str]:
        if seen is None:
            seen = set()
        for dep in JobManager.jobs[name]["dependencies"]:
            if dep not in seen:
                seen.add(dep)
                seen |= JobManager._resolve_dependencies(dep, seen)
        return seen

    @staticmethod
    def resolve_all_dependencies():
        for name in JobManager.jobs:
            all_deps = JobManager._resolve_dependencies(name)
            JobManager.jobs[name]["dependencies"] = list(all_deps)

    # === Tri dans l'ordre d'enregistrement ===
    @staticmethod
    def _sorted_deps(deps: list[str]) -> list[str]:
        order_map = {n: i for i, n in enumerate(JobManager.job_order)}
        return sorted(deps, key=lambda d: order_map.get(d, 9999))

    # === Récupération du stop flag approprié ===
    @staticmethod
    def get_stop_flag():
        """Retourne une version thread-safe du stop event."""
        return JobManager.stop_flag

    # === Boucle d’exécution des jobs ===
    @staticmethod
    async def _run_job(job: dict):
        name = job["name"]
        event = job["event"]
        lock = job["lock"]
        deps = job["dependencies"]
        coro = job["coro"]
        is_sync = job["is_sync"]
        interval = job["interval"]

        while JobManager.running:
            if interval:
                try:
                    await asyncio.wait_for(event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
            else:
                await event.wait()

            event.clear()
            if JobManager.stop_event.is_set():
                logger.info(f"JOBMANAGER| 🛑 Stop signal received before starting {name}")
                return


            async with lock:
                # attendre les dépendances
                for dep in JobManager._sorted_deps(deps):
                    async with JobManager.jobs[dep]["lock"]:
                        pass

                logger.info(f"JOBMANAGER| ▶ Starting job {name}")
                try:
                    if is_sync:
                        stop_flag = JobManager.get_stop_flag()
                        await asyncio.get_event_loop().run_in_executor(
                            JobManager.executor, coro, stop_flag
                        )
                    else:
                        await coro(JobManager.stop_event)

                    logger.info(f"JOBMANAGER| ✅ Finished job {name}")
                except asyncio.CancelledError:
                    logger.info(f"JOBMANAGER| ⚠ {name} cancelled")
                except Exception as e:
                    logger.info(f"JOBMANAGER| 💥 Exception not catched in job {name}: {type(e).__name__} — {e}")
                    # ici tu pourrais logguer plus proprement avec traceback
                    import traceback
                    traceback.print_exc()


            if JobManager.stop_event.is_set():
                logger.info(f"JOBMANAGER| 🛑 Stop signal detected after {name}")
                break

    # === Lancement global ===
    @staticmethod
    async def run_all():
        JobManager.resolve_all_dependencies()
        await asyncio.gather(*(JobManager._run_job(job) for job in JobManager.jobs.values()), return_exceptions=True)

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
            # si le loop est fermé ou non dispo
            JobManager.stop_event.set()