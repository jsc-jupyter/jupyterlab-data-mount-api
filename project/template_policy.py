DEFAULT_TEMPLATES = "uftp,b2drop,aws,s3,webdav,nfs,generic"


def is_template_allowed(template: str, configured_templates: str | None) -> bool:
    if configured_templates is None:
        configured_templates = DEFAULT_TEMPLATES
    allowed_templates = {
        item.strip() for item in configured_templates.split(",") if item.strip()
    }
    return template in allowed_templates