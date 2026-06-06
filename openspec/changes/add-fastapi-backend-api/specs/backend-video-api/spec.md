---
capability: backend-video-api
type: new
---

# Spec：backend-video-api

## ADDED Requirements

### Requirement: Health endpoint
The system SHALL expose `GET /health` returning `{ "ok": true }`.

#### Scenario: Health check succeeds
- **WHEN** a client requests `GET /health`
- **THEN** the response status is 200
- **AND** the response body is `{ "ok": true }`

### Requirement: Job persistence
The system SHALL persist jobs in SQLite with the existing editable job shape.

#### Scenario: Job is created and fetched
- **WHEN** a client creates a job
- **THEN** the system stores `id`, `name`, `theme`, `width`, `steps`, `createdAt`, and `updatedAt`
- **AND** a later fetch returns the same editable shape

### Requirement: Job listing order
The system SHALL list jobs ordered by `updatedAt` descending.

#### Scenario: Recently updated job appears first
- **WHEN** an older job is updated after a newer job was created
- **THEN** the updated job appears first in `GET /api/jobs`

### Requirement: Job CRUD
The system SHALL support create, read, update, and delete operations for jobs.

#### Scenario: Job lifecycle is managed through API
- **WHEN** a client creates, updates, fetches, and deletes a job
- **THEN** each operation returns the expected status
- **AND** fetching the deleted job returns 404

### Requirement: Job import
The system SHALL import a job from `configJson` and matching cpp file contents.

#### Scenario: Valid config and cpp files create a job
- **WHEN** a client posts valid `configJson` and all required cpp file contents
- **THEN** the system creates a job whose steps contain the matching `fileContent`

### Requirement: Missing import files
The system SHALL reject import requests when a required cpp file is missing.

#### Scenario: Missing cpp file is rejected
- **WHEN** a config step references a cpp file absent from `cppFiles`
- **THEN** the response status is 400
- **AND** the response explains which file is missing

### Requirement: Mock draft generation
The system SHALL create a mock generated draft job from problem statement and solution code.

#### Scenario: Draft generation returns editable job
- **WHEN** a client posts a problem statement and solution code
- **THEN** the system creates a job with editable steps
- **AND** the final step contains the full solution code

### Requirement: Render job creation
The system SHALL create render jobs for non-empty jobs.

#### Scenario: Non-empty job starts render
- **WHEN** a client creates a render job for a job with at least one step
- **THEN** the response status is 201
- **AND** the response contains a render job id with status `queued`

### Requirement: Render job statuses
The system SHALL expose render job status as `queued`, `running`, `succeeded`, or `failed`.

#### Scenario: Render status is fetched
- **WHEN** a client requests a render job status
- **THEN** the response contains one of the supported statuses

### Requirement: Render download gating
The system SHALL reject MP4 download before a render job has succeeded.

#### Scenario: Download before completion is rejected
- **WHEN** a client requests download for a render job that is not `succeeded`
- **THEN** the response status is 409

### Requirement: Duplicate cpp conflict
The system SHALL reject render export when duplicate cpp file labels contain different content.

#### Scenario: Conflicting duplicate file labels are rejected
- **WHEN** two steps use the same `fileLabel` with different `fileContent`
- **THEN** render export validation fails

### Requirement: Backend-backed frontend storage
The frontend SHALL use the backend API as the primary job storage.

#### Scenario: Editor loads job from API
- **WHEN** a user opens a job edit route
- **THEN** the frontend fetches the job through the backend API

### Requirement: Client-side preview
The frontend SHALL keep Remotion preview client-side and independent from backend render completion.

#### Scenario: Editing updates preview before render
- **WHEN** a user edits a job step
- **THEN** the preview can update from the local edited job state without waiting for MP4 render
