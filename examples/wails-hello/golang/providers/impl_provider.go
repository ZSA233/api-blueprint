package providers

func SelectProvider[Q, B, P any](
	spec ProviderSpec,
	handler RouteHandler[Q, B, P],
) Provider {
	return nil
}
