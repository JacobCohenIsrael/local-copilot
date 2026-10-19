#!/bin/sh
# Read-only device binding/checks. No mount, format, write, retry or fallback.
set -eu
mode=$1
expected_size=$2
case "$expected_size" in 134217728) ;; *) exit 31;; esac
hex() { od -An -tx1 -v | tr -d ' \n'; }
check_free() {
  devno=$(cat "$1/dev")
  while read -r a b num rest; do [ "$num" != "$devno" ] || return 1; done < /proc/self/mountinfo
  for holder in "$1"/holders/*; do [ ! -e "$holder" ] || return 1; done
  for part in "$1"/"${1##*/}"*; do [ ! -d "$part" ] || return 1; done
  [ "$(cat "$1/ro")" = 0 ]
}
if [ "$mode" = scan ]; then
  marker=$3
  [ "${#marker}" = 1024 ] || exit 32
  found= count=0
  for sys in /sys/block/sd*; do
    [ -d "$sys" ] || continue
    count=$((count + 1)); [ "$count" -le 32 ] || exit 33
    [ "$(cat "$sys/size")" = 262144 ] || continue
    device=/dev/${sys##*/}
    actual=$(dd if="$device" bs=512 count=1 2>/dev/null | hex)
    [ "$actual" = "$marker" ] || continue
    [ -z "$found" ] || exit 34
    check_free "$sys" || exit 35
    found=${sys##*/}
  done
  [ -n "$found" ] || exit 36
  printf '{"device":"/dev/%s","majorMinor":"%s","diskSequence":%s,"logicalBytes":134217728}\n' \
    "$found" "$(cat "/sys/block/$found/dev")" "$(cat "/sys/block/$found/diskseq")"
elif [ "$mode" = release ]; then
  device=$3; sequence=$4; fsuuid=$5
  case "$device" in /dev/sd[a-z]|/dev/sd[a-z][a-z]) ;; *) exit 37;; esac
  sys=/sys/block/${device##*/}
  [ "$(cat "$sys/diskseq")" = "$sequence" ] || exit 38
  [ "$(cat "$sys/size")" = 262144 ] || exit 39
  check_free "$sys" || exit 40
  actual=$(dd if="$device" bs=1 skip=1128 count=16 2>/dev/null | hex)
  [ "$actual" = "$fsuuid" ] || exit 41
  printf '{"releaseCheck":true}\n'
else exit 42
fi
