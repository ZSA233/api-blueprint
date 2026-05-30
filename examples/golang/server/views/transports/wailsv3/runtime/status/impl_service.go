package status

import (
	shared "example.com/project/golang/server/views/routes/runtime/status"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *StatusService {
	return newGeneratedStatusService(shared.NewRouter(), dispatcher)
}
