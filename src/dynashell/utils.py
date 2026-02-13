import random
from decimal import Decimal
from importlib import resources as resource_loader
import yaml
import json
import shutil
import os
import types
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
import inspect as inspect

# log_ methods

def log_debug(msg, fire=True):
    if fire:
        print(f"DEBUG   : ",msg)
    pass

def log_inform(msg, fire=True):
    if fire:
        print(f"INFORM  : ",msg)

def log_warning(msg, fire=True):
    if fire:
        print(f"WARNING : ",msg)

def log_error(msg, fire=True):
    if fire:
        print(f"ERROR   : ",msg)

def log_failure(msg, fire=True):
    if fire:
        print(f"FAILURE : ", msg)
        raise Exception(msg)

# is_ methods

def is_dir(chk):

    obj = Path(chk)
    if not obj.exists(): return False
    if not obj.is_dir(): return False
    return True

def is_file(chk):

    obj = Path(chk)
    if not obj.exists(): return False
    if not obj.is_file(): return False
    return True

def is_none(chk):

    return chk is None

def is_val_in(chk, *allow):

    return chk in allow

def is_end_in(chk, *allow):

    for test in allow:
        if chk.endswith(test): return True
    return False

def is_empty(chk):

    if is_none(chk): return True

    return len(chk)==0

def is_callable(chk):

    return callable(chk)
#

def choose(by, *lst, **hsh):

    if (len(hsh)==0)&(len(lst)==1):

        return by if by is not None else lst[0]

    log_failure("Unresolved choice")
    return None

def get_environ(key):

    return os.environ[key]

def set_environ(key, val):

    os.environ[key]=val

def load_file(file):

    if not is_file(file): log_failure(f"File '{file}' does not exist")
    with open(file,'r') as f:
        data=f.read()
    return data

def save_file(file, data):

    create_dir(os.path.dirname(file))
    with open(file,'w') as f:
        f.write(data)
        f.close()

def load_yaml(file):

    if not is_file(file): log_failure(f"File '{file}' does not exist")
    with open(file,'r') as f:
        data = yaml.load(f,Loader=yaml.FullLoader)
    return data

def save_yaml(file, data):

    create_dir(os.path.dirname(file))
    with open(file,'w') as f:
        yaml.dump(data,f,default_flow_style=False)

def dump_yaml(data):

    return yaml.dump(data,None,default_flow_style=False)

def load_json(file):

    if not is_file(file): log_failure(f"File '{file}' does not exist")
    with open(file,'r') as f:
        data = json.load(f,object_hook=decimal_decoder)
    return data

def save_json(file, data, indent=True):

    create_dir(os.path.dirname(file))
    with open(file,'w') as f:
        if indent:
            json.dump(data, f, indent=4, cls=DecimalEncoder)
        else:
            json.dump(data, f, cls=DecimalEncoder)

def dump_json(data):

    return json.dumps(data, indent=4, cls=DecimalEncoder)

def slashed_path(path):

    path = path.replace('\\','/')
    path = path.replace('//','/')
    if path.endswith('/'): path = path[:-1]
    return path

def create_dir(path):

    os.makedirs(path,exist_ok=True)

def clear_dir(path):

    if is_dir(path):

        for filename in os.listdir(path):

            file_path = os.path.join(path,filename)

            try:

                if os.path.isfile(file_path) or os.path.islink(file_path):

                    os.unlink(file_path)

                elif os.path.isdir(file_path):

                    shutil.rmtree(file_path,ignore_errors=True)

            except Exception as e:

                log_failure(f'Failed to delete {file_path}. Reason: {e}')

    else:

        create_dir(path)

def reset_dir(path):

    create_dir(path)
    clear_dir(path)

def remove_dir(path):

    shutil.rmtree(path,onerror = lambda _func,_path,_info : log_error(_info))

def unique_id(chrset, length):

    ret = ""
    for cnt in range(0,length):
        ret += chrset[random.randint(0,len(chrset)-1)]
    return ret

def pretty_print_dict(d, indent=0):

    for key,value in d.items():
        print(' ' * indent + str(key) + ': ', end='')
        if isinstance(value,dict):
            print()
            pretty_print_dict(value,indent+4)
        else:
            print(value)

def extend(obj, ext):

    if ext is None: return

    if type(ext)==dict:

        for mth in ext.keys():
            setattr(obj,mth,types.MethodType(ext[mth],obj))

    if type(ext)==ModuleType:

        hsh = {}
        for mth,fnc in inspect.getmembers(ext,inspect.isfunction):
            if fnc.__module__ == ext.__name__:
                hsh[mth]=fnc
        extend(obj,hsh)

class DecimalEncoder(json.JSONEncoder):

    def default(self,obj):
        if isinstance(obj,Decimal):
            return f"@D:{obj}"
        return super().default(obj)

def decimal_decoder(obj):

    for key,value in obj.items():
        if isinstance(value,str):
            if value.startswith("@D:"): obj[key] = Decimal(value[3:])
    return obj

def load_resource(filename, package=None):

    ret = None

    if package:

        inp_file = (resource_loader.files(package) / filename)

        with inp_file.open("r") as f:
            if filename.endswith('.json'):
                ret = json.load(f,object_hook=decimal_decoder)
            elif filename.endswith('.yaml'):
                ret = yaml.load(f,Loader=yaml.FullLoader)
            else:
                ret = f.read()
    else:

        if filename.endswith('.json'):
            ret = load_json(filename)
        elif filename.endswith('.yaml'):
            ret = load_yaml(filename)
        else:
            ret = load_file(filename)

    if is_none(ret): log_failure(f"Could not load resource '{filename}'")

    return ret

def import_from_string(module_name, source_code):
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(source_code, module.__dict__)
    sys.modules[spec.name] = module
    return module