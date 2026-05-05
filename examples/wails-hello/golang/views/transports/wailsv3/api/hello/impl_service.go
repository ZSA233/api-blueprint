package hello

import (
	shared "example.com/api-blueprint/wails-hello/golang/views/routes/api/hello"
	wailstransport "example.com/api-blueprint/wails-hello/golang/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher)
}
