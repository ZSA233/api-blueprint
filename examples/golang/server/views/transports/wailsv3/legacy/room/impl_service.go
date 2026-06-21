package room

import (
	sharedprovider "example.com/project/golang/server/views/providers"
	shared "example.com/project/golang/server/views/routes/legacy/room"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

type ServiceOption = sharedprovider.RuntimeOption
type ErrorMapperFunc = sharedprovider.ErrorMapperFunc

func WithErrorMapper(mapper ErrorMapperFunc) ServiceOption {
	return sharedprovider.WithErrorMapper(mapper)
}

func NewService(dispatcher wailstransport.EventDispatcher, options ...ServiceOption) *RoomService {
	return newGeneratedRoomService(shared.NewRouter(), dispatcher, options...)
}
