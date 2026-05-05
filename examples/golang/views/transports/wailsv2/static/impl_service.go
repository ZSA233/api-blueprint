package static

import (
	shared "demo/views/routes/static"
	wailstransport "demo/views/transports/wailsv2"
)

func NewService(dispatcher wailstransport.EventDispatcher) *StaticService {
	return newGeneratedStaticService(shared.NewRouter(), dispatcher)
}
