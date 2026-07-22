#!/usr/bin/env python3
"""
append_timestamps.py - Markdown Documentation Timestamp Injector

Scans the repository for Markdown (.md) files and ensures each file concludes
with a standardized Last Updated / Last Reviewed footer block.
"""

import sys
import re
from pathlib import Path
from datetime import datetime

IGNORE_DIRS = {
    '.git', 'node_modules', '.venv', 'venv', 'env', '.smoke_venv',
    'coverage', 'target', 'build', 'dist', 'bin', '.gemini', '.agent_scratch'
}

FOOTER_PATTERN = re.compile(
    r'<!-- markdownlint-disable MD049 -->\s*---\s*\*Last Updated:\s*[\d\-]+\*\s*\|\s*\*Last Reviewed:\s*[\d\-]+\*'
)

def should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return False

def append_timestamps(root_dir: Path = None):
    if root_dir is None:
        root_dir = Path(__file__).parent.parent.resolve()
        
    today_str = datetime.today().strftime('%Y-%m-%d')
    footer_text = f"\n\n<!-- markdownlint-disable MD049 -->\n---\n*Last Updated: {today_str}* | *Last Reviewed: {today_str}*\n"
    
    print(f"Scanning for Markdown files in {root_dir}...")
    
    count = 0
    updated_count = 0
    
    for md_path in root_dir.rglob('*.md'):
        if should_ignore(md_path):
            continue
            
        count += 1
        content = md_path.read_text(encoding='utf-8')
        
        if not FOOTER_PATTERN.search(content):
            print(f"Appending timestamp footer to {md_path.relative_to(root_dir)}")
            content = content.rstrip()
            md_path.write_text(content + footer_text, encoding='utf-8')
            updated_count += 1
            
    print(f"Done. Scanned {count} files. Injected footers into {updated_count} files.")

if __name__ == '__main__':
    target_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    append_timestamps(target_dir)
