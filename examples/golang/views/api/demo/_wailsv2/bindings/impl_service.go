package demo

import (
	runtime "demo/views/_wailsv2/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *DemoService {
	return newGeneratedDemoService(dispatcher)
}
