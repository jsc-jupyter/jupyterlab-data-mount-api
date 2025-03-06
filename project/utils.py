import asyncio
import os
import tempfile
from copy import deepcopy

from log import getLogger
from models import DataMountModel
from values import base_mount_dir
from values import gid
from values import uid


def type_specific_args(item: DataMountModel):
    type_ = item.options.get("config", {}).get("type", None)
    vendor_ = item.options.get("config", {}).get("vendor", None)
    url_ = item.options.get("config", {}).get("url", None)
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
    stdout, stderr = await process.communicate()
    stdout = stdout.decode().strip()
    return stdout


def validate(item: DataMountModel):
    if not item.path:
        raise Exception("path not provided")
    if not item.options.get("template", None):
        raise Exception("options.template not provided")
    if not item.options.get("config", {}).get("type", None):
        raise Exception("options.config.type not provided")
    if not item.options.get("config", {}).get("remotepath", None):
        raise Exception("options.config.remotepath not provided")


def get_cmd(item: DataMountModel, config_path: str):
    template = item.options.get("template", None)
    path = item.path
    remotepath = item.options.get("config", {}).get("remotepath", "None")
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
    if item.options.get("readonly", False):
        cmd += ["--read-only"]
    return cmd


async def create_config(item: DataMountModel):
    skip_keys = {
        "readonly",
        "displayName",
        "remotepath",
    }  # They're used in the command as arguments, not in the config file itself
    config = {
        k: v
        for k, v in deepcopy(item.options.get("config", {})).items()
        if k not in skip_keys
    }

    template = item.options.get("template", None)

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
    template = item.options.get("template", None)
    remotepath = item.options.get("config", {}).get("remotepath", "None")
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
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        with open(config_path) as f:
            config_string = f.read()
        log.info(f"Check rclone config ... failed")
        log.info(stderr.decode().strip())
        description = {
            "config": config_string,
            "error": stderr.decode().strip(),
            "message": f"Config not working. Exit Code {process.returncode}",
        }
        return description
    log.info(f"Check rclone config ... successful")


async def run_rclone_mount(command: list):
    """Run rclone mount command asynchronously."""
    process = await asyncio.create_subprocess_exec(*command)
    return process


async def mount(item: DataMountModel):
    log = getLogger()
    validate(item)
    config_path = await create_config(item)
    cmd = get_cmd(item, config_path)
    config_error = await check_rclone_config(item, config_path)
    if config_error:
        return False, config_error
    log.debug(f"Run cmd: {' '.join(cmd)}")
    process = await run_rclone_mount(cmd)
    return True, process


async def unmount(path: str, mount_process: asyncio.subprocess.Process):
    fullpath = os.path.join(base_mount_dir, path)
    process = await asyncio.create_subprocess_exec(
        *["umount", fullpath],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()
    if process.returncode != 0:
        raise Exception(stderr)

    mount_process.terminate()
    await mount_process.wait()

    os.rmdir(fullpath)
