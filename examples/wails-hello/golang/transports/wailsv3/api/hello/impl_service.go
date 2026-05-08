package hello

import (
	shared "example.com/api-blueprint/wails-hello/golang/routes/api/hello"
	wailstransport "example.com/api-blueprint/wails-hello/golang/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher)
}
