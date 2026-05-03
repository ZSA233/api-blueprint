package demo

import (
	runtime "demo/views/_wailsv3/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *DemoService {
	return newGeneratedDemoService(dispatcher)
}
