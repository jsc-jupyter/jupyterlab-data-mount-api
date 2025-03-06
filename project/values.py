import os

base_mount_dir = os.environ.get("BASE_DIR", "/mnt/data_mounts")
uid = os.environ.get("NB_UID", 1000)
gid = os.environ.get("NB_GID", 100)
