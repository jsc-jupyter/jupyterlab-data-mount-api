import unittest

from project.template_policy import is_template_allowed


class TemplatePolicyTests(unittest.TestCase):
    def test_default_templates_are_allowed(self):
        self.assertTrue(is_template_allowed("s3", None))
        self.assertFalse(is_template_allowed("custom", None))

    def test_configured_templates_are_enforced(self):
        self.assertTrue(is_template_allowed("webdav", "s3, webdav"))
        self.assertFalse(is_template_allowed("nfs", "s3, webdav"))

    def test_empty_allowlist_denies_every_template(self):
        self.assertFalse(is_template_allowed("s3", ""))


if __name__ == "__main__":
    unittest.main()