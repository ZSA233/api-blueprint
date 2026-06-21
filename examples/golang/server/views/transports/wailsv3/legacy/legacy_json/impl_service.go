package legacy_json

import (
	sharedprovider "example.com/project/golang/server/views/providers"
	shared "example.com/project/golang/server/views/routes/legacy/legacy_json"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

type ServiceOption = sharedprovider.RuntimeOption
type ErrorMapperFunc = sharedprovider.ErrorMapperFunc

func WithErrorMapper(mapper ErrorMapperFunc) ServiceOption {
	return sharedprovider.WithErrorMapper(mapper)
}

func NewService(dispatcher wailstransport.EventDispatcher, options ...ServiceOption) *LegacyJsonService {
	return newGeneratedLegacyJsonService(shared.NewRouter(), dispatcher, options...)
}
