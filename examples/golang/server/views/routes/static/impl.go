package static

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) DocJson(ctx *CTX_DocJson, req *REQ_DocJson) (rsp *RSP_DocJson, err error) {
	return &RSP_DocJson{}, nil
}

func (impl *Router) Dochaha(ctx *CTX_Dochaha, req *REQ_Dochaha) (rsp *RSP_Dochaha, err error) {
	return &RSP_Dochaha{A: "hello world"}, nil
}
