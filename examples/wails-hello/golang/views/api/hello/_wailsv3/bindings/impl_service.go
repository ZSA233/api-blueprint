package hello

import (
	runtime "example.com/api-blueprint/wails-hello/golang/views/_wailsv3/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *HelloService {
	return newGeneratedHelloService(dispatcher)
}
