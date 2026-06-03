import re

def check_jsx_tags(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex to find JSX tags: <Tag ...> or </Tag>
    # Avoid matching inside strings or comments
    # To keep it robust, we'll scan the file and maintain a stack
    stack = []
    
    # We can use a simplified tokenizer or parser for tags
    tag_pattern = re.compile(r'<(/?[a-zA-Z][a-zA-Z0-9\-\.]*)(?:\s+[^>]*?)?(/?)(?=>|$)')
    
    # Let's clean comments first to avoid false matches
    # Replace {/* ... */} and // comments with spaces
    # {/* ... */} comments
    content_clean = re.sub(r'\{\s*/\*.*?\*/\s*\}', lambda m: ' ' * len(m.group(0)), content, flags=re.DOTALL)
    # /* ... */ comments
    content_clean = re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group(0)), content_clean, flags=re.DOTALL)
    # // comments
    content_clean = re.sub(r'//.*$', lambda m: ' ' * len(m.group(0)), content_clean, flags=re.MULTILINE)
    
    # Find tags
    pos = 0
    line_offsets = []
    for line in content.splitlines(True):
        line_offsets.append(pos)
        pos += len(line)
        
    def get_line_col(index):
        line_idx = 0
        for i, offset in enumerate(line_offsets):
            if index >= offset:
                line_idx = i
            else:
                break
        return line_idx + 1, index - line_offsets[line_idx] + 1
        
    for match in re.finditer(r'<(/?[a-zA-Z][a-zA-Z0-9\-\.]*)', content_clean):
        tag_name = match.group(1)
        start_idx = match.start()
        
        # find matching >
        end_idx = content_clean.find('>', start_idx)
        if end_idx == -1:
            continue
            
        full_tag = content_clean[start_idx:end_idx+1]
        line, col = get_line_col(start_idx)
        
        # Check if self-closing
        if full_tag.endswith('/>') or tag_name in ['input', 'img', 'br', 'hr']:
            continue
            
        if tag_name.startswith('/'):
            # Closing tag
            real_name = tag_name[1:]
            if not stack:
                print(f"Extra closing tag </{real_name}> at line {line}, col {col}")
            else:
                top_name, top_line, top_col = stack.pop()
                if top_name != real_name:
                    print(f"Mismatched closing tag </{real_name}> at line {line}, col {col} (matches <{top_name}> at line {top_line}, col {top_col})")
        else:
            # Opening tag
            stack.append((tag_name, line, col))
            
    if stack:
        print("Unclosed JSX tags:")
        for name, l, c in stack:
            print(f"  <{name}> at line {l}, col {c}")
    else:
        print("All JSX tags match perfectly!")

check_jsx_tags("c:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx")
