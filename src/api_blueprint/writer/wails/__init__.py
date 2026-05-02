from api_blueprint.writer.core.registry import GeneratorTargetSpec, register_target

from .golang import WailsBlueprint, WailsGoWriter, WailsRouter, WailsRouterGroup
from .models import WailsGenerationTarget
from .writer import WailsWriter

register_target(
    GeneratorTargetSpec(
        name="wails",
        implemented=True,
        writer_factory=WailsWriter,
        description="Generate Wails v2/v3 Go bridge services and TypeScript clients.",
    )
)

__all__ = (
    "WailsBlueprint",
    "WailsGenerationTarget",
    "WailsGoWriter",
    "WailsRouter",
    "WailsRouterGroup",
    "WailsWriter",
)
