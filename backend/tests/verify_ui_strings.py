"""
UI String Verification Script (Windows Compatible)
Extracts and verifies all English strings in partition UI components
"""
import os
import re
import sys

def extract_strings_from_jsx(filepath):
    """Extract English strings from JSX file"""
    strings_found = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
            
            # Pattern 1: Strings in quotes (excluding imports and technical strings)
            # Look for user-facing text
            patterns = [
                r'>\s*([A-Z][a-zA-Z\s,.:!?-]{3,})\s*<',  # Text between tags
                r'title\s*=\s*["\']([^"\']+)["\']',  # title attributes
                r'placeholder\s*=\s*["\']([^"\']+)["\']',  # placeholder attributes
                r'label\s*=\s*["\']([^"\']+)["\']',  # label attributes
                r'text\s*=\s*["\']([^"\']+)["\']',  # text props
                r'message\s*=\s*["\']([^"\']+)["\']',  # message props
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    text = match.group(1).strip()
                    # Filter out technical strings, imports, etc.
                    if (len(text) > 3 and 
                        not text.startswith('import') and
                        not text.startswith('from') and
                        not text.endswith('.jsx') and
                        not text.endswith('.js') and
                        not '/' in text and
                        not text.isupper() and  # Skip constants
                        any(c.isalpha() for c in text)):  # Has letters
                        strings_found.append({
                            'line': line_num,
                            'text': text,
                            'context': line.strip()[:80]
                        })
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return strings_found

def verify_ui_strings():
    """Main verification function"""
    print("=" * 80)
    print("UI STRING VERIFICATION (Windows Compatible)")
    print("=" * 80)
    
    # Define partition component directory
    partition_dir = os.path.join('frontend', 'src', 'components', 'partition')
    
    if not os.path.exists(partition_dir):
        print(f"\n✗ Partition directory not found: {partition_dir}")
        return False
    
    print(f"\nScanning directory: {partition_dir}")
    print("-" * 80)
    
    # Get all JSX files
    jsx_files = []
    for filename in os.listdir(partition_dir):
        if filename.endswith('.jsx') or filename.endswith('.js'):
            jsx_files.append(os.path.join(partition_dir, filename))
    
    if not jsx_files:
        print("✗ No JSX files found in partition directory")
        return False
    
    print(f"Found {len(jsx_files)} JSX file(s):")
    for f in jsx_files:
        print(f"  - {os.path.basename(f)}")
    
    # Extract strings from each file
    all_strings = {}
    total_strings = 0
    
    for filepath in jsx_files:
        print(f"\n[Analyzing: {os.path.basename(filepath)}]")
        print("-" * 80)
        
        strings = extract_strings_from_jsx(filepath)
        
        if strings:
            all_strings[filepath] = strings
            total_strings += len(strings)
            print(f"Found {len(strings)} user-facing string(s):")
            
            for s in strings:
                print(f"\n  Line {s['line']}:")
                print(f"    Text: \"{s['text']}\"")
                print(f"    Context: {s['context']}")
        else:
            print("  ✓ No English strings found (likely already in PT-BR)")
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Files scanned: {len(jsx_files)}")
    print(f"Total strings found: {total_strings}")
    
    if total_strings > 0:
        print("\n⚠ WARNING: English strings detected in UI components")
        print("These strings should be translated to PT-BR:")
        print("-" * 80)
        
        for filepath, strings in all_strings.items():
            print(f"\n{os.path.basename(filepath)}:")
            for s in strings:
                print(f"  Line {s['line']}: \"{s['text']}\"")
        
        print("\n" + "=" * 80)
        print("TRANSLATION REQUIRED")
        print("=" * 80)
        return False
    else:
        print("\n✓ SUCCESS: All UI strings appear to be in PT-BR or are technical")
        print("=" * 80)
        return True

if __name__ == "__main__":
    try:
        success = verify_ui_strings()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
