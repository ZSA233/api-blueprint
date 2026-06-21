package hello

import (
	sharedprovider "example.com/api-blueprint/wails-hello/golang/providers"
	shared "example.com/api-blueprint/wails-hello/golang/routes/api/hello"
	wailstransport "example.com/api-blueprint/wails-hello/golang/transports/wailsv3"
)

type ServiceOption = sharedprovider.RuntimeOption
type ErrorMapperFunc = sharedprovider.ErrorMapperFunc

func WithErrorMapper(mapper ErrorMapperFunc) ServiceOption {
	return sharedprovider.WithErrorMapper(mapper)
}

func NewService(dispatcher wailstransport.EventDispatcher, options ...ServiceOption) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher, options...)
}
