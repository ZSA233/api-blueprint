package legacy_json

import (
	shared "example.com/project/golang/server/views/routes/legacy/legacy_json"
	wailstransport "example.com/project/golang/server/views/transports/wailsv2"
)

func NewService(dispatcher wailstransport.EventDispatcher) *LegacyJsonService {
	return newGeneratedLegacyJsonService(shared.NewRouter(), dispatcher)
}
