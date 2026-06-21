package providers

// SelectProvider is the user-owned hook for replacing or extending generated
// provider selection. Keep generated provider interfaces and context frames in
// gen_ files; use this hook to add project providers or return nil to keep the
// generated defaults.
func SelectProvider[Path, Query, Body, Response any](
	spec ProviderSpec,
	handler RouteHandler[Path, Query, Body, Response],
) Provider {
	return nil
}
