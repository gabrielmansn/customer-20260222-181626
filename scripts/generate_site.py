#!/usr/bin/env python3
"""
Generates a professional website for a Finnish service business using Claude AI.

Reads:
  - order.json       (customer order data from Formspree)
  - prompts/site.txt (system prompt / instructions for Claude)

Writes to current directory:
  - index.html
  - style.css
  - main.js
  - images/ (if referenced)
"""

import json
import os
import re
import sys

import anthropic


def load_files():
    """Load order data and prompt template from disk."""
    order_file = "order.json"
    if not os.path.exists(order_file):
        print(f"ERROR: {order_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(order_file, "r", encoding="utf-8") as f:
        order = json.load(f)

    prompt_file = "prompts/site.txt"
    if not os.path.exists(prompt_file):
        print(f"ERROR: {prompt_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    return order, prompt_template


def build_prompt(order: dict, prompt_template: str) -> str:
    """Combine the prompt template with the order data."""
    order_json = json.dumps(order, ensure_ascii=False, indent=2)

    return f"""{prompt_template}

---

## TILAUKSEN TIEDOT

Asiakkaan lomakkeelta saadut tiedot JSON-muodossa:

```json
{order_json}
```

Luo nyt täydellinen verkkosivusto yllä olevien ohjeiden ja tilauksen tietojen perusteella.

Merkitse jokainen tiedosto selkeästi käyttäen muotoa:
=== tiedostonimi ===
(tiedoston sisältö tähän)

Tarvittavat tiedostot: index.html, style.css, main.js
"""


def parse_response(content: str) -> dict[str, str]:
    """
    Parse Claude's response and extract individual files.

    Supports the '=== filename ===' section format as specified in the prompt.
    Falls back to other common patterns if needed.
    """
    files = {}

    # Primary format: === filename ===
    parts = re.split(r'===\s*([^\s=][^=\n]*?)\s*===', content)

    if len(parts) > 1:
        # parts: [preamble, filename1, content1, filename2, content2, ...]
        for i in range(1, len(parts), 2):
            filename = parts[i].strip()
            file_content = parts[i + 1].strip() if i + 1 < len(parts) else ""

            # Strip surrounding code fences (```html ... ``` etc.)
            file_content = re.sub(r'^```[a-zA-Z]*\n?', '', file_content)
            file_content = re.sub(r'\n?```\s*$', '', file_content.rstrip())

            if filename and file_content:
                files[filename] = file_content.strip()

    # Fallback 1: markdown headings followed by code blocks
    # e.g. "### index.html\n```html\n...\n```"
    if not files:
        pattern = re.compile(
            r'(?:#{1,4}\s*|`{3}[a-z]*\n)([a-zA-Z0-9_.\-/]+\.[a-zA-Z]+)\n```[a-zA-Z]*\n(.*?)```',
            re.DOTALL
        )
        for m in pattern.finditer(content):
            files[m.group(1).strip()] = m.group(2).strip()

    # Fallback 2: any labelled code blocks  **index.html**  followed by ```
    if not files:
        pattern = re.compile(
            r'\*\*([a-zA-Z0-9_.\-/]+\.[a-zA-Z]+)\*\*\s*\n```[a-zA-Z]*\n(.*?)```',
            re.DOTALL
        )
        for m in pattern.finditer(content):
            files[m.group(1).strip()] = m.group(2).strip()

    # Last resort: save raw response as index.html so something is always produced
    if not files:
        print(
            "WARNING: Could not parse named file sections — saving full response as index.html",
            file=sys.stderr
        )
        files["index.html"] = content

    return files


def write_files(files: dict[str, str]) -> list[str]:
    """Write parsed files to disk and return list of written filenames."""
    written = []

    for filename, content in files.items():
        # Only allow safe relative paths — no directory traversal
        clean = os.path.normpath(filename)
        if clean.startswith(".."):
            print(f"SKIP: unsafe path '{filename}'", file=sys.stderr)
            continue

        # Create subdirectories if needed (e.g. images/)
        parent = os.path.dirname(clean)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(clean, "w", encoding="utf-8") as f:
            f.write(content)

        written.append(clean)
        print(f"  Written: {clean}  ({len(content):,} chars)")

    return written


def main():
    print("=== Site generator starting ===")

    print("Loading order.json and prompts/site.txt...")
    order, prompt_template = load_files()
    print(f"Order fields: {list(order.keys())}")

    print("Building prompt...")
    prompt = build_prompt(order, prompt_template)
    print(f"Prompt length: {len(prompt):,} chars")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)

    print("Calling Claude API (claude-opus-4-5)...")
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.content[0].text
    print(f"Response received: {len(content):,} chars  |  stop_reason: {response.stop_reason}")

    print("Parsing response into files...")
    files = parse_response(content)
    print(f"Files found: {list(files.keys())}")

    print("Writing files...")
    written = write_files(files)

    print(f"\n=== Done! Generated {len(written)} file(s): {', '.join(written)} ===")


if __name__ == "__main__":
    main()
