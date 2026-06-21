package hello

import (
	sharedprovider "example.com/project/golang/server/views/providers"
	shared "example.com/project/golang/server/views/routes/api/hello"
	wailstransport "example.com/project/golang/server/views/transports/wailsv2"
)

type ServiceOption = sharedprovider.RuntimeOption
type ErrorMapperFunc = sharedprovider.ErrorMapperFunc

func WithErrorMapper(mapper ErrorMapperFunc) ServiceOption {
	return sharedprovider.WithErrorMapper(mapper)
}

func NewService(dispatcher wailstransport.EventDispatcher, options ...ServiceOption) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher, options...)
}
