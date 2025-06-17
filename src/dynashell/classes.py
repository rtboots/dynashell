import os
import site
import time
import importlib
import traceback
import dynashell.check as check
import dynashell.utils as utils
from   dynashell.utils import choose,extend

class Shell:

    Instance = None

    def __init__(self,line):

        # Set shell instance

        check.none(Shell.Instance,"Only 1 instance of Shell allowed")
        Shell.Instance = self

        # Public properties

        self.startup    = Command(line)
        self.config     = None
        self.command    = None
        self.variable   = Dictionary()
        self.reader     = None
        self.utils      = utils
        self.check      = check

        # Private properties

        self._path      = {}
        self._module    = []
        self._script    = []
        self._counter   = 100
        self._declare   = {}

        # Initialize system and session path

        system_path = utils.slashed_path(os.getcwd())
        self._path['system']=system_path
        session_file = choose(self.startup.flag.session,'./session.yaml')
        session_path = utils.slashed_path(os.path.abspath(os.path.dirname(session_file)))
        self._path['session']=session_path

        # Load session configuration

        self.config = self.load(session_file)

        # Initialize path

        hsh = self.config.get('path',{})
        for key in hsh.keys():
            self._path[key]=utils.slashed_path(self.path(hsh.get(key)))

        # Determine temp path

        if self._path.get('temp') is None:
            self._path['temp'] = self.path("session:/temp")

        utils.reset_path(self._path['temp'])

        # Initialize _module

        lst = self.config.get('module',[])
        for itm in lst:
            pth = utils.slashed_path(self.path(itm))
            self._module.append(pth)
            site.addsitedir(pth)

        # Add temp path to _module

        self._module.append(self._path['temp'])
        site.addsitedir(self._path['temp'])

        # Initialize _script

        lst = self.config.get('script',[])
        for itm in lst:
            pth = utils.slashed_path(self.path(itm))
            self._script.append(pth)

        # Execute start scripts

        lst = self.config.get('start',[])
        for itm in lst:
            time.sleep(0.25)
            self.execute(Command(itm))

        # Start input reader

        self.reader = Reader(self)
        self.reader.start()

    def execute(self,cmnd):

        try:
            self.command = cmnd
            label = cmnd.name
            body  = self.source(cmnd.name)
            file  = self.script(body,label)
            importlib.import_module(file)
        except:
            traceback.print_exc()

    def source(self,name):

        for pth in self._script:
            if utils.file_exists(f"{pth}/{name}"):
                return utils.load_file(f"{pth}/{name}")

        check.failure(f"Could not find script source for '{name}'")

        return None

    def script(self,body,label):

        tmp = ""
        lst = self.config.get('import',[])
        if len(lst):
            tmp += "#Imports\n\n"
            for itm in lst:
                tmp += f"import {itm}\n"
            print("\n")

        tmp += "#Shell \n\n"
        tmp += "from simpleshell.main import instance\n"
        tmp += "sh = instance()\n\n"

        lst = self._declare.keys()
        if len(lst):
            tmp += "# Variables\n\n"
            for itm in lst:
                tmp += f"{itm} = sh.variable.get('{itm}')\n"
            print("\n")

        tmp += f"# Source '{label}\n\n"
        tmp += body

        file = f"script{self._counter}"
        self._counter += 1
        utils.save_file(self.path(f"temp:{file}.py"),tmp)

        return file

    def path(self,val):

        for key in self._path.keys():

            if val.startswith(f"{key}:"):
                val = val[len(key)+1:]
                if not val.startswith("/"): val = f"/{val}"
                return self._path[key]+val

        return val

    def load(self,file):

        file = self.path(file)

        if file.endswith('yaml'):
            return Dictionary.Load(file)
        if file.endswith('json'):
            return Dictionary.Load(file)

        return utils.load_file(file)

    def save(self,file,data):

        file = self.path(file)

        if file.endswith('yaml'):
            utils.save_yaml(file,data)
        elif file.endswith('json'):
            utils.save_json(file,data)
        else:
            utils.save_file(file,data)

    def declare(self,key,val):

        self.variable[key]=val
        self._declare[key]=True

    def extend(self,methods):

        extend(self,methods)

class Reader:

    def __init__(self,shell):

        self._shell   = shell
        self._running = True
        self._stdin   = choose(shell.startup.flag.stdin,True)
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
        self.value = Dictionary(cmd["values"])
        self.flag  = Dictionary(cmd["flags"])

    def see(self,chk):

        if len(self.data):
            return self.data[0]==chk

        return False

    def pop(self):
        if len(self.data):
            return self.data.pop(0)
        else:
            return None

    def done(self):
        return len(self.data)==0

class Dictionary:

    def __init__(self,data=None):

        # NOTE : In order to be able to get AND set dictionary entries
        #        it is necessary to remove all object properties and put the
        #        data hash outside the object (linked via the hash() code)

        Dictionary.Data(hash(self), data)

    def __getattr__(self,key):

        if self.data().get(key):
            val = self.data().get(key)
            #print(f"Getting dictionary key {key} value {val}")
            return Dictionary(val) if isinstance(val,dict) else val
        else:
            return None

    def __setattr__(self,key,val):

        if not key in dir(self):
            #print(f"Setting dictionary key {key} to value {val}")
            self.data()[key]=val
        else:
            tmp = f"Cannot overwrite Dictionary method {key}"
            raise Exception(tmp)

    def __del__(self):

        del Dictionary.Instance[hash(self)]

    def __str__(self):

        return self.dump('json')

    # ----- Partial dict API

    def clear(self):
        self.data().clear()

    def copy(self):

        return Dictionary(self.data().copy())

    def keys(self):
        return self.data().keys()

    def items(self):
        return self.data().items()

    # -----

    def data(self,data=None):

        return Dictionary.Data(hash(self), data)

    def set(self,key,val):

        node = self.data()
        path = key.split(".")
        leaf = path.pop()

        for step in path:

            if node.get(step) is None: node[step]={}
            node = node.get(step)
            if not isinstance(node,dict): check.failure("Expected dict node")

        node[leaf]=val

    def get(self,key,default=None):

        node = self.data()
        path = key.split(".")
        leaf = path.pop()

        for step in path:

            if step in node:
                node = node.get(step)
                if node is None: return default
            else:
                return default

        leaf = node.get(leaf,default)

        return Dictionary(leaf) if isinstance(leaf,dict) else leaf

    def has(self,key):

        return self.data().get(key) is not None

    def load(self,file):

        check.not_none(file)
        check.ends_with(file,'.yaml','.json')

        if file.endswith('yaml'):
            self.data(utils.load_yaml(file))

        if file.endswith('json'):
            self.data(utils.load_json(file))

        return self

    def save(self,file):

        check.not_none(file)
        check.ends_with(file,'.yaml','.json')

        if file.endswith('yaml'):
             utils.save_yaml(file,self.data())

        if file.endswith('json'):
            utils.save_json(file, self.data())

        return self

    def dump(self,typ=None):

        if typ is None:
            if self._file is not None:
                typ = 'yaml' if self._file.endswith('yaml') else 'json'
            else:
                typ = 'json'

        if typ=='yaml': return utils.dump_yaml(self.data())
        if typ=='json': return utils.dump_json(self.data())

        check.failure(f"Unknown dump type '{typ}'")

        return None

    @staticmethod
    def Load(file):

        return Dictionary().load(file)

    @staticmethod
    def Data(code,data=None):

        if Dictionary.Instance.get(code) is None:
            Dictionary.Instance[code] = {}

        if data is not None:
            Dictionary.Instance[code] = data

        return Dictionary.Instance[code]

    Instance = {}

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
            'name': None,
            'text': None,
            'data': [],  # data
            'values': {},  # values
            'flags': {}  # flags
        }

        line = line.strip()
        text = line

        for tok in Tokenizer(line+' ').parse():

            if tok.typ == Token.DATA:
                cmd['data'].append(tok.val)
            if tok.typ == Token.VALUE:
                _, cmd['values'][tok.key] = Tokenizer.Value(tok.val)
            if tok.typ == Token.FLAG:
                _, cmd['flags'][tok.key] = Tokenizer.Value(tok.val)

        name = cmd['data'].pop(0)
        cmd['name'] = name
        cmd['text'] = text[len(name) + 1:].strip()

        return cmd

    @staticmethod
    def Value(txt):

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
