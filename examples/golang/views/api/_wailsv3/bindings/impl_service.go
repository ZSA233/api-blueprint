package api

import (
	runtime "demo/views/_wailsv3/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *ApiService {
	return newGeneratedApiService(dispatcher)
}
