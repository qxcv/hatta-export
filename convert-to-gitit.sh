#!/bin/bash

# script to convert a Hatta wiki to Markdown-based format that will be accepted
# by gitit

set -e

OUTPUT_DIR="./hatta/"
FILE_PREFIX="hatta-files"

if [ "$#" != 1 ]; then
    echo "USAGE: $0 <path to Hatta config>"
    exit 1
fi
hatta_config="$1"

echo "Reading from $hatta_config. Will write to $OUTPUT_DIR."
./convert.py \
    --strip-html-link-ext \
    --file-prefix "$FILE_PREFIX" \
    "$hatta_config" "$OUTPUT_DIR"
find "$OUTPUT_DIR" -type f -name '*.html' -not -path "$OUTPUT_PREFIX/$FILE_PREFIX" \
| while read html_path; do
    page_path="$(echo "$html_path" | sed -e 's/\.html$/.page/')"
    echo "$html_path -> $page_path"
    pandoc \
        --from html+tex_math_dollars \
        --to markdown+tex_math_dollars+hard_line_breaks \
        < "$html_path" > "$page_path"
    rm "$html_path"
done
