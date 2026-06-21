package api

import (
	sharedprovider "example.com/project/golang/server/views/providers"
	shared "example.com/project/golang/server/views/routes/api"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

type ServiceOption = sharedprovider.RuntimeOption
type ErrorMapperFunc = sharedprovider.ErrorMapperFunc

func WithErrorMapper(mapper ErrorMapperFunc) ServiceOption {
	return sharedprovider.WithErrorMapper(mapper)
}

func NewService(dispatcher wailstransport.EventDispatcher, options ...ServiceOption) *ApiService {
	return newGeneratedApiService(shared.NewRouter(), dispatcher, options...)
}
