package main

import (
	"embed"
	"fmt"

	bindinghello "example.com/api-blueprint/wails-hello/golang/transports/wailsv3/api/hello"

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
		return fmt.Errorf("[wails-hello] application is not ready")
	}
	if ok := dispatcher.app.Event.Emit(name, payload); !ok {
		return fmt.Errorf("[wails-hello] failed to emit event[%s]", name)
	}
	return nil
}

func main() {
	dispatcher := &EventDispatcher{}
	app := application.New(application.Options{
		Name:        "api-blueprint-wails-hello",
		Description: "Minimal api-blueprint Wails-only hello example",
		Assets: application.AssetOptions{
			Handler: application.AssetFileServerFS(assets),
		},
		Services: []application.Service{
			application.NewService(bindinghello.NewService(dispatcher)),
		},
	})
	dispatcher.SetApp(app)

	app.Window.NewWithOptions(application.WebviewWindowOptions{
		Name:      "main",
		Title:     "api-blueprint Wails Hello",
		Width:     920,
		Height:    640,
		MinWidth:  720,
		MinHeight: 520,
	})

	if err := app.Run(); err != nil {
		panic(err)
	}
}
