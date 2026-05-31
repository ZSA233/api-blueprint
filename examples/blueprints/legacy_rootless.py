from api_blueprint.includes import *

from blueprints.app import legacybp


class AccountProfile(Model):
    user_id = String(description="user id")
    nickname = String(description="display name")


class RoomSummary(Model):
    room_id = String(description="room id")
    title = String(description="room title")


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
