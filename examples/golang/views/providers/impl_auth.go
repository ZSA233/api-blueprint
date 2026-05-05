package providers

type AuthContext[Q, B, P any] struct{}

func (prov *AuthProvider[Q, B, P]) BuildAuthContext(
	ctx *Context[Q, B, P],
	req *REQ[Q, B],
) (auth *AuthContext[Q, B, P], err error) {
	return &AuthContext[Q, B, P]{}, nil
}
