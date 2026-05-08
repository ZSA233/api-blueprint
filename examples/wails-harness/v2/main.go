package main

import (
	"context"
	"embed"
	"fmt"

	bindingapi "example.com/project/golang/server/views/transports/wailsv2/api"
	bindingdemo "example.com/project/golang/server/views/transports/wailsv2/api/demo"
	bindinghello "example.com/project/golang/server/views/transports/wailsv2/api/hello"
	bindingstatic "example.com/project/golang/server/views/transports/wailsv2/static"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	wailsruntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

//go:embed all:frontend/dist
var assets embed.FS

type EventDispatcher struct {
	ctx context.Context
}

func (dispatcher *EventDispatcher) SetContext(ctx context.Context) {
	dispatcher.ctx = ctx
}

func (dispatcher *EventDispatcher) Emit(name string, payload any) error {
	if dispatcher.ctx == nil {
		return fmt.Errorf("[wails-harness/v2] runtime context is not ready")
	}
	wailsruntime.EventsEmit(dispatcher.ctx, name, payload)
	return nil
}

func main() {
	dispatcher := &EventDispatcher{}
	err := wails.Run(&options.App{
		Title:  "api-blueprint Wails v2 Harness",
		Width:  1200,
		Height: 760,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		OnStartup: func(ctx context.Context) {
			dispatcher.SetContext(ctx)
		},
		Bind: []interface{}{
			bindingapi.NewService(dispatcher),
			bindingdemo.NewService(dispatcher),
			bindinghello.NewService(dispatcher),
			bindingstatic.NewService(dispatcher),
		},
	})
	if err != nil {
		panic(err)
	}
}
