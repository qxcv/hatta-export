#!/bin/bash

# script to convert a Hatta wiki to Markdown-based format that will be accepted
# by gitit

set -e

PANDOC_CMD="pandoc --from html+tex_math_dollars --to markdown+tex_math_dollars+hard_line_breaks"
