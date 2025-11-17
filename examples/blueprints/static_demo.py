from api_blueprint.includes import *
from blueprints.app import staticbp

staticbp.GET('/doc.json').RSP()
staticbp.GET('/dochaha').RSP(
    a = String(description='a', default='hello world')
)