# Synthetic HTTP assertions and secret references

DeviceMesh synthetic HTTP monitors support richer response assertions and authenticated requests without persisting credential values in the control-plane database.

## HTTP monitor configuration

HTTP monitor creation accepts:

- `httpHeaders`: non-sensitive literal headers.
- `httpSecretHeaders`: a mapping from HTTP header name to a secret reference.
- `expectedBodyContains`: an optional bounded substring assertion (1–512 characters).
- the existing `httpMethod`, `expectedStatus`, timeout and interval fields.

Sensitive headers such as `Authorization`, `Cookie`, `Proxy-Authorization`, `X-API-Key`, and header names containing `token`, `secret`, `api-key` or `apikey` must use `httpSecretHeaders`. DeviceMesh rejects attempts to persist those values in `httpHeaders`.

`expectedBodyContains` is not valid for `HEAD` monitors. A missing substring produces the synthetic error kind `assertion`; an unexpected status remains `http_status`.

## Secret reference contract

A secret reference is an opaque identifier matching:

```text
^[A-Za-z0-9._-]{1,128}$
```

For example:

```json
{
  "httpSecretHeaders": {
    "Authorization": "payments-api-token"
  }
}
```

The database stores only `payments-api-token`. It never stores the credential value.

The work API sent to distributed probes also carries only the reference. The backend does not resolve a secret and forward its value to a probe. Each execution location must have the referenced secret provisioned locally.

## Provisioning on backend workers and probes

The default secret directory is:

```text
/run/secrets/devicemesh-synthetics
```

A reference such as `payments-api-token` is resolved first from:

```text
/run/secrets/devicemesh-synthetics/payments-api-token
```

If no file exists, DeviceMesh checks an environment variable derived from the reference:

```text
DEVICEMESH_SYNTHETIC_SECRET_PAYMENTS_API_TOKEN
```

The backend directory can be changed with `DEVICEMESH_SYNTHETIC_SECRET_DIRECTORY`. Distributed probes use the same environment variable for their local directory.

File-backed secrets are read on every check, so replacing the file rotates the value for subsequent executions without changing the monitor definition. Environment-backed rotation requires updating the process environment, normally by restarting the worker/probe with the new secret.

For distributed monitoring, provision the same reference independently at every probe that can execute the monitor. Different probes may deliberately map the same reference to different local values if regional credentials are required.

## Failure and redaction behaviour

If a required secret cannot be resolved:

- the check fails as a bounded `policy` failure;
- the distributed probe emits the generic message `required synthetic secret is not configured`;
- no secret value is included in the result payload;
- HTTP response body assertion failures report only that the expected substring was absent, not the response body;
- secret values are not returned by monitor-list or work APIs.

The operator API may return the configured **reference name**, because it is configuration metadata rather than the secret value.

## Rotation and removal

To rotate a credential without changing DeviceMesh configuration:

1. Replace the corresponding secret file (preferred) or environment value on every relevant executor.
2. For file-backed secrets, the next check uses the replacement automatically. For environment-backed secrets, restart the affected process.
3. Confirm successful synthetic results from all assigned probe locations.
4. Revoke the old credential at the upstream service.

To stop using a credential, first remove or disable the monitor/assignment that references it, then delete the local secret material.

## Security boundaries

Secret references do not make arbitrary destinations safe. Existing synthetic target policy still blocks prohibited local/link-local/reserved targets and validates resolved addresses before connecting. Secret-backed requests therefore inherit the same SSRF boundary as unauthenticated synthetic checks.

Operators should use narrowly scoped, read-only credentials for monitoring endpoints whenever possible and avoid sharing application write credentials with synthetic checks.
