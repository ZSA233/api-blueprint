package api

import (
	shared "demo/views/routes/api"
	wailstransport "demo/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *ApiService {
	return newGeneratedApiService(shared.NewRouter(), dispatcher)
}
