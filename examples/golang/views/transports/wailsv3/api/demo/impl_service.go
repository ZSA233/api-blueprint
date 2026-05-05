package demo

import (
	shared "demo/views/routes/api/demo"
	wailstransport "demo/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *DemoService {
	return newGeneratedDemoService(shared.NewRouter(), dispatcher)
}
