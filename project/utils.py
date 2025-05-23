import asyncio
import json
import os
import tempfile
import traceback
from copy import deepcopy

import uftp
from log import getLogger
from models import DataMountModel
from values import base_mount_dir
from values import gid
from values import uid

lock = asyncio.Lock()
background_tasks = set()
mounts = {}


def get_lock():
    global lock
    return lock


def get_mounts():
    global mounts
    return mounts


def type_specific_args(item: DataMountModel):
    type_ = item.options.config.get("type", None)
    vendor_ = item.options.config.get("vendor", None)
    url_ = item.options.config.get("url", None)
    if (
        type_ == "webdav"
        and vendor_ == "nextcloud"
        and (url_.endswith("/webdav") or url_.endswith("/webdav/"))
    ):
        return ["--webdav-nextcloud-chunk-size=0"]
    return []


async def obscure(value: str):
    process = await asyncio.create_subprocess_exec(
        *["rclone", "obscure", value],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    stdout = stdout.decode().strip()
    return stdout


def validate(item: DataMountModel):
    if not item.path:
        raise Exception("path not provided")
    if not item.options.template:
        raise Exception("options.template not provided")
    if not item.options.config.get("type", None):
        raise Exception("options.config.type not provided")
    if not item.options.config.get("remotepath", None):
        raise Exception("options.config.remotepath not provided")


def get_cmd(item: DataMountModel, config_path: str):
    template = item.options.template
    path = item.path
    remotepath = item.options.config.get("remotepath", "None")
    fullpath = os.path.join(base_mount_dir, path)
    if not os.path.exists(fullpath):
        os.makedirs(fullpath, exist_ok=True)
        os.chown(fullpath, uid, gid)
    if os.path.isdir(fullpath):
        if os.listdir(fullpath):
            raise Exception(f"Directory {path} is not empty.")
    cmd_args = [
        "--vfs-cache-max-size=10G",
        "--vfs-read-chunk-size=64M",
        "--vfs-cache-mode=writes",
        "--allow-other",
        f"--uid={uid}",
        f"--gid={gid}",
    ]
    cmd = [
        "rclone",
        "mount",
        "--config",
        config_path,
        f"{template}:{remotepath}",
        fullpath,
    ] + cmd_args
    cmd += type_specific_args(item)
    if item.options.readonly:
        cmd += ["--read-only"]
    return cmd


async def create_config(item: DataMountModel):
    skip_keys = {
        "readonly",
        "displayName",
        "remotepath",
    }  # They're used in the command as arguments, not in the config file itself
    config = {
        k: v for k, v in deepcopy(item.options.config).items() if k not in skip_keys
    }

    template = item.options.template

    s = f"[{template}]"
    for key, value in config.items():
        if key.startswith("obscure_"):
            value = await obscure(value)
            key = key[len("obscure_") :]
        s += f"\n{key} = {value}"

    tmpfile = tempfile.NamedTemporaryFile(delete=False, mode="w")
    with tmpfile as f:
        f.write(s)

    return tmpfile.name


async def check_rclone_config(item: DataMountModel, config_path: str):
    """Runs 'rclone lsd' to check if the remote storage is accessible."""
    log = getLogger()
    log.info(f"Check rclone config ...")
    template = item.options.template
    remotepath = item.options.config.get("remotepath", "None")
    cmd = [
        "rclone",
        "lsd",
        "--config",
        config_path,
        f"{template}:{remotepath}",
    ] + type_specific_args(item)
    log.debug(f"Run cmd: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        with open(config_path) as f:
            config_string = f.read()
        log.info(f"Check rclone config ... failed")
        log.info(stderr.decode().strip())
        description = {
            "error": stderr.decode().strip(),
            "message": f"Config not working. Exit Code {process.returncode}",
        }
        if not item.options.external:
            description["config"] = config_string
        return description
    log.info(f"Check rclone config ... successful")


async def run_process(command: list):
    """Run rclone mount command asynchronously."""
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        # Wait up to 1 second to see if process exits immediately
        await asyncio.wait_for(process.wait(), timeout=1.0)
        # Process exited quickly — check the return code
        _, stderr = await process.communicate()
        raise RuntimeError(
            f"Process exited early with code {process.returncode}:\n{stderr.decode().strip()}"
        )
    except asyncio.TimeoutError:
        # Process is still running — treat as successful launch
        return process


def is_directory_usable(path: str) -> bool:
    try:
        return os.path.isdir(path) and os.listdir(path) is not None
    except Exception as e:
        print(f"[Error] Directory '{path}' is not usable: {e}")
        return False


async def mount(item: DataMountModel):
    global mounts
    log = getLogger()
    log.info(f"Mount {item.path} ...")
    validate(item)
    if item.options.template == "uftp":
        cmd = uftp.cmd(item)
    else:
        config_path = await create_config(item)
        cmd = get_cmd(item, config_path)
        config_error = await check_rclone_config(item, config_path)
        if config_error:
            log.info(
                f"Mount {item.path} ... failed. Error: {config_error.get('error', 'unknown')}"
            )
            return False, config_error
    log.debug(f"Run cmd: {' '.join(cmd)}")
    process = await run_process(cmd)

    # When the process is no longer running
    # we remove it from the mounts dict
    async def done_callback(process, path):
        await process.wait()
        async with lock:
            if path in mounts:
                del mounts[path]

    task = asyncio.create_task(done_callback(process, item.path))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    mounts[item.path] = {
        "process": process,
        "model": item.model_dump(),
    }

    fullpath = os.path.join(base_mount_dir, item.path)
    if not is_directory_usable(fullpath):
        raise Exception(
            "Mount failed. Directory not usable. Check if remote path exists."
        )

    log.info(f"Mount {item.path} ... successful")
    return True, None


async def unmount(path: str, force: bool = False):
    mount_process = mounts[path]["process"]
    fullpath = os.path.join(base_mount_dir, path)
    process = await asyncio.create_subprocess_exec(
        *["umount", fullpath],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()
    if process.returncode != 0 and not force:
        raise Exception(stderr)

    try:
        mount_process.terminate()
        await mount_process.wait()
    except ProcessLookupError:
        pass

    if process.returncode != 0:
        # first umount failed, call umount with -l
        # That's only called with force: true
        await asyncio.create_subprocess_exec(
            *["umount", "-l", fullpath],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

    os.rmdir(fullpath)


async def init_mounts():
    init_mounts_path = os.environ.get("INIT_MOUNTS", "/mnt/config/mounts.json")
    log = getLogger()
    if os.path.exists(init_mounts_path):
        log.info("Init mounts ...")
        mounts = {}
        with open(init_mounts_path) as f:
            mounts = json.load(f)
        for mount_config in mounts:
            item = DataMountModel(**mount_config)
            item.options.external = True
            try:
                log.info(f"Mount {item.path} ...")
                success, error_process = await mount(item)
                if not success:
                    raise Exception(f"Mount failed: {error_process}")
            except:
                log.exception(
                    f"Mount {mount_config.get('path', 'unknown path')} failed"
                )
