# Local storage maintenance (Windows)

These tools preserve active City tasks, Git history and recovery archives. They
do not remove application data, credentials, installed runtimes or main tests.
Plans, archives and reports stay in ignored `artifacts/storage-cleanup/`.

1. Run `.codex-tools/python312/python.exe scripts/maintenance/prepare_worktree_cleanup.py`
   to archive unique changes and prepare the inactive-worktree plan. Inspect the
   resulting plan before removal. Archives are recovery copies, not GitHub commits.
2. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/maintenance/remove_inactive_worktrees.ps1`
   to verify candidates. Add `-Execute` to remove verified inactive copies;
   optionally use `-Limit 3` for a small batch. Changed or inaccessible copies are
   skipped. Recovery refs and archives are retained.
3. Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/maintenance/remove_reproducible_tests.ps1`
   to inspect reproducible cache candidates; add `-Execute` to remove them.
   Tracked files and unexpected paths block removal.

Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/maintenance/test_native_tree_cleanup.ps1`
to check long paths, readonly files and directory-link boundaries using temporary
fixtures. Elevation is optional and should only be used after reviewing the plan
when Windows reports access denied. No global execution policy is changed.
