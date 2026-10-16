import os
from contextlib import asynccontextmanager

import utils
from fastapi import FastAPI
from fastapi import Query
from fastapi import Response
from fastapi.responses import JSONResponse
from log import getLogger
from models import DataMountModel
from template_policy import is_template_allowed
from values import base_mount_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    await utils.init_mounts()
    yield

    mount_paths = list(utils.get_mounts().keys())
    for path in mount_paths:
        await utils.unmount(path, force=True)


app = FastAPI(lifespan=lifespan)

log = getLogger()


@app.post("/")
async def post(item: DataMountModel):
    item.options.external = False
    if not is_template_allowed(
        item.options.template, os.environ.get("JUPYTERLAB_DATA_MOUNT_TEMPLATES")
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": f"Mount template '{item.options.template}' is not allowed"},
        )
    try:
        utils.validate(item)
    except Exception as e:
        log.exception("Validation failed")
        return JSONResponse(status_code=400, content={"detail": str(e)})
    async with utils.get_lock():
        if item.path in utils.get_mounts():
            log.warning(f"{item.path} already mounted")
            return JSONResponse(
                status_code=400, content={"detail": f"{item.path} already mounted"}
            )
    try:
        async with utils.get_lock():
            success, error_process = await utils.mount(item)
        if success:
            return Response(status_code=204)
        else:
            return JSONResponse(status_code=400, content=error_process)
    except Exception as e:
        log.exception(f"Mount {item.path} failed")
        fullpath = os.path.join(base_mount_dir, item.path)
        try:
            await utils.unmount(item.path, force=True)
        except:
            log.exception("After mount failed the attempt to unmount it threw an exception as well")
            pass
        err = str(e).replace(fullpath, item.path)
        return JSONResponse(status_code=400, content={"detail": err})


@app.get("/")
async def get():
    async with utils.get_lock():
        models = []
        for path, entry in utils.get_mounts().items():
            options = entry["model"].get("options", {})
            if entry["model"].get("options", {}).get("external", False):
                options["config"] = {}
            models.append({"path": path, "options": options})
        return JSONResponse(content=models)


@app.delete("/{path:path}")
async def delete(path: str, force: bool = Query(True)):
    try:
        async with utils.get_lock():
            mount = utils.get_mounts().get(path)
            if mount is None:
                log.debug(f"{path} not found")
                return JSONResponse(
                    status_code=404, content={"detail": "Mount not found"}
                )
            options = mount.get("model", {}).get("options", {})
            if options.get("external", False):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Administrator-provisioned mounts cannot be removed"},
                )
            log.info(f"Unmount {path} ...")
            await utils.unmount(path, force=force)
            log.info(f"Unmount {path} ... successful")
        return Response(status_code=204)
    except Exception as e:
        log.exception(f"Unmount {path} ... failed")
        fullpath = os.path.join(base_mount_dir, path)
        err = str(e).replace(fullpath, path)
        return JSONResponse(status_code=400, content={"detail": err})
