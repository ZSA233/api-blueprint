package http

import runtime "example.com/project/golang/client/runtime"

func NewClient(config HttpConfig) runtime.Transport {
	return NewHttpTransport(config)
}
