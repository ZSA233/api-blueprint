package room

import (
	shared "example.com/project/golang/server/views/routes/legacy/room"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *RoomService {
	return newGeneratedRoomService(shared.NewRouter(), dispatcher)
}
