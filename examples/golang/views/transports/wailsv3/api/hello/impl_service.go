package hello

import (
	shared "demo/views/routes/api/hello"
	wailstransport "demo/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *HelloService {
	return newGeneratedHelloService(shared.NewRouter(), dispatcher)
}
