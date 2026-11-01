from app.config import settings

# Maps the {service} part of /api/v1/proxy/{service}/{path} to a base URL.
# Services without a configured URL are left out, so they return 404.
DOWNSTREAM_SERVICES = {
    name: url
    for name, url in {"hello": settings.downstream_hello_url}.items()
    if url
}
