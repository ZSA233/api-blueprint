from api_blueprint.includes import *

from blueprints.app import altbp
import enum


class KeywordEnum(enum.StrEnum):
    DEFAULT = "default"
    CLASS = "class"


class ConflictModel(Model):
    default = String(description="same model name in another blueprint root")
    class_ = String(description="same python-safe field in another root")
    enum = Enum[KeywordEnum](description="same enum name in another root")


with altbp.group('/conflict') as views:
    views.GET(
        '/default',
        operation_id='default',
        summary='Alt naming conflict example',
        description='Covers multi-blueprint output and ok/data/error envelopes',
    ).ARGS(
        class_ = String(description='reserved query field', default='alt-query-class'),
    ).RSP(ConflictModel)
