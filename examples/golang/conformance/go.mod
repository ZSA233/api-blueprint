module example.com/project/golang/conformance

go 1.23.8

require (
	example.com/project/golang/client v0.0.0
	github.com/coder/websocket v1.8.13
)

replace example.com/project/golang/client => ../client
