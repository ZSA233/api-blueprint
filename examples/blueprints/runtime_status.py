from api_blueprint.includes import *

from blueprints.app import runtimebp


class RuntimeStatus(Model):
    status = String(description="runtime root status")


with runtimebp.group('/status') as views:
    views.GET(
        '/current',
        operation_id='RuntimeCurrentStatus',
        summary='Runtime root naming example',
        description='Covers Swift root module naming when the root segment is runtime.',
    ).RSP(RuntimeStatus)
