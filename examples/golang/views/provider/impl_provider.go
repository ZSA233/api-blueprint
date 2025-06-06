package provider

func Select[Q, F, J, P any](
	key string, value string,
	handler func(c *Context[Q, F, J, P], req *REQ[Q, F, J]) (rsp *P, err error),
) Provider {
	var prov Provider = nil
	switch key {
	}
	return prov
}
