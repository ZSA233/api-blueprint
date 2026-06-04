from api_blueprint.includes import *

from blueprints.app import legacybp


class AccountProfile(Model):
    user_id = LegacyStringID(description="user id")
    nickname = String(description="display name")


class RoomSummary(Model):
    room_id = LegacyStringID(description="room id")
    title = String(description="room title")


class LegacyJsonCompatPayload(Model):
    target = OneOf(String(), Array[String](), description="legacy target")
    ids = Array[OneOf(String(), Int())](description="legacy ids")
    normalized_ids = Array[LegacyStringID](description="legacy ids normalized to string")


with legacybp.group('/account') as views:
    views.GET(
        '/profile',
        operation_id='AccountProfile',
        summary='Rootless account profile example',
        description='Covers a rootless Blueprint group under /account.',
    ).RSP(AccountProfile)


with legacybp.group('/room') as views:
    views.GET(
        '/list',
        operation_id='RoomList',
        summary='Rootless room list example',
        description='Covers a second top-level group under the same logical blueprint.',
    ).RSP(
        rooms=Array[RoomSummary](description='rooms'),
    )


with legacybp.group('/legacy-json') as views:
    views.GET(
        '/compat',
        operation_id='LegacyJsonCompat',
        summary='Legacy JSON compatibility example',
        description='Covers legacy fields that accept multiple JSON shapes.',
    ).RSP(LegacyJsonCompatPayload)
