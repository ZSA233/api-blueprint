package media

import (
	"io"
	"strings"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

var sampleJPEG = []byte{0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 'J', 'F', 'I', 'F', 0x00, 0x01, 0x01, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9}

func (impl *Router) MediaPreview(ctx *CTX_MediaPreview, req *REQ_MediaPreview) (rsp *RSP_MediaPreview, err error) {
	if req != nil && req.B != nil && req.B.Image.File != nil {
		_, _ = io.Copy(io.Discard, req.B.Image.File)
		_ = req.B.Image.File.Close()
	}
	return &RSP_MediaPreview{
		Body:        sampleJPEG,
		ContentType: "image/jpeg",
	}, nil
}

func (impl *Router) MediaFrame(ctx *CTX_MediaFrame, req *REQ_MediaFrame) (rsp *RSP_MediaFrame, err error) {
	return &RSP_MediaFrame{
		Body:        sampleJPEG,
		ContentType: "image/jpeg",
	}, nil
}

func (impl *Router) MediaDownload(ctx *CTX_MediaDownload, req *REQ_MediaDownload) (rsp *RSP_MediaDownload, err error) {
	return &RSP_MediaDownload{
		Body:        []byte("PK\x03\x04api-blueprint media report\n"),
		ContentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	}, nil
}

func (impl *Router) MediaDownloadDynamic(ctx *CTX_MediaDownloadDynamic, req *REQ_MediaDownloadDynamic) (rsp *RSP_MediaDownloadDynamic, err error) {
	return &RSP_MediaDownloadDynamic{
		Body:        []byte("PK\x03\x04api-blueprint media report dynamic\n"),
		ContentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		Filename:    "media-report-dynamic.xlsx",
	}, nil
}

func (impl *Router) MediaMjpeg(ctx *CTX_MediaMjpeg, req *REQ_MediaMjpeg) (rsp *RSP_MediaMjpeg, err error) {
	chunk := "--frame\r\nContent-Type: image/jpeg\r\n\r\n" + string(sampleJPEG) + "\r\n"
	return &RSP_MediaMjpeg{
		Stream:      strings.NewReader(chunk),
		ContentType: "multipart/x-mixed-replace; boundary=frame",
		Size:        int64(len(chunk)),
	}, nil
}
