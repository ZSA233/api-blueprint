package main

import (
	"embed"
	"fmt"

	bindingapi "demo/views/transports/wailsv3/api"
	bindingdemo "demo/views/transports/wailsv3/api/demo"
	bindinghello "demo/views/transports/wailsv3/api/hello"
	bindingstatic "demo/views/transports/wailsv3/static"

	"github.com/wailsapp/wails/v3/pkg/application"
)

//go:embed all:frontend/dist
var assets embed.FS

type EventDispatcher struct {
	app *application.App
}

func (dispatcher *EventDispatcher) SetApp(app *application.App) {
	dispatcher.app = app
}

func (dispatcher *EventDispatcher) Emit(name string, payload any) error {
	if dispatcher.app == nil {
		return fmt.Errorf("[wails-harness/v3] application is not ready")
	}
	if ok := dispatcher.app.Event.Emit(name, payload); !ok {
		return fmt.Errorf("[wails-harness/v3] failed to emit event[%s]", name)
	}
	return nil
}

func main() {
	dispatcher := &EventDispatcher{}
	app := application.New(application.Options{
		Name:        "api-blueprint-wails-v3-harness",
		Description: "Minimal api-blueprint Wails v3 harness",
		Assets: application.AssetOptions{
			Handler: application.AssetFileServerFS(assets),
		},
		Services: []application.Service{
			application.NewService(bindingapi.NewService(dispatcher)),
			application.NewService(bindingdemo.NewService(dispatcher)),
			application.NewService(bindinghello.NewService(dispatcher)),
			application.NewService(bindingstatic.NewService(dispatcher)),
		},
	})
	dispatcher.SetApp(app)

	app.Window.NewWithOptions(application.WebviewWindowOptions{
		Name:      "main",
		Title:     "api-blueprint Wails v3 Harness",
		Width:     1200,
		Height:    760,
		MinWidth:  960,
		MinHeight: 640,
	})

	if err := app.Run(); err != nil {
		panic(err)
	}
}
