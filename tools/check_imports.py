import ast, os, sys
LOCAL = ('utils', 'core', 'services', 'models')

def top_names(path):
    out = set()
    for n in ast.parse(open(path).read()).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                out.update(x.id for x in ast.walk(t) if isinstance(x, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split('.')[0] for a in n.names)
    return out

bad = []
files = ['app.py'] + [os.path.join(d, f) for d in LOCAL for f in os.listdir(d) if f.endswith('.py')]
for f in files:
    for n in ast.walk(ast.parse(open(f).read())):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split('.')[0] in LOCAL:
            p = n.module.replace('.', '/') + '.py'
            if os.path.exists(p):
                have = top_names(p)
                bad += [f + ':' + str(n.lineno) + ' imports ' + a.name + ' from ' + n.module
                        for a in n.names if a.name != '*' and a.name not in have]
print(os.linesep.join(bad) if bad else 'all local imports resolve')
sys.exit(1 if bad else 0)