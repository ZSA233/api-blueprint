from .gen_client import *
from .gen_types import *


# Preserved channel processor scaffolds. Customize these classes to plug a
# project-owned channel bridge into the generated typed message visitors.


class AssistantSessionChannelSession:
    def __init__(
        self,
        bridge: ApiChannelBridge[AssistantServerMessage, AssistantClientMessage, AssistantSessionClose],
        processor: AssistantServerMessageProcessor[object],
        context: object | None = None,
    ):
        self.bridge = bridge
        self.processor = processor
        self.context = context

    async def serve(self) -> None:
        async for message in self.bridge:
            visit_assistant_server_message(self.context, message, self.processor)
