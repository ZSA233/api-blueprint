import Foundation

import ABClientAPIRoutes
import ABClientRuntime

let transport = URLSessionAPITransport(
    config: HTTPAPIConfig(baseURL: URL(string: "http://localhost:2333")!)
)
let api = APIRootClient(transport: transport)

_ = api.hello
print("swift narrow entrypoint ok")
