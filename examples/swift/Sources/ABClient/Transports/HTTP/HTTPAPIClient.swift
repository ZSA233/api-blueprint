import Foundation
import ABClientRuntime

public enum HTTPAPIClient {
    public static func create(baseURL: URL) -> ABClient {
        let transport = URLSessionAPITransport(config: HTTPAPIConfig(baseURL: baseURL))
        return ABClient(transport: transport)
    }

    public static func create(config: HTTPAPIConfig = HTTPAPIConfig()) -> ABClient {
        let transport = URLSessionAPITransport(config: config)
        return ABClient(transport: transport)
    }
}
