package legacy_json

import (
	types "example.com/project/golang/server/views/routes/legacy/_gen_types"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) LegacyJsonCompat(
	ctx *CTX_LegacyJsonCompat,
	req *REQ_LegacyJsonCompat,
) (rsp *RSP_LegacyJsonCompat, err error) {
	return &types.LegacyJsonCompatPayload{
		Target:        []string{"legacy-room", "backup-room"},
		Ids:           []any{"1", 2, "3"},
		NormalizedIds: []string{"1", "2", "3"},
	}, nil
}
