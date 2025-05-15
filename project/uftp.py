import os

import pyunicore.client as uc_client
import pyunicore.credentials as uc_credentials
import pyunicore.uftp.uftp as uc_uftp
from models import DataMountModel
from values import base_mount_dir
from values import gid
from values import uid


def validate(item: DataMountModel):
    if not item.options.config.get("access_token", None):
        description = {
            "error": "",
            "message": f"Config not working. access_token required",
        }
        return False, description
    if not item.options.config.get("auth_url", None):
        description = {
            "error": "",
            "message": f"Config not working. auth_url required",
        }
        return False, description
    return True, None


def cmd(item: DataMountModel):
    validation, description = validate(item)
    if not validation:
        return validation, description

    access_token = item.options.config["access_token"]
    cred = uc_credentials.OIDCToken(access_token, None)
    _auth = item.options.config["auth_url"]

    if item.options.config.get("remotepath", "/") == "__custom__path__":
        _base_dir = item.options.config.get("custompath", "/")
    else:
        _base_dir = item.options.config.get("remotepath", "/")
    uc_client.Transport(credential=cred, verify=False, timeout=30)
    pref_list = []
    if "uid" in item.options.config.keys():
        pref_list.append(f"uid:{item.options.config['uid']}")
    if "group" in item.options.config.keys():
        pref_list.append(f"group:{item.options.config['group']}")
    preferences = ",".join(pref_list)
    _host, _port, _password = uc_uftp.UFTP().authenticate(
        cred, _auth, _base_dir, preferences=preferences if preferences else None
    )
    cmd = ["/opt/datamount_venv/bin/unicore-fusedriver", "-d"]
    if item.options.readonly:
        cmd.append("-r")
    cmd.extend(["-P", _password])
    cmd.append(f"{_host}:{_port}")
    cmd.extend(["--fuse-options", f"uid={uid},gid={gid},allow_other"])
    fullpath = os.path.join(base_mount_dir, item.path)
    cmd.append(fullpath)
    if not os.path.exists(fullpath):
        os.makedirs(fullpath, exist_ok=True)
        os.chown(fullpath, uid, gid)
    if os.path.isdir(fullpath):
        if os.listdir(fullpath):
            raise Exception(f"Directory {item.path} is not empty.")
    return cmd
