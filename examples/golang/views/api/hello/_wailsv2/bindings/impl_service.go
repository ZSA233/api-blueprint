package hello

import (
	runtime "demo/views/_wailsv2/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *HelloService {
	return newGeneratedHelloService(dispatcher)
}
