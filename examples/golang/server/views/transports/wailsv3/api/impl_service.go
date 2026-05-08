package api

import (
	shared "example.com/project/golang/server/views/routes/api"
	wailstransport "example.com/project/golang/server/views/transports/wailsv3"
)

func NewService(dispatcher wailstransport.EventDispatcher) *ApiService {
	return newGeneratedApiService(shared.NewRouter(), dispatcher)
}
