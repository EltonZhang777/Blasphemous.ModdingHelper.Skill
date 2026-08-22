# Use stack-safe sessions for mod test rollback

Status: accepted

Repeated test sessions are allowed because developers often need to deploy a second build before cleaning the first one. Sessions therefore retain their deployment manifests and backups in a newest-first stack; cleaning an older session while a newer session is active is rejected. This preserves rollback safety without blocking iteration, while keeping newly created files out of the default safe clean operation.

## Considered Options

- Reject every new run until the previous session is cleaned.
- Overwrite the previous session state and accept loss of the older rollback point.
- Allow repeated runs while retaining an ordered session stack.

The third option was selected because it supports rapid iteration without silently losing the user's pre-test files.
