import os
import ast
import re

EXTENSIONS = ('.py', '.html', '.js', '.css')
IGNORE_DIRS = ('__pycache__', 'node_modules', '.git')

def get_python_info(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        doc = ast.get_docstring(tree)
        return doc, classes, funcs
    except Exception:
        return None, [], []

def get_html_js_info(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # very basic JS function extraction
        funcs = re.findall(r'function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(', content)
        funcs += re.findall(r'(?:const|let|var)\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*(?:function|\()', content)
        
        # find title in HTML
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        title = title_match.group(1) if title_match else None
        
        return title, [], list(set(funcs))
    except Exception:
        return None, [], []

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    slides = []
    
    for subdir, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith(EXTENSIONS):
                filepath = os.path.join(subdir, file)
                rel_path = os.path.relpath(filepath, root_dir)
                
                info = ""
                doc, classes, funcs = None, [], []
                
                if file.endswith('.py'):
                    doc, classes, funcs = get_python_info(filepath)
                elif file.endswith(('.html', '.js')):
                    doc, classes, funcs = get_html_js_info(filepath)
                
                slide = f"## File: `{rel_path}`\n\n"
                
                if doc:
                    slide += f"**Description/Title:**\n> {doc.strip().split(chr(10))[0]}\n\n"
                
                if classes:
                    slide += f"**Classes:**\n" + ", ".join([f"`{c}`" for c in classes[:10]]) + ("..." if len(classes)>10 else "") + "\n\n"
                if funcs:
                    slide += f"**Key Functions:**\n" + ", ".join([f"`{f}`" for f in funcs[:15]]) + ("..." if len(funcs)>15 else "") + "\n\n"
                
                try:
                    size = os.path.getsize(filepath)
                    slide += f"**Size:** {size} bytes\n"
                except:
                    pass
                
                slides.append(slide)

    slides.sort()

    out_file = os.path.join(root_dir, 'workspace_analysis.md')
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("````carousel\n")
        f.write("<!-- slide -->\n".join(slides))
        f.write("````\n")
    print(f"Generated {out_file} with {len(slides)} slides.")

if __name__ == "__main__":
    main()
