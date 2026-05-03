package provider

type Indexer[Q, B, P any] struct {
	Req *ReqProvider[Q, B, P]
	Rsp *RspProvider[Q, B, P]
}

func Select[Q, B, P any](
	key string, value string,
	handler func(c *Context[Q, B, P], req *REQ[Q, B]) (rsp *P, err error),
) Provider {
	var prov Provider = nil
	switch key {
	}
	return prov
}
