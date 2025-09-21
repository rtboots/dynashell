import os
import site
import sys
import time
import importlib
import traceback
import dynashell.check as check
import dynashell.utils as utils
from   dynashell.utils import extend

class Shell:

    # Shell Instance storage

    Instance = None

    #

    def __init__(self,line):

        # Set shell instance

        check.none(Shell.Instance,"Only 1 instance of Shell allowed")
        Shell.Instance = self

        # Public properties

        self.startup    = Command(line)
        self.config     = None
        self.setting    = {}
        self.command    = None
        self.reader     = None
        self.utils      = utils
        self.check      = check

        # Private properties

        self._path      = {}
        self._module    = []
        self._script    = []
        self._counter   = 100
        self._handler   = {}
        self._variable  = Dictionary()
        self._export    = {
            'startup'   : self.startup
        }

        # Set "system:" path

        system_path = utils.slashed_path(os.getcwd())
        self._path['system']=system_path

        # Get configuration file

        config_file = self.startup.flag.get('config','./config.yaml')

        # Set "shell:" path

        shell_path = utils.slashed_path(os.path.abspath(os.path.dirname(config_file)))
        self._path['shell']=shell_path

        # Load shell configuration

        self.config = self.load(config_file,True)
        self._export['config'] = self.config

        # Process config.path section

        hsh = self.config.get('path',{})
        for key in hsh.keys():
            self._path[key]=utils.slashed_path(self.path(hsh.get(key)))

        # Load dynashell settings

        res = utils.load_resource("dynashell", "setting.yaml")

        platform = 'default'
        for key in res.keys():
            if sys.platform.startswith(key):
                platform=key
                break

        setting = res.get('default',{})
        setting.update(res.get(platform,{}))

        # Process config.setting section

        for itm in self.config.get('setting',[]):
            if '=' in itm:
                key,val = itm.split('=')
                setting[key]=val
            else:
                res = utils.load_resource(None,self.path(itm))
                if res.get('default'):
                    setting.update(res.get('default',{}))
                    setting.update(res.get(platform,{}))
                else:
                    setting.update(res)

        # Create setting object

        self.setting = Setting(setting)
        self._export['setting'] = self.setting

        # Handle USE_READLINE

        if self.setting.USE_READLINE: import readline

        # Determine temp path (for dynascript storage)

        if self._path.get('temp') is None:
            self._path['temp'] = self.path("shell:/temp")

        utils.reset_path(self._path['temp'])

        # Process config.module section

        lst = self.config.get('module',[])
        for itm in lst:
            pth = utils.slashed_path(self.path(itm))
            self._module.append(pth)
            site.addsitedir(pth)

        # Add shell temp path (for dynascript storage) to module locations

        self._module.append(self._path['temp'])
        site.addsitedir(self._path['temp'])

        # Process config.script section

        lst = self.config.get('script',[])
        for itm in lst:
            pth = utils.slashed_path(self.path(itm))
            self._script.append(pth)

        # Execute start scripts

        lst = self.config.get('start',[])
        for itm in lst:
            time.sleep(self.setting.STARTUP_SCRIPT_DELAY)
            self.execute(Command(itm))

        # Start command reader

        self.reader = Reader(self)
        self.reader.start()

    def handler(self,*args): # wrd1,wrd2,fnc

        if len(args)==1:

            for verb,hsh in args[0].items():
                for noun,fnc in hsh.items():
                    self.handler(verb,noun,fnc)

            return

        if len(args)==3:

            (verb,noun,fnc)=args

            if self._handler.get(verb) is None:
                self._handler[verb] = {}

            self._handler[verb][noun] = fnc

            return

    def execute(self,cmnd):

        try:

            self.command = cmnd
            self._export['command'] = cmnd

            # execution by handler

            if self._handler.get(cmnd.name):

                verb = cmnd.name

                star = None

                for noun in self._handler[verb].keys():

                    if cmnd.peek(noun):

                        cmnd.pop()
                        check.is_true(self._handler[verb][noun](verb,noun,cmnd),f"{verb} {noun} has not been handled")
                        return

                    if noun == '*':

                        star = self._handler[verb][noun]

                if star:

                    check.is_true(star(verb,'*',cmnd), f"{verb} * has not been handled")
                    return

            # execution by script

            label  = cmnd.name
            source = self.source(cmnd.name)
            file   = self.script(source,label)
            importlib.import_module(file)

        except:
            traceback.print_exc()

    def source(self,name):

        for pth in self._script:
            if utils.file_exists(f"{pth}/{name}"):

                src = ""
                for line in utils.load_file(f"{pth}/{name}").splitlines():

                    # Macro line
                    if line.startswith("@"):

                        cmnd = Command(line[1:])
                        src += self.__class__.__dict__[f"_{cmnd.name}_"](self,cmnd) +"\n"

                    # Normal line
                    else:

                        src += line+"\n"

                return src

        check.failure(f"Could not find script source for '{name}'")

        return None

    def script(self, source, label):

        tmp = ""

        # Add configured include

        inc = self.config.get('include')

        if inc:
            tmp += "# Configured include\n\n"
            tmp += f"{inc.strip()}\n\n"

        # Add shell instance

        tmp += "# Shell Instance\n\n"
        tmp += "from dynashell.main import instance\n"
        tmp += "shell = instance()\n\n"

        # Add exported variables

        lst = self._export.keys()
        if len(lst):
            tmp += "# Exported variables\n\n"
            for key in lst:
                tmp += f"{key} = shell.export('{key}')\n"
            tmp += "\n"

        # Add script source

        tmp += f"# Source '{label}'\n\n"
        tmp += source

        # Save script to shell's temp directory

        file = f"script{self._counter}"
        self._counter += 1
        utils.save_file(self.path(f"temp:{file}.py"),tmp)

        # Return dynascript filename

        return file

    def path(self,val):

        for key in self._path.keys():

            if val.startswith(f"{key}:"):
                val = val[len(key)+1:]
                if not val.startswith("/"): val = f"/{val}"
                return self._path[key]+val

        return val

    def load(self,file,as_dictionary=False):

        file = self.path(file)

        if file.endswith('yaml'):
            if as_dictionary:
                return Dictionary.Load(file)
            else:
                return utils.load_yaml(file)

        if file.endswith('json'):
            if as_dictionary:
                return Dictionary.Load(file)
            else:
                return utils.load_json(file)

        return utils.load_file(file)

    def save(self,file,data):

        file = self.path(file)

        if file.endswith('yaml'):
            utils.save_yaml(file,data)
        elif file.endswith('json'):
            utils.save_json(file,data)
        else:
            utils.save_file(file,data)

    def export(self,*arg):

        if len(arg)==1:

            key = arg[0]
            return self._export[key]

        if len(arg)==2:

            key,val = arg
            if self._export.get(key):
                raise Exception(f"Cannot re-declare {key}")

            self._export[key]=arg[1]
            return None

        raise Exception("shell.export can only be called with 1 or 2 arguments")

    def extend(self,methods):

        extend(self,methods)

    def set(self,key,val):

        self._variable.set(key, val)

    def get(self,key,default=None):

        return self._variable.get(key, default)

    def has(self,key):

        return self._variable.has(key)

    # macro handlers

    def _include_(self,cmnd):

        return self.source(cmnd.pop())

class Reader:

    def __init__(self,shell):

        self._shell   = shell
        self._running = True
        self._stdin   = shell.startup.flag.get('stdin',True)
        self._lines   = []

    def read_line(self):

        if len(self._lines)!=0:
            return self._lines.pop(0)
        else:
            if self._stdin:
                return input('>')
            else:
                return None

    def append(self,txt):

        self._lines.extend(txt.split("\n"))

    def exit(self):

        self._running = False

    def start(self):

        while self._running:

            line = self.read_line()

            # No more lines to read

            if line is None: return

            # Ignore empty lines and comments

            line = line.strip()
            if len(line)==0: continue
            if line.startswith("#"): continue

            # Exit shell

            if line=='exit': return

            # Execute command

            self._shell.execute(Command(line))

class Command:

    def __init__(self,line):

        cmd = Tokenizer.Parse(line)

        self.name  = cmd["name"]
        self.text  = cmd["text"]
        self.data  = cmd["data"]
        self.value = Dictionary(cmd["value"])
        self.flag  = Dictionary(cmd["flag"])

    def see(self,chk):

        if len(self.data):

            if self.data[0]==chk:
                self.data.pop(0)
                return True
            else:
                return False

        return False

    def pop(self,wrd=None):

        tmp = None

        if len(self.data):
            tmp = self.data.pop(0)

        if wrd is not None:
            if wrd!=tmp:
                check.failure(f"Command expected '{wrd}' but found '{tmp}'")

        return tmp

    def peek(self,wrd):

        if len(self.data):
            return self.data[0]==wrd
        else:
            return False

    def done(self):

        return len(self.data)==0

class Dictionary:

    def __init__(self, hsh=None, lock=False):

        if hsh is None: hsh = {}

        self._data = hsh
        self._lock = lock

    def __getattr__(self, key):

        node, leaf = self.find(key)

        if node:
            return self._cast(node.get(leaf))
        else:
            return None

    def __delattr__(self, item):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot del {item}")

        self._data.pop(item)

    def __str__(self):

        return self.string('json')

    def lock(self):

        self._lock = True

    def data(self):

        return self._data

    def find(self, key, create=False):

        node = self._data
        path = key.split(".")
        leaf = path.pop()

        if create:

            for step in path:

                if step in node:
                    node = node.get(step)
                else:
                    node[step] = {}
                    node = node.get(step)

        else:

            for step in path:

                if step in node:
                    node = node.get(step)
                    if node is None: return None, leaf
                else:
                    return None, leaf

        return node, leaf

    def has(self, key):

        node, leaf = self.find(key)

        if node:
            return leaf in node
        else:
            return False

    def get(self, key, default=None):

        node, leaf = self.find(key)

        if node:
            return self._cast(node.get(leaf, default))
        else:
            return self._cast(default)

    def set(self, key, val):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot set {key}")

        node, leaf = self.find(key)

        if node:
            node[leaf] = val
        else:
            raise Exception(f"Path {key} not added yet")

    def add(self, key, val):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot add {key}")

        node, leaf = self.find(key, True)

        if leaf in node:
            raise Exception(f"Path {key} already added")

        node[leaf] = val

        return self._cast(val)

    # def del(self,key) : is handled by pop()

    def string(self, typ):

        if typ == 'yaml':
            return utils.dump_yaml(self._data)

        return utils.dump_json(self._data)

    # Dict API

    def clear(self):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot clear")

        self._data.clear()

    def copy(self):

        return Dictionary(self._data.copy())

    def items(self, key=None):

        if key: return self.get(key).items()

        ret = list()
        for name, item in self._data.items():
            ret.append((name, self._cast(item)))
        return ret

    def keys(self, key=None):

        if key: return self.get(key).keys()

        return self._data.keys()

    def pop(self, key, default=None):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot pop {key}")

        node, leaf = self.find(key)

        if node:
            return node.pop(leaf, default)
        else:
            raise Exception(f"Path {key} not defined")

    def popitem(self, key):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot popitem {key}")

        node, leaf = self.find(key)

        if node:
            node = node.get(leaf)
            if not isinstance(node, dict):
                raise Exception(f"Path {key} not mapped to dict")
            return node.popitem()
        else:
            raise Exception(f"Path {key} not defined")

    def setdefault(self, key, default=None):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot setdefault {key}")

        node, leaf = self.find(key)

        if node:
            if not isinstance(node, dict):
                raise Exception(f"Path {key} not mapped to dict")
            return node.setdefault(leaf, default)
        else:
            raise Exception(f"Path {key} not defined")

    def update(self, data):

        if self._lock:
            raise Exception(f"Dictionary is locked. Cannot update")

        self._data.update(data)

    def values(self, key=None):

        if key: return self.get(key).values()

        ret = list()
        for item in self._data.values():
            ret.append(self._cast(item))
        return ret

    def load(self, file):

        check.not_none(file)
        check.ends_with(file, '.yaml', '.json')

        if file.endswith('yaml'):
            self._data = utils.load_yaml(file)

        if file.endswith('json'):
            self._data = utils.load_json(file)

        return self

    def save(self, file):

        check.not_none(file)
        check.ends_with(file, '.yaml', '.json')

        if file.endswith('yaml'):
            utils.save_yaml(file, self._data)

        if file.endswith('json'):
            utils.save_json(file, self._data)

        return self

    def _cast(self,obj):

        if isinstance(obj, dict):
            return Dictionary(obj,self._lock)
        else:
            return obj

    @staticmethod
    def Load(file):

        return Dictionary().load(file)

class Setting:

    def __init__(self,data):

        data['__init__']=True
        self._data = data
        data.pop('__init__')

    def __str__(self):

        return f"{self._data}"

    def __getattr__(self,key):

        if not key in self._data.keys(): raise Exception(f"Unknown setting key {key} encountered")

        return self._data.get(key)

    def __setattr__(self, key, value):

        if value.__init__:
             super().__setattr__(key,value)
        else:
            raise Exception("Setting is not allowed to be updated")

    def __setitem__(self, key, value):

        raise Exception("Setting is not allowed to be updated")

class Token:

    DATA    = 1
    VALUE   = 2
    FLAG    = 3

    def __init__(self,typ=None,key=None,val=None):

        self.typ = typ
        self.key = key
        self.val = val

    def __str__(self):

        return f"<type({('','DATA','VALUE','FLAG')[self.typ]},key({self.key}),val({self.val})>"

class Tokenizer:

    def __init__(self,src):

        self.src = src
        self.buf = src
        self.tok = None

    def parse(self):

        lst = []

        while not self.done():

            tok = self.read()
            lst.append(tok)

        return lst

    def read(self):

        if self.scan('--'):

            key = self.read_word()
            val = True
            if self.scan('='): val = self.read_value()
            return Token(typ=Token.FLAG,key=key,val=val)

        else:

            if self.scan('"'):
                return Token(typ=Token.DATA,val=self.read_string('"'))
            if self.scan("'"):
                return Token(typ=Token.DATA,val=self.read_string("'"))

            key = self.read_word()
            if self.scan('='):
                val = self.read_value()
                return Token(typ=Token.VALUE,key=key,val=val)
            else:
                return Token(typ=Token.DATA,val=key)

    def peek(self,checker=None):

        if checker:
            if not self.done():
                return checker(self.buf[0])
            else:
                return False
        else:
            return self.buf[0]

    def next(self):

        ch = self.buf[0]
        self.buf = self.buf[1:]
        return ch

    def done(self):

        return len(self.buf)==0 or self.buf.isspace()

    def trim(self):

        self.buf = self.buf.lstrip()

    def scan(self,tst):

        self.trim()
        if self.buf.startswith(tst):
            self.buf = self.buf[len(tst):]
            return True
        else:
            return False

    def expect(self,ch):

        check.is_value(self.next(),ch)

    def skip_spaces(self):

        while self.peek().isspace(): self.next()

    def read_chars(self,cset):

        tmp = ''
        while self.peek(lambda ch: ch in cset): tmp += self.next()
        return tmp

    def read_word(self):

        word = ''
        while self.peek() not in ' =': word += self.next()
        check.not_empty(word)
        return word

    def read_value(self):

        # String

        if self.scan('"'): return self.read_string('"')
        if self.scan("'"): return self.read_string("'")

        # TODO : [<value>,...,<value>]

        # literal

        tmp = ''
        while self.peek(lambda ch : not ch.isspace()): tmp += self.next()
        return tmp

    def read_string(self,tr):

        tmp = ''
        while self.peek(lambda ch : ch != tr): tmp += self.next()
        self.next()
        return tmp

    @staticmethod
    def Parse(line):

        cmd = {
            'name'  : None,
            'text'  : None,
            'data'  : [],
            'value' : {},
            'flag'  : {}
        }

        line = line.strip()
        text = line

        for tok in Tokenizer(line+' ').parse():

            if tok.typ == Token.DATA:
                cmd['data'].append(tok.val)
            if tok.typ == Token.VALUE:
                _, cmd['value'][tok.key] = Tokenizer.Value(tok.val)
            if tok.typ == Token.FLAG:
                _, cmd['flag'][tok.key] = Tokenizer.Value(tok.val)

        name = cmd['data'].pop(0)
        cmd['name'] = name
        cmd['text'] = text[len(name) + 1:].strip()

        return cmd

    @staticmethod
    def Value(txt):

        if not isinstance(txt,str): return True,txt

        txt = txt.strip()

        if txt=='null'  : return True,None
        if txt=='None'  : return True,None
        if txt=='true'  : return True,True
        if txt=='True'  : return True,True
        if txt=='false' : return True,False
        if txt=='False' : return True,False

        try:
            return True,int(txt)
        except:
            pass

        try:
            return True,float(txt)
        except:
            pass

        if txt.startswith('"') | txt.startswith('\''):
            return True,txt[1:-1]

        return False,txt