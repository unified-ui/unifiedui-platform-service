# n8n API Integration — Reference

## Overview

The platform service integrates with n8n's Public REST API to manage workflow executions.
All requests require the `X-N8N-API-KEY` header for authentication.

Base URL pattern: `{n8n_host}/api/{api_version}/` (currently only `v1`).

## Endpoints Used

### GET /executions — List Workflow Runs

Lists workflow executions with optional filtering and cursor-based pagination.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `workflowId` | string | Filter by workflow ID |
| `status` | string | Filter by status: `success`, `error`, `waiting`, `running`, `new`, `canceled` |
| `limit` | int | Max results (default varies, max 250) |
| `cursor` | string | Pagination cursor from `nextCursor` field |
| `includeData` | bool | Include full execution data (input/output) — avoid on list calls |

**Response:**
```json
{
  "data": [
    {
      "id": "4",
      "finished": true,
      "mode": "manual",
      "retryOf": null,
      "retrySuccessId": null,
      "status": "success",
      "startedAt": "2026-03-15T09:08:50.765Z",
      "stoppedAt": "2026-03-15T09:08:50.770Z",
      "workflowId": "fpYuPhtG3XWAja14",
      "waitTill": null
    }
  ],
  "nextCursor": "eyJsYXN0SWQiOiIzIiwibGltaXQiOjJ9"
}
```

**Pagination model:** Cursor-based. `nextCursor` is `null` when no more pages. Pass `cursor` param on subsequent requests.

**Status values observed:** `success`, `error`, `waiting`, `running`, `new`, `canceled`.

### GET /executions/{id} — Get Execution Detail

Returns a single execution with optional full data.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `includeData` | bool | Include `data` and `workflowData` fields |

**Response (with `includeData=true`):**
```json
{
  "id": "4",
  "finished": true,
  "mode": "manual",
  "retryOf": null,
  "retrySuccessId": null,
  "status": "success",
  "createdAt": "2026-03-15T09:08:50.758Z",
  "startedAt": "2026-03-15T09:08:50.765Z",
  "stoppedAt": "2026-03-15T09:08:50.770Z",
  "deletedAt": null,
  "workflowId": "fpYuPhtG3XWAja14",
  "waitTill": null,
  "data": {
    "version": 1,
    "startData": {},
    "resultData": {
      "runData": {
        "NodeName": [{ "startTime": 123, "executionTime": 1, "executionStatus": "success", "data": {} }]
      },
      "pinData": {},
      "lastNodeExecuted": "Execute Command"
    },
    "executionData": { "contextData": {}, "metadata": {} }
  },
  "workflowData": {
    "id": "fpYuPhtG3XWAja14",
    "name": "My workflow",
    "active": false,
    "nodes": [{ "name": "Webhook", "type": "n8n-nodes-base.webhook" }]
  }
}
```

**Note:** The detail response includes `createdAt` and `deletedAt` fields not present in list items.

### POST /executions/{id}/retry — Retry Execution

Retries a **failed** execution. Cannot retry successful executions.

**Response (success already):**
```json
{ "message": "The execution succeeded, so it cannot be retried." }
```

**Response (retry triggered):**
```json
{ "data": { "id": "5", "retried": true } }
```

**Note:** Only executions with `status: "error"` can be retried.

## Integration Architecture

```
Frontend → Platform Service → n8n API
         (generic endpoints)   (type-specific implementation)
```

The platform service provides generic workflow endpoints. Internally, a factory pattern dispatches to type-specific handlers (currently only N8N). This allows adding other workflow engines (Airflow, Temporal, etc.) without changing the API contract.

## Configuration

n8n connection details are stored in the autonomous agent's `config` field:

| Config Key | Description |
|------------|-------------|
| `api_version` | n8n API version (currently `v1`) |
| `workflow_endpoint` | Full URL like `http://host:port/workflow/{workflowId}` |
| `api_api_key_credential_id` | Credential ID for API key (stored in vault) |
| `webhook_url` | Optional webhook URL for triggering workflows |

The `workflow_endpoint` is parsed to extract `n8n_host` and `workflow_id`.

## Error Handling

- **Vault unavailable**: Returns empty results (no crash). Log error.
- **n8n unreachable**: Returns empty results with HTTP error log.
- **Unsupported agent type**: Raises `UnsupportedAutonomousAgentTypeError` (400).
- **Retry on success**: n8n returns specific message (not an HTTP error).
