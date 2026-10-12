from django.conf import settings
from django.utils.cache import patch_cache_control

UNCACHED_PATHS = ('/api/health/',)


class ApiCacheHeadersMiddleware:
    """Mark successful API GETs as publicly cacheable; the data changes only on deploy or import."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method in ('GET', 'HEAD')
            and request.path.startswith('/api/')
            and request.path not in UNCACHED_PATHS
            and response.status_code == 200
            and not response.has_header('Cache-Control')
        ):
            patch_cache_control(response, public=True, max_age=getattr(settings, 'API_CACHE_MAX_AGE', 3600))
        return response
