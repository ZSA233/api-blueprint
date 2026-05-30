import Foundation

public enum HTTPAPIClient {
    public static func create(baseURL: URL) -> ApiBlueprintExampleClient {
        let transport = URLSessionAPITransport(config: HTTPAPIConfig(baseURL: baseURL))
        return ApiBlueprintExampleClient(transport: transport)
    }

    public static func create(config: HTTPAPIConfig = HTTPAPIConfig()) -> ApiBlueprintExampleClient {
        let transport = URLSessionAPITransport(config: config)
        return ApiBlueprintExampleClient(transport: transport)
    }
}
