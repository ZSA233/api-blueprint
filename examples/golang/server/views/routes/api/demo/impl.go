package demo

import (
	types "example.com/project/golang/server/views/routes/api/_gen_types"
	apperrors "example.com/project/golang/server/views/runtime/errors"
	"example.com/project/golang/server/views/runtime/errors/common_err"
	"example.com/project/golang/server/views/runtime/errors/demo_err"
)

type Router struct {
	_GenRouter
}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Abc(ctx *CTX_Abc, req *REQ_Abc) (rsp *RSP_Abc, err error) {
	return demoA("abc", 7), nil
}

func (impl *Router) TestPost(ctx *CTX_TestPost, req *REQ_TestPost) (rsp *RSP_TestPost, err error) {
	body := req.B
	return &RSP_TestPost{
		List: []string{"test_post", body.Req1},
		Map: map[string]*types.ApiDemoMap{
			"req2": {Haha: int64(body.Req2)},
		},
	}, nil
}

func (impl *Router) FormSubmit(ctx *CTX_FormSubmit, req *REQ_FormSubmit) (rsp *RSP_FormSubmit, err error) {
	body := req.B
	return &RSP_FormSubmit{
		Summary: body.Title,
		Count:   body.Count,
		Enabled: body.Enabled,
	}, nil
}

func (impl *Router) PutDemo(ctx *CTX_PutDemo, req *REQ_PutDemo) (rsp *RSP_PutDemo, err error) {
	query := req.Q
	body := req.B
	return &RSP_PutDemo{
		List: []string{query.Arg1, body.Req1},
		AnonKv: &types.ANON_Func1put_anon_kv{
			Kv1: uint(body.Req2),
			Kv2: []float64{query.Arg2, float64(body.Req2)},
		},
	}, nil
}

func (impl *Router) Delete(ctx *CTX_Delete, req *REQ_Delete) (rsp *RSP_Delete, err error) {
	return &RSP_Delete{
		List: []string{req.Q.Arg1},
		AnonList: []*types.ANON_Delete_anon_list{
			{Kv1: int64(req.Q.Arg2), Kv2: []string{"deleted"}},
		},
	}, nil
}

func (impl *Router) SweepEvents(
	ctx *CTX_SweepEvents,
	stream STREAM_SweepEvents,
) error {
	open := stream.Open()
	message, err := NewSweepStreamMessageState(&SweepStreamMessage_State_DATA{
		Status: "sweep " + open.RunId + " started",
	})
	if err != nil {
		return err
	}
	if err := stream.Send(ctx, message); err != nil {
		return err
	}
	return stream.Close(ctx, &CLOSE_SweepEvents{Code: 1000, Reason: "example stream complete"})
}

func (impl *Router) PostDeprecated(ctx *CTX_PostDeprecated, req *REQ_PostDeprecated) (rsp *RSP_PostDeprecated, err error) {
	return &RSP_PostDeprecated{List: []string{req.B.Req1}}, nil
}

func (impl *Router) Raw(ctx *CTX_Raw, req *REQ_Raw) (rsp *RSP_Raw, err error) {
	return &RSP_Raw{
		List: []string{"raw"},
		List2: map[int64][]*types.ApiDemoA{
			1: {demoA("raw", 1)},
		},
	}, nil
}

func (impl *Router) MapModel(ctx *CTX_MapModel, req *REQ_MapModel) (rsp *RSP_MapModel, err error) {
	return &RSP_MapModel{
		1: {Haha: 101},
		2: {Haha: 202},
	}, nil
}

func (impl *Router) ErrorDemo(ctx *CTX_ErrorDemo, req *REQ_ErrorDemo) (rsp *RSP_ErrorDemo, err error) {
	switch req.Q.Mode {
	case "token":
		return nil, common_err.TOKEN_EXPIRE
	case "rate_limit":
		return nil, demo_err.RATE_LIMITED.WithToast(apperrors.ToastPayload{
			Key:     "demo.rate_limited",
			Level:   "warning",
			Default: "请求过于频繁，请稍后再试",
			Text:    "请等待 30 秒后重试",
		})
	case "unknown":
		return nil, apperrors.New(70001, "example undefined business error")
	default:
		return &RSP_ErrorDemo{Status: "ok"}, nil
	}
}

func demoA(label string, n int) *types.ApiDemoA {
	return &types.ApiDemoA{
		Bc:         label,
		A:          n,
		Efg:        1.5,
		Hijk:       []uint{1, 2, 3},
		EnumColor:  "red",
		EnumStatus: 2,
		EnumList:   []int{1, 2, 3},
		Lmnop: []*types.ApiDemoSubA{
			{
				Hello: map[string]int{"n": n},
				Amap:  []*types.ApiDemoMap{{Haha: int64(n)}},
			},
		},
	}
}
