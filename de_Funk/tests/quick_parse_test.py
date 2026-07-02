#!/usr/bin/env python3
"""
Quick test to see what the markdown parser produces.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from de_funk.notebook.parsers.markdown_parser import MarkdownNotebookParser
from pathlib import Path

parser = MarkdownNotebookParser(Path.cwd())
config = parser.parse_file("configs/notebooks/stocks/stock_analysis_v2.md")

print(f"Notebook: {config.notebook.title}")
print(f"Is markdown: {getattr(config, '_is_markdown', False)}")
print(f"Has content blocks: {hasattr(config, '_content_blocks')}")

if hasattr(config, '_content_blocks'):
    print(f"\nContent blocks: {len(config._content_blocks)}")
    for i, block in enumerate(config._content_blocks[:5]):  # Show first 5
        print(f"\nBlock {i+1}:")
        print(f"  Type: {block.get('type')}")
        if block.get('type') == 'markdown':
            content_preview = block.get('content', '')[:100].replace('\n', ' ')
            print(f"  Content preview: {content_preview}...")
        elif block.get('type') == 'exhibit':
            print(f"  Exhibit ID: {block.get('id')}")
            print(f"  Exhibit: {block.get('exhibit')}")

print(f"\nTotal exhibits in config: {len(config.exhibits)}")
