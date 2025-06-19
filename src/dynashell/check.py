from pathlib import Path

def path_exists(path):

    obj = Path(path)
    if not obj.exists(): failure(f"{path} does not exist")
    if not obj.is_dir(): failure(f"{path} is a file")

def path_not_exists(path):

    obj = Path(path)
    if obj.exists(): failure(f"{path} does already exist")

def file_exists(path):

    obj =  Path(path)
    if not obj.exists(): failure(f"{path} does not exist")
    if not obj.is_file(): failure(f"{path} is a directory")

def file_not_exists(path):

    obj = Path(path)
    if obj.exists(): failure(f"{path} does already exist")

def none(chk,msg=None):

    if not msg: msg = "Value must be None"
    if chk is not None: failure(msg)

def not_none(chk,msg=None):

    if not msg: msg = "Value cannot be None"
    if chk is None: failure(msg)

def not_handled(_handled=False):

    if _handled: return
    failure("Request has not been handled")

def handled(_handled=False):

    if _handled: return
    failure("Request has not been handled")

def is_value(val,*allow,msg=None):

    if not msg: msg = f"Value {val} not allowed"
    if not val in allow: failure(msg)

def ends_with(val,*allow,msg=None):

    if not msg: msg = f"Value {val} does not end with ({allow})"
    for test in allow:
        if val.endswith(test): return
    failure(msg)

def is_true(val,msg=None):

    if not msg: msg = "Value must be true"
    if val: return
    failure(msg)

def is_false(val, msg=None):

    if not msg: msg = "Value must be false"
    if not val: return
    failure(msg)

def not_empty(val,msg=None):

    if not msg: msg = "Value cannot be empty"
    if len(val): return
    failure(msg)

def failure(msg):
    raise Exception(msg)