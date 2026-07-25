package com.example.apiblueprint.api.routes.api.media

import com.example.apiblueprint.api.runtime.*

public class MediaService : MediaServiceStub() {

    /**
     * Multipart media preview
     * POST /api/media/preview
     */
    public override suspend fun mediaPreview(
        multipart: MediaPreviewRequest
    ): ApiRawResponse {
        return super.mediaPreview(
            multipart = multipart
        )
    }

    /**
     * Latest media frame
     * GET /api/media/frame
     */
    public override suspend fun mediaFrame(
    ): ApiRawResponse {
        return super.mediaFrame(
        )
    }

    /**
     * Media workbook download
     * GET /api/media/download
     */
    public override suspend fun mediaDownload(
    ): ApiRawResponse {
        return super.mediaDownload(
        )
    }

    /**
     * Media workbook download with service filename override
     * GET /api/media/download-dynamic
     */
    public override suspend fun mediaDownloadDynamic(
    ): ApiRawResponse {
        return super.mediaDownloadDynamic(
        )
    }

    /**
     * Media download with RFC 5987 filename
     * GET /api/media/download-filename-edge
     */
    public override suspend fun mediaDownloadFilenameEdge(
    ): ApiRawResponse {
        return super.mediaDownloadFilenameEdge(
        )
    }

    /**
     * Raw media typed error
     * GET /api/media/error-frame
     */
    public override suspend fun mediaErrorFrame(
        query: MediaMediaErrorFrameQuery
    ): ApiRawResponse {
        return super.mediaErrorFrame(
            query = query
        )
    }

    /**
     * MJPEG byte stream
     * GET /api/media/mjpeg
     */
    public override suspend fun mediaMjpeg(
    ): ApiStreamResponse {
        return super.mediaMjpeg(
        )
    }

}
