"""First small function task; static admission before a bounded correctness job."""
import ast
import json
from pathlib import Path
import sys

PROMPT = ('Write a Python function fibonacci(n) that returns a list of the first n Fibonacci '
          'numbers, starting with 0, 1. Assume n is a non-negative integer. '
          'For n=0 return []; for n=1 return [0]; for n=7 return [0, 1, 1, 2, 3, 5, 8]. '
          'Return only the function code, optionally in one Python code fence. '
          'Use standard Python without imports, I/O, examples, or top-level calls. '
          'Do not add other requirements or explanations.')
MAX_CODE_BYTES = 32768
ALLOWED = (ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.Assign,
           ast.AnnAssign,ast.AugAssign,ast.For,ast.While,ast.If,ast.Expr,ast.Pass,
           ast.Break,ast.Continue,ast.List,ast.Tuple,ast.Constant,ast.Name,ast.Load,
           ast.Store,ast.BinOp,ast.UnaryOp,ast.Add,ast.Sub,ast.Mult,ast.Mod,
           ast.FloorDiv,ast.USub,ast.UAdd,ast.Compare,ast.Lt,ast.LtE,ast.Gt,ast.GtE,
           ast.Eq,ast.NotEq,ast.And,ast.Or,ast.Not,ast.BoolOp,ast.Subscript,
           ast.Slice,ast.IfExp,ast.ListComp,ast.comprehension,ast.Call,ast.Attribute,
           ast.Raise,ast.keyword)
BUILTINS = {'range':range,'len':len,'list':list,'tuple':tuple,'int':int,
            'enumerate':enumerate,'zip':zip,'ValueError':ValueError,'TypeError':TypeError}
CASES = {0:[],1:[0],2:[0,1],7:[0,1,1,2,3,5,8],10:[0,1,1,2,3,5,8,13,21,34],
         20:[0,1,1,2,3,5,8,13,21,34,55,89,144,233,377,610,987,1597,2584,4181]}


def validate_code(code):
    if not isinstance(code,str) or not 1<=len(code.encode())<=MAX_CODE_BYTES:
        raise ValueError('FUNCTION_CODE_BUDGET')
    tree = ast.parse(code)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
        raise ValueError('ONE_FUNCTION_REQUIRED')
    function = tree.body[0]
    args = function.args
    if (function.name!='fibonacci' or len(args.posonlyargs)+len(args.args)!=1 or
            (args.posonlyargs+args.args)[0].arg!='n' or args.vararg or args.kwarg or
            args.kwonlyargs or args.defaults or args.kw_defaults):
        raise ValueError('FIBONACCI_SIGNATURE_REQUIRED')
    names = {x.name for x in ast.walk(tree) if isinstance(x,ast.FunctionDef)}
    for node in ast.walk(tree):
        if not isinstance(node,ALLOWED): raise ValueError('FUNCTION_NODE_NOT_ALLOWED')
        if isinstance(node,ast.FunctionDef) and (node.decorator_list or node.name.startswith('__')):
            raise ValueError('FUNCTION_DECORATOR_NOT_ALLOWED')
        if isinstance(node,ast.Name) and node.id.startswith('__'):raise ValueError('FUNCTION_NAME_NOT_ALLOWED')
        if isinstance(node,ast.arg) and node.arg.startswith('__'):raise ValueError('FUNCTION_NAME_NOT_ALLOWED')
        if isinstance(node,ast.Attribute) and (node.attr not in ('append','extend') or not isinstance(node.value,ast.Name)):
            raise ValueError('FUNCTION_ATTRIBUTE_NOT_ALLOWED')
        if isinstance(node,ast.Call):
            if not ((isinstance(node.func,ast.Name) and node.func.id in set(BUILTINS)|names) or
                    (isinstance(node.func,ast.Attribute) and node.func.attr in ('append','extend'))):
                raise ValueError('FUNCTION_CALL_NOT_ALLOWED')
    return tree


def code_from_response(response):
    choice = response['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('MODEL_OUTPUT_INCOMPLETE')
    text = choice['message']['content'].strip()
    if text.startswith('```'):
        lines=text.splitlines()
        if len(lines)<3 or lines[0] not in ('```','```python') or lines[-1]!='```':
            raise ValueError('CODE_FENCE_INVALID')
        text='\n'.join(lines[1:-1]).strip()
    text+='\n'
    validate_code(text)
    return text


def evaluate(code):
    tree=validate_code(code)
    namespace={'__builtins__':dict(BUILTINS)}
    exec(compile(tree,'<strata-function>','exec'),namespace)
    passed=[]
    for n,expected in CASES.items():
        actual=namespace['fibonacci'](n)
        if type(actual) is not list or len(actual)!=len(expected) or any(type(x) is not int for x in actual) or actual!=expected:
            raise ValueError('FUNCTION_RESULT_WRONG_'+str(n))
        passed.append(n)
    return {'status':'FUNCTION_CASES_PASSED','inputs':passed}


if __name__=='__main__':
    # The parent uses the existing Windows kill-on-close job: one CPU, one
    # process, 128 MiB, two seconds. Never run admitted model code in the host.
    if len(sys.argv)!=4 or sys.argv[1]!='--evaluate':raise SystemExit('fixed evaluator arguments required')
    code=Path(sys.argv[2]).read_bytes()
    if len(code)>MAX_CODE_BYTES:raise SystemExit('FUNCTION_CODE_BUDGET')
    try:result=evaluate(code.decode('utf-8'))
    except BaseException as error:result={'status':'FUNCTION_CASES_FAILED','errorType':type(error).__name__,'error':str(error)[:256]}
    with Path(sys.argv[3]).open('x',encoding='utf-8') as out:json.dump(result,out)
    raise SystemExit(0 if result['status']=='FUNCTION_CASES_PASSED' else 3)
