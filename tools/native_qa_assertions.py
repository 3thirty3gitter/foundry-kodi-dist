"""Test-only generation hardener. Never apply to shipped production modules."""
import ast

def harden_qa_source(source):
    tree = ast.parse(source)
    assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    if not assertions:
        return source
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    alias = '_foundry_qa_assertions_builtins'
    while alias in names:
        alias += '_'
    class Harden(ast.NodeTransformer):
        def visit_Assert(self, node):
            error = ast.Attribute(value=ast.Name(id=alias, ctx=ast.Load()), attr='AssertionError', ctx=ast.Load())
            args = [] if node.msg is None else [node.msg]
            replacement = ast.If(test=ast.UnaryOp(op=ast.Not(), operand=node.test),
                body=[ast.Raise(exc=ast.Call(func=error, args=args, keywords=[]), cause=None)], orelse=[])
            return ast.copy_location(replacement, node)
    tree = Harden().visit(tree)
    # Keep module docstring and all future imports in their mandatory initial position.
    index = 0
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        index = 1
    while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body.insert(index, ast.Import(names=[ast.alias(name='builtins', asname=alias)]))
    ast.fix_missing_locations(tree)
    result = ast.unparse(tree) + '\n'
    if any(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(result))):
        raise RuntimeError('QA assertion hardening incomplete')
    compile(result, '<hardened-native-qa>', 'exec', optimize=2)
    return result
