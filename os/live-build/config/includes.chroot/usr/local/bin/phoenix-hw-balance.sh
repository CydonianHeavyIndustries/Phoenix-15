#!/bin/sh
set -e

ROLE="${1:-generic}"
LOG_PATH="/var/log/phoenix_hw_balance.log"
POLICY_PATH="/etc/phoenix/hardware_policy.json"

_log() {
  TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)
  echo "[$TS] $*" >> "$LOG_PATH" 2>/dev/null || true
}

_cpu_total() {
  CPU_TOTAL=$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)
  if [ -z "$CPU_TOTAL" ]; then
    CPU_TOTAL=$(nproc 2>/dev/null || true)
  fi
  if [ -z "$CPU_TOTAL" ] || [ "$CPU_TOTAL" -lt 1 ]; then
    CPU_TOTAL=1
  fi
  echo "$CPU_TOTAL"
}

_cpu_range() {
  CPU_TOTAL="$1"
  START="$2"
  END="$3"
  if [ "$START" -lt 0 ]; then
    START=0
  fi
  if [ "$END" -lt "$START" ]; then
    END="$START"
  fi
  if [ "$END" -ge "$CPU_TOTAL" ]; then
    END=$((CPU_TOTAL - 1))
  fi
  echo "${START}-${END}"
}

_detect_gpus() {
  GPU_COUNT=0
  GPU_LIST=""
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_COUNT=$(nvidia-smi -L 2>/dev/null | wc -l | tr -d ' ')
  elif [ -d /proc/driver/nvidia/gpus ]; then
    GPU_COUNT=$(ls /proc/driver/nvidia/gpus 2>/dev/null | wc -l | tr -d ' ')
  fi
  if [ -z "$GPU_COUNT" ] || [ "$GPU_COUNT" -lt 1 ]; then
    GPU_COUNT=0
  fi
  if [ "$GPU_COUNT" -gt 0 ]; then
    i=0
    while [ "$i" -lt "$GPU_COUNT" ]; do
      if [ -z "$GPU_LIST" ]; then
        GPU_LIST="$i"
      else
        GPU_LIST="${GPU_LIST},${i}"
      fi
      i=$((i + 1))
    done
  fi
  echo "${GPU_COUNT}|${GPU_LIST}"
}

CPU_TOTAL=$(_cpu_total)
CPU_MID=$((CPU_TOTAL / 2))
if [ "$CPU_MID" -lt 1 ]; then
  CPU_MID=1
fi
CPU_LAST=$((CPU_TOTAL - 1))

PHX_CPUSET="0-${CPU_LAST}"
PHX_CPU_THREADS="$CPU_TOTAL"
case "$ROLE" in
  backend)
    if [ "$CPU_TOTAL" -gt 1 ]; then
      PHX_CPUSET=$(_cpu_range "$CPU_TOTAL" 0 $((CPU_MID - 1)))
      PHX_CPU_THREADS="$CPU_MID"
    fi
    ;;
  ui)
    if [ "$CPU_TOTAL" -gt 1 ]; then
      PHX_CPUSET=$(_cpu_range "$CPU_TOTAL" "$CPU_MID" "$CPU_LAST")
      PHX_CPU_THREADS=$((CPU_TOTAL - CPU_MID))
      if [ "$PHX_CPU_THREADS" -lt 1 ]; then
        PHX_CPU_THREADS=1
      fi
    fi
    ;;
  sync|data)
    if [ "$CPU_TOTAL" -gt 2 ]; then
      PHX_CPUSET=$(_cpu_range "$CPU_TOTAL" "$CPU_LAST" "$CPU_LAST")
      PHX_CPU_THREADS=1
    fi
    ;;
esac

GPU_INFO=$(_detect_gpus)
PHX_GPU_COUNT=$(echo "$GPU_INFO" | cut -d'|' -f1)
PHX_GPU_LIST=$(echo "$GPU_INFO" | cut -d'|' -f2)
PHX_GPU_MODE="balanced"

if [ -f "$POLICY_PATH" ] && command -v jq >/dev/null 2>&1; then
  MODE=$(jq -r '.gpu_mode // empty' "$POLICY_PATH" 2>/dev/null || true)
  if [ -n "$MODE" ]; then
    PHX_GPU_MODE="$MODE"
  fi
fi

if [ "$PHX_GPU_COUNT" -gt 0 ]; then
  case "$PHX_GPU_MODE" in
    primary)
      export CUDA_VISIBLE_DEVICES="0"
      ;;
    secondary)
      if [ "$PHX_GPU_COUNT" -gt 1 ]; then
        export CUDA_VISIBLE_DEVICES="1"
      else
        export CUDA_VISIBLE_DEVICES="0"
      fi
      ;;
    balanced|all|"")
      export CUDA_VISIBLE_DEVICES="$PHX_GPU_LIST"
      ;;
  esac
  export NVIDIA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-$PHX_GPU_LIST}"
fi

export PHX_CPUSET
export PHX_CPU_THREADS
export PHX_GPU_COUNT
export PHX_GPU_LIST
export PHX_GPU_MODE
export OMP_NUM_THREADS="$PHX_CPU_THREADS"
export OPENBLAS_NUM_THREADS="$PHX_CPU_THREADS"
export MKL_NUM_THREADS="$PHX_CPU_THREADS"

_log "role=${ROLE} cpu_total=${CPU_TOTAL} cpuset=${PHX_CPUSET} cpu_threads=${PHX_CPU_THREADS} gpu_count=${PHX_GPU_COUNT} gpu_list=${PHX_GPU_LIST} gpu_mode=${PHX_GPU_MODE}"
