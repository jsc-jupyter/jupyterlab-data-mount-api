import asyncio
import logging

import utils
from fastapi import FastAPI
from fastapi import Response
from fastapi.responses import JSONResponse
from log import getLogger
from models import DataMountModel

mounts = {}
lock = asyncio.Lock()
background_tasks = set()

app = FastAPI()

log = getLogger()


@app.post("/")
async def post(item: DataMountModel):
    global mounts
    try:
        utils.validate(item)
    except Exception as e:
        log.exception("Validation failed")
        return JSONResponse(status_code=400, content={"detail": str(e)})
    async with lock:
        if item.path in mounts:
            log.warning(f"{item.path} already mounted")
            return JSONResponse(
                status_code=400, content={"detail": f"{item.path} already mounted"}
            )
    try:
        async with lock:
            log.info(f"Mount {item.path} ...")
            success, error_process = await utils.mount(item)
            if success:
                log.info(f"Mount {item.path} ... successful")

                # When the process is no longer running
                # we remove it from the mounts dict
                async def done_callback(process, path):
                    await process.wait()
                    async with lock:
                        if path in mounts:
                            del mounts[path]

                task = asyncio.create_task(done_callback(error_process, item.path))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)

                mounts[item.path] = {
                    "process": error_process,
                    "model": item.model_dump(),
                }
            else:
                log.info(
                    f"Mount {item.path} ... failed. Error: {error_process.get('error', 'unknown')}"
                )
        if success:
            return Response(status_code=204)
        else:
            return JSONResponse(status_code=400, content=error_process)
    except Exception as e:
        log.exception(f"Mount {item.path} failed")
        return JSONResponse(status_code=400, content={"detail": str(e)})


@app.get("/")
async def get():
    global mounts
    async with lock:
        models = {path: entry["model"] for path, entry in mounts.items()}
        return JSONResponse(content=models)


@app.delete("/{path}")
async def delete(path: str):
    global mounts
    if path not in mounts:
        log.debug(f"{path} not found")
        return JSONResponse(status_code=404, content={"detail": "Mount not found"})
    try:
        async with lock:
            log.info(f"Unmount {path} ...")
            await utils.unmount(path, mounts[path]["process"])
            log.info(f"Unmount {path} ... successful")
        return Response(status_code=204)
    except Exception as e:
        log.exception(f"Unmount {path} ... failed")
        return JSONResponse(status_code=400, content={"detail": str(e)})
