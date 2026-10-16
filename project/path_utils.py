import os


def resolve_mount_path(path: str, base_dir: str) -> str:
    if not path or "\0" in path:
        raise ValueError("Mount path must not be empty")
    if os.path.isabs(path) or os.path.normpath(path) != path:
        raise ValueError("Mount path must be a normalized relative path")
    if ".." in path.split(os.sep):
        raise ValueError("Mount path must not contain parent-directory segments")

    root = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(root, path))
    if full_path == root or os.path.commonpath((root, full_path)) != root:
        raise ValueError("Mount path must remain within the mount directory")

    current_path = root
    for segment in path.split(os.sep):
        current_path = os.path.join(current_path, segment)
        if os.path.islink(current_path):
            raise ValueError("Mount path must not traverse symbolic links")

    return full_path