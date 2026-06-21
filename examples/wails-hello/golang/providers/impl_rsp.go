package providers

// User-owned extension point for response provider helpers.
//
// ResponseContext, ResponseMeta, RuntimeOptions, and envelope wrappers are
// generated in gen_rsp.go / gen_wrapper.go so every transport observes the same
// success and error semantics. Add project-specific response helper methods in
// this file or another non-gen file, but do not re-declare generated response
// types.
