package hello

import (
	shared "example.com/project/golang/server/views/routes/api/hello"
	wailstransport "example.com/project/golang/server/views/transports/wailsv2"
)

func NewService(dispatcher wailstransport.EventDispatcher) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher)
}
