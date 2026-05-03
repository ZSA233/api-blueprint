package api

import (
	runtime "demo/views/_wailsv2/runtime"
)

func NewService(dispatcher runtime.EventDispatcher) *ApiService {
	return newGeneratedApiService(dispatcher)
}
