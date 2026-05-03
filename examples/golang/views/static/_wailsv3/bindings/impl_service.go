package static

import (
	runtime "demo/views/_wailsv3/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *StaticService {
	return newGeneratedStaticService(dispatcher)
}
