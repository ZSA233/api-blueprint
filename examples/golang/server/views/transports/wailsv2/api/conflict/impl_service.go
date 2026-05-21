package conflict

import (
	shared "example.com/project/golang/server/views/routes/api/conflict"
	wailstransport "example.com/project/golang/server/views/transports/wailsv2"
)

func NewService(dispatcher wailstransport.EventDispatcher) *ConflictService {
	return newGeneratedConflictService(shared.NewRouter(), dispatcher)
}
