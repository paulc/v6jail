#!/bin/sh

usage="$0: <name> <ttl> <rtype> <value>"

printf 'zone-begin --\nzone-set -- "%s" "%d" "%s" "%s"\nzone-diff --\nzone-commit --\n' "${1?$usage}" "${2?$usage}" "${3?$usage}" "${4?$usage}" | knotc
