#!/usr/bin/env python3
"""
Documentation validation script to check for syntax errors and formatting issues.
"""

import os
import re
from pathlib import Path

def validate_markdown_file(file_path: Path) -> list:
    """Validate a markdown file for common issues."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for unclosed code blocks using simple count method
        code_block_count = content.count('```')
        if code_block_count % 2 != 0:
            issues.append(f"Unclosed code block (found {code_block_count} ``` markers)")
            
        # Check for syntax errors in Python code blocks
        python_blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
        for i, block in enumerate(python_blocks):
            try:
                compile(block, f"<{file_path.name}:python_block_{i}>", "exec")
            except SyntaxError as e:
                issues.append(f"Python syntax error in block {i+1}: {e}")
                    
    except Exception as e:
        issues.append(f"Error reading file: {e}")
        
    return issues

def main():
    """Validate all documentation files."""
    docs_dir = Path("docs")
    
    if not docs_dir.exists():
        print("❌ docs/ directory not found")
        return 1
        
    markdown_files = list(docs_dir.glob("*.md"))
    
    if not markdown_files:
        print("❌ No markdown files found in docs/")
        return 1
        
    total_issues = 0
    
    print(f"🔍 Validating {len(markdown_files)} documentation files...\n")
    
    for md_file in sorted(markdown_files):
        print(f"📄 Checking {md_file.name}...")
        issues = validate_markdown_file(md_file)
        
        if issues:
            print(f"  ❌ Found {len(issues)} issue(s):")
            for issue in issues:
                print(f"    - {issue}")
            total_issues += len(issues)
        else:
            print(f"  ✅ No issues found")
        print()
    
    print(f"📊 Summary:")
    print(f"  Files checked: {len(markdown_files)}")
    print(f"  Total issues: {total_issues}")
    
    if total_issues == 0:
        print("🎉 All documentation files are valid!")
        return 0
    else:
        print("⚠️  Some issues found. Please review and fix.")
        return 1

if __name__ == "__main__":
    exit(main())
