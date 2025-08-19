import os

from models import DataMountModel
from values import base_mount_dir
from values import gid
from values import uid


def validate(item: DataMountModel):
    if not item.options.config.get("server", None):
        description = {
            "error": "",
            "message": f"Config not working. server required",
        }
        return False, description
    if not item.options.config.get("remotepath", None):
        description = {
            "error": "",
            "message": f"Config not working. remotepath required",
        }
        return False, description
    return True, None


def cmd(item: DataMountModel):
    validation, description = validate(item)
    if not validation:
        return validation, description
    
    path = item.path
    server = item.options.config.get("server", "None")
    remotepath = item.options.config.get("remotepath", "None")
    fullpath = os.path.join(base_mount_dir, path)
    if not os.path.exists(fullpath):
        os.makedirs(fullpath, exist_ok=True)
        os.chown(fullpath, uid, gid)
    if os.path.isdir(fullpath):
        if os.listdir(fullpath):
            raise Exception(f"Directory {path} is not empty.")
    cmd = [
        "mount",
        "-t",
        "nfs",
        "-o"
    ]
    options = ["vers=4"]
    if item.options.readonly:
        options.append("ro")
    options_str = ','.join(options)
    cmd.append(options_str)
    cmd.append(f"{server}:{remotepath}")
    cmd.append(fullpath)
    check_cmd = ["&&", "while", "grep", "-qs", f"\"{fullpath} \"", "/proc/mounts;", "do", "sleep", "1;", "done"]
    cmd += check_cmd
    return ["sh", "-c", ' '.join(cmd)]