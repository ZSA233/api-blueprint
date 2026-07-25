from __future__ import annotations

from .gen_service import *
from .gen_types import *


class DemoServiceImpl(DemoServiceStub):
    async def abc(
        self,
        query: AbcQuery,
    ) -> AbcResponse:
        """这是abc的summary
        GET /api/demo/abc
        """
        return await super().abc(
            query=query,
        )

    async def test_post(
        self,
        json: TestPostJSON,
    ) -> TestPostResponse:
        """这是post的summary
        POST /api/demo/test_post
        """
        return await super().test_post(
            json=json,
        )

    async def form_submit(
        self,
        form: FormSubmitForm,
    ) -> FormSubmitResponse:
        """Form body example
        POST /api/demo/form-submit
        """
        return await super().form_submit(
            form=form,
        )

    async def request_options(
        self,
        query: RequestOptionsQuery,
    ) -> RequestOptionsResponse:
        """Request options conformance endpoint
        GET /api/demo/request-options
        """
        return await super().request_options(
            query=query,
        )

    async def path_echo(
        self,
        path: PathEchoPath,
    ) -> PathEchoResponse:
        """Path parameter example
        GET /api/demo/path-echo/{item}/{badge}
        """
        return await super().path_echo(
            path=path,
        )

    async def empty_response(self) -> EmptyResponseResponse:
        """Empty response example
        POST /api/demo/empty-response
        """
        return await super().empty_response()

    async def put_demo(
        self,
        query: PutDemoQuery,
        json: PutDemoJSON,
    ) -> PutDemoResponse:
        """这是put的summary
        PUT /api/demo/1put
        """
        return await super().put_demo(
            query=query,
            json=json,
        )

    async def delete(
        self,
        query: DeleteQuery,
    ) -> DeleteResponse:
        """这是delete的summary
        DELETE /api/demo/delete$
        """
        return await super().delete(
            query=query,
        )

    async def sweep_events(
        self,
        open_data: SweepEventsOpen,
        stream: ApiServerStream[SweepStreamMessage, SweepEventsClose] | None = None,
    ) -> Any:
        """Sweep event stream
        STREAM /api/demo/sweep-events
        """
        return await super().sweep_events(
            open_data=open_data,
            stream=stream,
        )

    async def assistant_session(
        self,
        open_data: AssistantSessionOpen,
        channel: ApiServerChannel[AssistantClientMessage, AssistantServerMessage, AssistantSessionClose] | None = None,
    ) -> Any:
        """Assistant channel
        CHANNEL /api/demo/assistant-session
        """
        return await super().assistant_session(
            open_data=open_data,
            channel=channel,
        )

    async def post_deprecated(
        self,
        json: PostDeprecatedJSON,
    ) -> PostDeprecatedResponse:
        """这是一个summary
        POST /api/demo/post_deprecated
        """
        return await super().post_deprecated(
            json=json,
        )

    async def raw(self) -> RawResponse:
        """这是一个raw
        POST /api/demo/raw
        """
        return await super().raw()

    async def map_model(self) -> dict[int, ApiDemoMap]:
        """这是一个raw
        POST /api/demo/map_model
        """
        return await super().map_model()

    async def error_demo(
        self,
        query: ErrorDemoQuery,
    ) -> ErrorDemoResponse:
        """Typed error example
        GET /api/demo/error-demo
        """
        return await super().error_demo(
            query=query,
        )
