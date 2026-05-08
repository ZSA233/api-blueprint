package demo

import (
	shared "example.com/project/golang/server/views/routes/api/demo"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *DemoService {
	return newGeneratedDemoService(shared.NewRouter(), dispatcher)
}
