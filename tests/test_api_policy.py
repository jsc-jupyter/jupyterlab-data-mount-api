import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_DIR = Path(__file__).resolve().parents[1] / "project"
sys.path.insert(0, str(PROJECT_DIR))
_TEST_MOUNT_DIR = tempfile.TemporaryDirectory()
os.environ["BASE_DIR"] = _TEST_MOUNT_DIR.name

import main
from models import DataMountModel


class ApiPolicyTests(unittest.TestCase):
    def test_delete_rejects_external_mount(self):
        mounts = {"shared": {"model": {"options": {"external": True}}}}
        with (
            patch.object(main.utils, "get_mounts", return_value=mounts),
            patch.object(main.utils, "unmount", new_callable=AsyncMock) as unmount,
        ):
            response = asyncio.run(main.delete("shared", force=True))

        self.assertEqual(response.status_code, 403)
        unmount.assert_not_awaited()

    def test_delete_allows_user_mount(self):
        mounts = {"mine": {"model": {"options": {"external": False}}}}
        with (
            patch.object(main.utils, "get_mounts", return_value=mounts),
            patch.object(main.utils, "unmount", new_callable=AsyncMock) as unmount,
        ):
            response = asyncio.run(main.delete("mine", force=True))

        self.assertEqual(response.status_code, 204)
        unmount.assert_awaited_once_with("mine", force=True)

    def test_post_cannot_set_external_flag(self):
        item = DataMountModel(
            path="mine",
            options={
                "displayName": "Mine",
                "template": "s3",
                "external": True,
                "config": {"type": "s3", "remotepath": "bucket"},
            },
        )
        with (
            patch.dict(os.environ, {"JUPYTERLAB_DATA_MOUNT_TEMPLATES": "s3"}),
            patch.object(main.utils, "validate"),
            patch.object(main.utils, "get_mounts", return_value={}),
            patch.object(
                main.utils, "mount", new_callable=AsyncMock, return_value=(True, None)
            ) as mount,
        ):
            response = asyncio.run(main.post(item))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(item.options.external)
        self.assertFalse(mount.await_args.args[0].options.external)

    def test_post_rejects_unconfigured_template(self):
        item = DataMountModel(
            path="mine",
            options={
                "displayName": "Mine",
                "template": "nfs",
                "config": {"server": "192.0.2.1", "remotepath": "/share"},
            },
        )
        with (
            patch.dict(os.environ, {"JUPYTERLAB_DATA_MOUNT_TEMPLATES": "s3"}),
            patch.object(main.utils, "validate") as validate,
        ):
            response = asyncio.run(main.post(item))

        self.assertEqual(response.status_code, 403)
        validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()