#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"
require_config
compose "$@"
