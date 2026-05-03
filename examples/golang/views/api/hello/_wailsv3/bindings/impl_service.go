package hello

import (
	runtime "demo/views/_wailsv3/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *HelloService {
	return newGeneratedHelloService(dispatcher)
}
