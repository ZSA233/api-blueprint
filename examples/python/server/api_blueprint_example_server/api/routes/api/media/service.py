from __future__ import annotations

from .gen_service import *
from .gen_types import *


class MediaServiceImpl(MediaServiceStub):
    async def media_preview(
        self,
        multipart: MediaPreviewForm,
    ) -> bytes | ApiRawResponse[bytes]:
        """Multipart media preview
        POST /api/media/preview
        """
        return await super().media_preview(
            multipart=multipart,
        )

    async def media_frame(self) -> bytes | ApiRawResponse[bytes]:
        """Latest media frame
        GET /api/media/frame
        """
        return await super().media_frame()

    async def media_download(self) -> str | Path | ApiRawResponse[bytes]:
        """Media workbook download
        GET /api/media/download
        """
        return await super().media_download()

    async def media_download_dynamic(self) -> str | Path | ApiRawResponse[bytes]:
        """Media workbook download with service filename override
        GET /api/media/download-dynamic
        """
        return await super().media_download_dynamic()

    async def media_download_filename_edge(self) -> str | Path | ApiRawResponse[bytes]:
        """Media download with RFC 5987 filename
        GET /api/media/download-filename-edge
        """
        return await super().media_download_filename_edge()

    async def media_error_frame(
        self,
        query: MediaErrorFrameQuery,
    ) -> bytes | ApiRawResponse[bytes]:
        """Raw media typed error
        GET /api/media/error-frame
        """
        return await super().media_error_frame(
            query=query,
        )

    async def media_mjpeg(self) -> AsyncIterable[bytes] | Iterable[bytes] | ApiRawResponse[AsyncIterable[bytes] | Iterable[bytes]]:
        """MJPEG byte stream
        GET /api/media/mjpeg
        """
        return await super().media_mjpeg()
