package com.example.apiblueprint.api.routes.api.demo

import com.example.apiblueprint.api.runtime.*

public class DemoService : DemoServiceStub() {

    /**
     * 这是abc的summary
     * GET /api/demo/abc
     */
    public override suspend fun abc(
        query: DemoAbcQuery
    ): ApiDemoA {
        return super.abc(
            query = query
        )
    }

    /**
     * 这是post的summary
     * POST /api/demo/test_post
     */
    public override suspend fun testPost(
        json: DemoTestPostJson
    ): DemoTestPostResponse {
        return super.testPost(
            json = json
        )
    }

    /**
     * Form body example
     * POST /api/demo/form-submit
     */
    public override suspend fun formSubmit(
        form: DemoFormSubmitForm
    ): DemoFormSubmitResponse {
        return super.formSubmit(
            form = form
        )
    }

    /**
     * Request options conformance endpoint
     * GET /api/demo/request-options
     */
    public override suspend fun requestOptions(
        query: DemoRequestOptionsQuery
    ): RequestOptionsResponse {
        return super.requestOptions(
            query = query
        )
    }

    /**
     * Path parameter example
     * GET /api/demo/path-echo/{item}/{badge}
     */
    public override suspend fun pathEcho(
        path: PathEchoPath
    ): PathEchoResponse {
        return super.pathEcho(
            path = path
        )
    }

    /**
     * Empty response example
     * POST /api/demo/empty-response
     */
    public override suspend fun emptyResponse(
    ): DemoEmptyResponseResponse {
        return super.emptyResponse(
        )
    }

    /**
     * 这是put的summary
     * PUT /api/demo/1put
     */
    public override suspend fun putDemo(
        query: DemoPutDemoQuery,
        json: DemoPutDemoJson
    ): DemoPutDemoResponse {
        return super.putDemo(
            query = query,
            json = json
        )
    }

    /**
     * 这是delete的summary
     * DELETE /api/demo/delete$
     */
    public override suspend fun delete(
        query: DemoDeleteQuery
    ): String {
        return super.delete(
            query = query
        )
    }

    /**
     * Sweep event stream
     * STREAM /api/demo/sweep-events
     */
    public override suspend fun sweepEvents(
        openData: SweepOpen,
        stream: ApiServerStream<SweepStreamMessage, ConnectionClose>
    ): Unit {
        return super.sweepEvents(
            openData = openData,
            stream = stream
        )
    }

    /**
     * Assistant channel
     * CHANNEL /api/demo/assistant-session
     */
    public override suspend fun assistantSession(
        openData: AssistantOpen,
        channel: ApiServerChannel<AssistantClientMessage, AssistantServerMessage, ConnectionClose>
    ): Unit {
        return super.assistantSession(
            openData = openData,
            channel = channel
        )
    }

    /**
     * 这是一个summary
     * POST /api/demo/post_deprecated
     */
    public override suspend fun postDeprecated(
        json: DemoPostDeprecatedJson
    ): DemoPostDeprecatedResponse {
        return super.postDeprecated(
            json = json
        )
    }

    /**
     * 这是一个raw
     * POST /api/demo/raw
     */
    public override suspend fun raw(
    ): DemoRawResponse {
        return super.raw(
        )
    }

    /**
     * 这是一个raw
     * POST /api/demo/map_model
     */
    public override suspend fun mapModel(
    ): DemoMapModelResponse {
        return super.mapModel(
        )
    }

    /**
     * Typed error example
     * GET /api/demo/error-demo
     */
    public override suspend fun errorDemo(
        query: DemoErrorDemoQuery
    ): DemoErrorDemoResponse {
        return super.errorDemo(
            query = query
        )
    }

}
