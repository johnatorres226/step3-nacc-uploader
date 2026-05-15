"""Convert f-string logging to % formatting across the codebase."""

import re
from pathlib import Path

def convert_fstring_logging(content):
    """Convert logger.X(f"...") to logger.X("...", args)."""
    
    def replace_fstring(match):
        """Replace a single f-string logging statement."""
        indent = match.group(1)
        level = match.group(2)
        fstring = match.group(3)
        
        # Remove f" prefix and " suffix
        message = fstring[2:-1]
        
        # Find all {var} patterns
        pattern = r'\{([^}]+)\}'
        variables = re.findall(pattern, message)
        
        if not variables:
            # No variables, just remove the f prefix
            return f'{indent}logger.{level}("{message}")'
        
        # Replace {var} with %s or %d
        converted_message = message
        args = []
        
        for var in variables:
            # Determine format specifier
            if 'len(' in var or '.count' in var or var.isdigit():
                converted_message = converted_message.replace(f'{{{var}}}', '%d', 1)
            else:
                converted_message = converted_message.replace(f'{{{var}}}', '%s', 1)
            args.append(var)
        
        # Build the new logging statement
        if args:
            args_str = ', '.join(args)
            return f'{indent}logger.{level}("{converted_message}", {args_str})'
        else:
            return  f'{indent}logger.{level}("{converted_message}")'
    
    # Pattern to match logger.LEVEL(f"...")
    pattern = r'([ \t]*)logger\.(info|debug|warning|error|critical)\(f"([^"]+)"\)'
    content = re.sub(pattern, replace_fstring, content)
    
    # Also handle logging.LEVEL(f"...")
    pattern = r'([ \t]*)logging\.(info|debug|warning|error|critical)\(f"([^"]+)"\)'
    content = re.sub(pattern, lambda m: f'{m.group(1)}logging.{m.group(2)}("{m.group(3)[2:]}")', content if 'f"' in content else content)
    
    return content


def process_file(file_path):
    """Process a single Python file."""
    print(f"Processing: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if there are any f-string logging statements
        if 'logger.' not in content and 'logging.' not in content:
            print(f"  Skipping (no logging)")
            return
        
        if 'f"' not in content and "f'" not in content:
            print(f"  Skipping (no f-strings)")
            return
        
        original_content = content
        content = convert_fstring_logging(content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated")
        else:
            print(f"  No changes needed")
            
    except Exception as e:
        print(f"  ✗ Error: {e}")


def main():
    """Process all Python files in the project."""
    base_dir = Path(__file__).parent.parent
    
    # Target directories
    target_dirs = [
        base_dir / "src" / "redcap_data",
        base_dir / "src" / "cli",
        base_dir / "src" / "pull_errors" / "src" / "python",
        base_dir / "src" / "pull_identifiers" / "src" / "python",
        base_dir / "src" / "pull_status" / "src" / "python",
        base_dir / "src" / "python-uploader" / "src" / "python",
        base_dir / "src" / "fwcli" / "src" / "python",
    ]
   
    for target_dir in target_dirs:
        if not target_dir.exists():
            print(f"Skipping {target_dir} (does not exist)")
            continue
            
        print(f"\n{'='*60}")
        print(f"Processing directory: {target_dir}")
        print(f"{'='*60}")
        
        for py_file in target_dir.rglob("*.py"):
            process_file(py_file)
    
    print(f"\n{'='*60}")
    print("Conversion complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
