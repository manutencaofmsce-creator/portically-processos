"""Import from legacy source without executing it or emitting its content."""
import ast
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from case_store import CaseStore


def extract(source):
    tree=ast.parse(source)
    bundle={n.targets[0].id.lower():ast.literal_eval(n.value) for n in tree.body
            if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
            and n.targets[0].id in {'MAIN','RELATED','TITLE'}}
    fragments={}
    class Extract(ast.NodeVisitor):
        def visit_JoinedStr(self,node):
            for v in node.values:
                if isinstance(v,ast.Constant) and isinstance(v.value,str):
                    fragments[f'{len(fragments):03d}']=v.value
                else: self.visit(v)
        def visit_Constant(self,node):
            if isinstance(node.value,str) and '<' in node.value:
                fragments[f'{len(fragments):03d}']=node.value
    for n in tree.body:
        if isinstance(n,ast.FunctionDef) and n.name in {'validation_html','tab_content'}:
            Extract().visit(n)
    bundle['fragments']=fragments
    return bundle


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('legacy_source',type=Path)
    p.add_argument('--confirm-authorized-import',action='store_true',required=True)
    args=p.parse_args()
    try:
        bundle=extract(args.legacy_source.read_text())
        CaseStore(os.environ.get('DATABASE_URL',''),os.environ.get('DATA_ENCRYPTION_KEY','')).import_once(bundle)
    except Exception:
        print('Import refused or failed. No case contents logged.',file=sys.stderr)
        sys.exit(1)
    print('Protected import committed; existing records preserved.')
