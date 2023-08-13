#!/bin/sh

usage="$0: <name>"

printf 'zone-begin --\nzone-unset -- "%s"\nzone-diff --\nzone-commit --\n' "${1?$usage}" | knotc
