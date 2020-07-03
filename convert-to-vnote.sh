#!/bin/bash

# script to convert a Hatta wiki to Markdown-based format that will be accepted
# by VNote

set -e

OUTPUT_DIR="./Wiki/"
FILE_PREFIX="_v_images"

if [ "$#" != 1 ]; then
    echo "USAGE: $0 <path to Hatta config>"
    exit 1
fi
hatta_config="$1"

echo "Reading from $hatta_config. Will write to $OUTPUT_DIR."
./convert.py \
    --add-link-ext .md \
    --files-in-one-dir \
    --file-prefix "$FILE_PREFIX" \
    "$hatta_config" "$OUTPUT_DIR"
find "$OUTPUT_DIR" -type f -name '*.html' -not -path "$OUTPUT_PREFIX/$FILE_PREFIX" \
| while read html_path; do
    page_path="$(echo "$html_path" | sed -e 's/\.html$/.md/')"
    echo "$html_path -> $page_path"
    pandoc \
        --from html+tex_math_dollars \
        --to markdown+tex_math_dollars+hard_line_breaks \
        < "$html_path" > "$page_path"
    rm "$html_path"
done

# this is necessary to make VNote recognise the output dir as a notebook
touch "$OUTPUT_DIR/fake.md"
