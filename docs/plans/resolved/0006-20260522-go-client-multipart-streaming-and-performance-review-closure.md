# Go Client Multipart Streaming And Performance Review Closure

## Summary

- Close review `0007` by fixing the confirmed Go HTTP client multipart performance gap.
- Keep the public API unchanged: callers still use `runtime.MultipartFile{Reader, Bytes}`.
- Change only the generated Go HTTP transport implementation so multipart bodies are streamed with `io.Pipe` and `multipart.Writer` instead of pre-buffered into `bytes.Buffer`.
- Keep conformance focused on protocol correctness; add targeted codegen/runtime tests for the streaming invariant and record performance benchmark coverage gaps as future probe work.

## Design

- `encodeMultipart(input)` validates the multipart struct synchronously, then returns:
  - `io.Reader`: pipe reader;
  - content type: `multipart.Writer.FormDataContentType()`;
  - content length: `-1`, allowing Go `net/http` to use chunked transfer for unknown length.
- A goroutine writes multipart fields to the pipe writer and closes with `CloseWithError` so encoder failures reach `http.Client.Do`.
- `writeMultipartFile` continues to prefer `runtime.MultipartFile.Reader`; if no reader is present, it falls back to `Bytes`.
- The implementation does not try to precompute content length because that would reintroduce buffering or require a second pass over non-rewindable readers.

## Compatibility

- No public Go API break.
- Requests that previously had a fixed multipart `Content-Length` may now use unknown length/chunked transfer.
- Projects that require fixed content length can still provide a custom `runtime.Transport`; the default adapter prioritizes streaming correctness for file readers.

## Tests

- Update Go client media codegen tests to assert:
  - `encodeMultipart` uses `io.Pipe`;
  - it no longer creates `bytes.Buffer` inside the multipart encoder;
  - it returns content length `-1`;
  - errors are propagated via `CloseWithError`.
- Refresh blueprint examples so generated Go client snapshots match the template.
- Run:

```bash
uv run pytest tests/codegen/go/client/test_media_raw.py tests/codegen/go tests/codegen/shared -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
git diff --check
```

## Resolution Criteria

- Generated Go client multipart upload no longer buffers full multipart bodies before sending.
- Existing media conformance and benchmark smoke remain available.
- `0007` is moved to `docs/reviews/resolved/` with a Resolution note.
- This plan is moved to `docs/plans/resolved/`.

## Implementation Record

Implementation date: 2026-05-22

Completed:

- Go HTTP client multipart encoder now validates the request struct synchronously and streams multipart output through `io.Pipe`.
- `runtime.MultipartFile.Reader` is no longer consumed when `encodeMultipart` is called; it is consumed only when the request body is read by the HTTP client.
- Multipart content length is reported as `-1` so Go `net/http` can use unknown-length/chunked transfer for non-rewindable readers.
- Blueprint examples were refreshed so `examples/golang/client/transports/http/gen_transport.go` matches the template.
- Go client docs now document that `Reader` is the streaming upload path and `Bytes` is for small files/tests.

Validation:

```bash
uv run pytest tests/codegen/go/client/test_media_raw.py -q
env -u GOROOT uv run pytest tests/codegen/go tests/codegen/shared -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_conformance run --servers go --clients go --scenario media
```
