# Changelog

## Unreleased

### Breaking changes

- `ksef2 --json invoices metadata --all` now returns an object instead of a bare
  invoice array. Read the merged list from `invoices` and update scripts from
  `jq '.[]'` to `jq '.invoices[]'`. The object also includes `has_more`,
  `is_truncated`, and `permanent_storage_hwm_date` from the final API response,
  plus `page_count`, counting every fetched response, including empty pages.
  Single-page JSON and text output are unchanged.

## v1.1.0 (2026-10-29)

### Added

- Add `ksef2 fa3 schema` to export the public SDK invoice draft JSON schema.
- Add Polish introduction, installation, quickstart, guides and command reference.

### Changed

- Remove the deprecated documentation deployment hook.
