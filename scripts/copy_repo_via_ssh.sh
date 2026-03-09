#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/copy_repo_via_ssh.sh user@host /remote/path [options]

Options:
  --port PORT           SSH port (default: 22)
  --include-env         Include the local .env file
  --include-instance    Include the local instance/ directory
  --delete              Delete remote files not present locally
  --help                Show this help

Examples:
  scripts/copy_repo_via_ssh.sh root@demo-box /opt/ecc-sheet
  scripts/copy_repo_via_ssh.sh root@demo-box /opt/ecc-sheet --include-env --include-instance
EOF
}

escape_remote_shell_arg() {
  local value="$1"
  printf "'%s'" "${value//\'/\'\"\'\"\'}"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  usage >&2
  exit 1
fi

target_host="$1"
remote_dir="$2"
shift 2

ssh_port="22"
include_env="false"
include_instance="false"
delete_remote="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      ssh_port="${2:-}"
      if [[ -z "$ssh_port" ]]; then
        echo "Missing value for --port" >&2
        exit 1
      fi
      shift 2
      ;;
    --include-env)
      include_env="true"
      shift
      ;;
    --include-instance)
      include_instance="true"
      shift
      ;;
    --delete)
      delete_remote="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for cmd in rsync ssh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync_args=(
  --archive
  --compress
  --human-readable
  --itemize-changes
  --exclude=.git/
  --exclude=.venv/
  --exclude=node_modules/
  --exclude=.pytest_cache/
  --exclude=.ruff_cache/
  --exclude=coverage/
  --exclude=logs/
  --exclude=.DS_Store
  --exclude=__pycache__/
  --exclude=*.pyc
)

if [[ "$include_env" != "true" ]]; then
  rsync_args+=(--exclude=.env)
fi

if [[ "$include_instance" != "true" ]]; then
  rsync_args+=(--exclude=instance/)
fi

if [[ "$delete_remote" == "true" ]]; then
  rsync_args+=(--delete)
fi

escaped_remote_dir="$(escape_remote_shell_arg "$remote_dir")"

echo "Creating remote directory ${remote_dir} on ${target_host}"
ssh -p "$ssh_port" "$target_host" "mkdir -p -- $escaped_remote_dir"

echo "Syncing ${repo_root} to ${target_host}:${remote_dir}"
rsync "${rsync_args[@]}" -e "ssh -p ${ssh_port}" \
  "${repo_root}/" "${target_host}:$escaped_remote_dir/"

echo "Copy complete"
