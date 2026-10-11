"""Deployment entry point with safe probes, compatible with V21 and V22.

Run: uvicorn health_app_V1:app
The existing application, middleware and lifecycle remain in use.
"""
import app as application
from health_checks_V1 import readiness_response

app = application.app
# Remove the legacy GET handler so route ordering cannot leave the old probe
# active. No existing data-bearing source file is copied or rewritten.
app.router.routes[:] = [
    route for route in app.router.routes
    if not (getattr(route, 'path', None) == '/health'
            and 'GET' in getattr(route, 'methods', set()))
]


@app.get('/health')
@app.get('/live')
def health():
    return {'status': 'ok'}


@app.get('/ready')
def readiness():
    return readiness_response(vars(application))
