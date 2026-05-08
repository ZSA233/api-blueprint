package static

import (
	shared "example.com/project/golang/server/views/routes/static"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *StaticService {
	return newGeneratedStaticService(shared.NewRouter(), dispatcher)
}
