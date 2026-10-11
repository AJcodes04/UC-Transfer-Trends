"""One error shape for every response: {'error': '<message>'}."""

from rest_framework.response import Response
from rest_framework.views import exception_handler


def error_response(message, status_code):
    return Response({'error': message}, status=status_code)


def api_exception_handler(exc, context):
    """Reshape DRF's default {'detail': ...} payload so raised exceptions match hand-built errors."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and 'detail' in data:
        data = data['detail']
    response.data = {'error': str(data) if not isinstance(data, (list, dict)) else data}
    return response
