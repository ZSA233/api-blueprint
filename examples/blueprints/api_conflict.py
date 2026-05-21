from api_blueprint.includes import *

from blueprints.app import apibp
import enum


class KeywordEnum(enum.StrEnum):
    DEFAULT = "default"
    CLASS = "class"


class ConflictModel(Model):
    default = String(description="reserved keyword field")
    class_ = String(description="python-safe class field")
    enum = Enum[KeywordEnum](description="reserved enum value")


with apibp.group('/conflict') as views:
    views.GET(
        '/default',
        operation_id='default',
        summary='Naming conflict example',
        description='Covers reserved operation names and route-local model names',
    ).ARGS(
        class_ = String(description='reserved query field', default='query-class'),
    ).RSP(ConflictModel)
