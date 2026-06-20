package providers

func SelectProvider[Path, Query, Body, Response any](
	spec ProviderSpec,
	handler RouteHandler[Path, Query, Body, Response],
) Provider {
	return nil
}
