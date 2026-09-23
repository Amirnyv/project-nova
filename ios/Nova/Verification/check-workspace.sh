#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/nova-workspace-check.XXXXXX")
xcrun swiftc -module-cache-path "$check_dir/modules" \
    "$project_dir/Nova/GoogleWorkspaceModels.swift" \
    "$project_dir/Nova/GoogleWorkspaceService.swift" \
    "$project_dir/Nova/GoogleWorkspaceViewModel.swift" \
    "$project_dir/Verification/WorkspaceChecks.swift" \
    -o "$check_dir/workspace-checks"
"$check_dir/workspace-checks"
