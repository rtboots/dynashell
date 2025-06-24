import random
from decimal import Decimal
from importlib import resources as resource_loader
import yaml
import json
import shutil
import os
from pathlib import Path
import types
import dynashell.check as check

def choose(by,*lst,**hsh):

    if (len(hsh)==0)&(len(lst)==1):
        return by if by else lst[0]

    raise Exception("Unresolved choice")

def get_environ(key):

    return os.environ[key]

def set_environ(key,val):

    os.environ[key]=val

def load_file(file):

    check.file_exists(file)
    with open(file,'r') as f:
        data=f.read()
    return data

def save_file(file,data):

    with open(file,'w') as f:
        f.write(data)
        f.close()

def load_yaml(file):

    check.file_exists(file)
    with open(file,'r') as f:
        data = yaml.load(f,Loader=yaml.FullLoader)
    return data

def save_yaml(file,data):

    with open(file,'w') as f:
        yaml.dump(data,f,default_flow_style=False)

def dump_yaml(data):

    return yaml.dump(data,None,default_flow_style=False)

def load_json(file):

    check.file_exists(file)
    with open(file,'r') as f:
        data = json.load(f,object_hook=decimal_decoder)
    return data

def save_json(file,data,indent=True):

    with open(file,'w') as f:
        if indent:
            json.dump(data,f,indent=4,cls=decimal_encoder)
        else:
            json.dump(data,f,cls=decimal_encoder)

def dump_json(data):

    return json.dumps(data,indent=4,cls=decimal_encoder)

def slashed_path(path):

    path = path.replace('\\','/')
    path = path.replace('//','/')
    if path.endswith('/'): path = path[:-1]
    return path

def file_exists(file):

    obj = Path(file)
    return obj.exists() and obj.is_file()

def path_exists(file):
    obj = Path(file)
    return obj.exists() and obj.is_dir()

def create_path(path):

    os.makedirs(path,exist_ok=True)

def clear_path(path):

    if path_exists(path):

        for filename in os.listdir(path):

            file_path = os.path.join(path,filename)

            try:

                if os.path.isfile(file_path) or os.path.islink(file_path):

                    os.unlink(file_path)

                elif os.path.isdir(file_path):

                    shutil.rmtree(file_path,ignore_errors=True)

            except Exception as e:

                print(f'Failed to delete {file_path}. Reason: {e}')

    else:

        create_path(path)

def reset_path(path):

    create_path(path)
    clear_path(path)

def remove_path(path):

    shutil.rmtree(path,onerror = lambda _func,_path,_info : print(_info))

def unique_id(chrset,length):

    ret = ""
    for cnt in range(0,length):
        ret += chrset[random.randint(0,len(chrset)-1)]
    return ret

def pretty_print_dict(d,indent=0):

    for key,value in d.items():
        print(' ' * indent + str(key) + ': ', end='')
        if isinstance(value,dict):
            print()
            pretty_print_dict(value,indent+4)
        else:
            print(value)

def extend(obj,methods):
    if methods is None: return
    for mth in methods.keys():
        setattr(obj,mth,types.MethodType(methods[mth],obj))

class decimal_encoder(json.JSONEncoder):
    def default(self,obj):
        if isinstance(obj,Decimal):
            return f"@D:{obj}"
        return super().default(obj)

def decimal_decoder(obj):
    for key,value in obj.items():
        if isinstance(value,str):
            if value.startswith("@D:"): obj[key] = Decimal(value[3:])
    return obj

def load_resource(package,filename):

    ret = None

    if package:

        inp_file = (resource_loader.files(package) / filename)

        with inp_file.open("rt") as f:
            if filename.endswith('.json'):
                ret=json.load(f, object_hook=decimal_decoder)
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

    check.not_none(ret)

    return ret

