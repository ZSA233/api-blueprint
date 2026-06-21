package providers

// AuthContext is intentionally user-owned: unlike RequestContext,
// ResponseContext, and HandleContext, generated transports do not depend on a
// fixed auth field layout. Add project auth/session fields here as needed.
type AuthContext[Path, Query, Body, Response any] struct{}

func (prov *AuthProvider[Path, Query, Body, Response]) BuildAuthContext(
	ctx *Context[Path, Query, Body, Response],
	req *REQ[Path, Query, Body],
) (auth *AuthContext[Path, Query, Body, Response], err error) {
	return &AuthContext[Path, Query, Body, Response]{}, nil
}
