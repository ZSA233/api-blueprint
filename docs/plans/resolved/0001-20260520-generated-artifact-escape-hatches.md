# Generated Artifact Escape Hatches

## Status

Superseded / archived.

This early design note is no longer an active implementation plan. Its core intent has been absorbed into the later generated ownership, request-options, production escape-hatch, resource-guard, and performance-closure plans:

- `docs/plans/resolved/0002-20260520-generated-template-ownership-and-client-request-options.md`
- `docs/plans/resolved/0004-20260522-production-escape-hatches-and-narrow-entrypoints.md`
- `docs/plans/resolved/0005-20260522-server-resource-guards-file-streaming-and-dependency-hygiene.md`
- `docs/plans/resolved/0006-20260522-go-client-multipart-streaming-and-performance-review-closure.md`

The historical guidance below is kept for context, but it should not be treated as the current source of implementation truth. Current user-facing rules live in `PRE_README.MD`, `README.md`, `README_EN.md`, and `docs/zh|en/generators.md`.

Archived on 2026-05-22.

## Original Note

This note records the recommended low-intrusion escape hatch model for generated API artifacts. It is a design note only; this change set does not modify generator behavior.

## Recommendation

Prefer preserved overlay files around generated contracts:

- Keep protocol contracts, DTOs, typed errors, route clients, binary codecs, and message unions in generator-owned `gen_*` / `Gen*` files.
- Keep stable facades, route wrappers, codec registries, transport constructors, and service stubs in preserved files that are created only when missing.
- Let applications bypass a bad generated route through a preserved wrapper, custom transport, codec override, or raw request body helper while waiting for the generator fix.
- Keep the bypass local to the affected route or codec so normal regeneration still updates the rest of the SDK.

This gives users a way to ship when one generated method is broken without forking the entire generated tree.

## Useful Hooks

- Stable facade: expose the normal generated client by default, but allow an app-owned method to call a fixed implementation for one route.
- Transport hook: replace the generated HTTP transport with an app-owned transport that special-cases a request and delegates all other requests.
- Codec registry: register an app-owned JSON or binary codec override for one DTO or packet type.
- Raw body fallback: use a generated binary/raw body type to send bytes directly when the typed codec has a defect.
- Route-level wrapper override: add an app-owned wrapper next to the generated route client and update the app import to use the wrapper.

## Not Recommended For The First Phase

- Template partial overrides: they add a second template resolution model and make support/debugging harder.
- Post-generate patch hooks: they hide generated output drift and make reproducibility weaker.
- Editing `gen_*` / `Gen*` files: regeneration will overwrite the fix and leaves no stable maintenance point.

## Examples

### Dart / Flutter

If `gen_demo_api.dart` serializes one field incorrectly, keep the generated client untouched and add a preserved wrapper:

```dart
class DemoApiPatch {
  DemoApiPatch(this._inner, this._transport);

  final DemoApi _inner;
  final ApiTransport _transport;

  Future<DemoFormSubmitResponse> formSubmitFixed(DemoFormSubmitForm form) async {
    final response = await _transport.requestJson(
      ApiRequest(
        routeId: 'api.demo.post.formsubmit',
        method: 'POST',
        path: '/api/demo/form-submit',
        form: {
          'title': form.title,
          'count': form.count.toString(),
          'enabled': form.enabled.toString(),
        },
      ),
    );
    return DemoFormSubmitResponse.fromJson(response as Map<String, Object?>);
  }

  DemoApi get generated => _inner;
}
```

The app imports the preserved wrapper for the affected call and keeps using `ApiClient.demo` for all other routes.

### TypeScript

If a generated route method builds the wrong query string, create a user-owned helper next to the generated client:

```ts
export async function getAbcFixed(
  transport: ApiTransport,
  query: GetAbcQuery,
): Promise<GetAbcResponse> {
  const data = await transport.requestJson({
    routeId: "api.demo.get.abc",
    method: "GET",
    path: "/api/demo/abc",
    query: { arg1: query.arg1, arg2: String(query.arg2) },
  });
  return getAbcResponseFromJson(data);
}
```

Only the failing call site switches to `getAbcFixed(...)`; normal `demoClient` regeneration continues.

### Go

If `routes/api/demo/gen_client.go` encodes one request body incorrectly, add a preserved method in `routes/api/demo/client.go`:

```go
func (c *Client) FormSubmitFixed(ctx context.Context, form FormSubmitForm) (*FormSubmitResponse, error) {
	values := url.Values{}
	values.Set("title", form.Title)
	values.Set("count", strconv.Itoa(form.Count))
	values.Set("enabled", strconv.FormatBool(form.Enabled))

	var out FormSubmitResponse
	if err := c.transport.Do(ctx, runtime.Request{
		RouteID: "api.demo.post.formsubmit",
		Method:  http.MethodPost,
		Path:    "/api/demo/form-submit",
		Form:    values,
	}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
```

The patched method lives in a preserved file and can be deleted after the generator fix lands.

### Kotlin

If a generated binary writer is wrong for one packet, use a preserved route facade method with a raw body fallback:

```kotlin
suspend fun BinaryApi.packetRawFixed(
    trace: String,
    bytes: ByteArray,
): BinaryPacketResponse {
    return transport.request(
        ApiRequest(
            routeId = "api.binary.post.packet",
            method = "POST",
            path = "/api/binary/packet",
            query = mapOf("trace" to trace),
            body = ApiBinaryBody(bytes),
        ),
        BinaryPacketResponse.serializer(),
    )
}
```

This keeps the affected binary workaround local while the generated DTOs, error lookup, and other route methods keep updating.

## Review Rule

Every escape hatch should include a short comment with the generator issue it works around and a deletion condition. The goal is to keep shipping while preserving pressure to fix the generator root cause.
