import os
import site
import sys
import time
import importlib
import traceback
import atexit
from textwrap import dedent
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
        self._source    = []
        self._counter   = 100
        self._handler   = {}
        self._declare   = Dictionary()
        self._declare.startup = self.startup
        self._variable  = Dictionary()

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
        self._declare.config=self.config

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

        self.setting = Dictionary(setting)
        self._declare.setting = self.setting

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

        lst = self.config.get('source',[])
        for itm in lst:
            pth = utils.slashed_path(self.path(itm))
            self._source.append(pth)

        # Execute STARTUP scripts
        # NOTE : Use config.source so we get ':' paths instead of absolute resolved ones

        for pth in self.config.get('source',[]):
            time.sleep(float(self.setting.SCRIPT_EXECUTION_DELAY))
            self.dynaload(self.source(f"{pth}/STARTUP",True))

        # Execute startup scripts

        lst = self.config.get('startup',[])
        for itm in lst:
            time.sleep(float(self.setting.SCRIPT_EXECUTION_DELAY))
            self.execute(Command(itm))

        # Define atexit handler to deal with ctrl-c exit

        atexit.register(lambda : Shell.Instance.shutdown() )

        # Start command reader

        self.config.running=True
        self.reader = Reader(self)
        self.reader.start()

        # Execute shutdown scripts

        self.shutdown()

    def shutdown(self):

        if self.config.running:

            # Execute shutdown scripts

            lst = self.config.get('shutdown',[])
            for itm in lst:
                time.sleep(float(self.setting.SCRIPT_EXECUTION_DELAY))
                self.execute(Command(itm))

            # Execute SHUTDOWN scripts
            # NOTE : Use config.source so we get ':' paths instead of absolute resolved ones

            for pth in self.config.get('source', []):
                time.sleep(float(self.setting.SCRIPT_EXECUTION_DELAY))
                self.dynaload(self.source(f"{pth}/SHUTDOWN", True))

            # Only run shutdown() once.

            self.config.running=False

    def handler(self,*args): # wrd1,wrd2,fnc

        # handler({...})

        if len(args)==1:

            for verb,hsh in args[0].items():
                for noun,fnc in hsh.items():
                    self.handler(verb,noun,fnc)

            return

        # handler(verb,noun,fnc)

        if len(args)==3:

            (verb,noun,fnc)=args

            if self._handler.get(verb) is None:
                self._handler[verb] = {}

            self._handler[verb][noun] = fnc

            return

    def macro(self,*args):

        # macro({...})

        if len(args)==1:
            for typ,fnc in args[0].items(): self.macro(typ,fnc)

        # macro(key,fnc)

        if len(args)==2:
            (typ,fnc)=args

            check.is_false(hasattr(self,f"macro_{typ}"), f"Macro handler {typ} already defined")
            extend(self, {f"macro_{typ}": fnc})

    def format(self,typ,fnc):

        check.is_false(hasattr(self, f"format_{typ}"), f"Format handler {typ} already defined")
        extend(self, {f"format_{typ}": fnc})

    def execute(self,cmnd):

        try:

            self.command = cmnd
            self._declare.command = cmnd

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

            source = self.source(cmnd.name)
            label  = cmnd.name

            self.dynaload(source,label)

        except:
            traceback.print_exc()

    def dynaload(self,source,label='Anonymous'):

        if source:

            file   = self.script(source,label)
            mod    = importlib.import_module(file)

            # call onImport (optional)

            if hasattr(mod, "onImport"): getattr(mod,"onImport")(self,mod)

    def source(self,name,silent=False):

        # explicit source

        if ":" in name:

            name = self.path(name)
            if utils.file_exists(name):
                return self.parse(utils.load_file(name))

        # implicit source

        else:

            for pth in self._source:
                if utils.file_exists(f"{pth}/{name}"):
                    return self.parse(utils.load_file(f"{pth}/{name}"))

        # Source not found

        if not silent: check.failure(f"Could not find source for '{name}'")

        return None

    def parse(self,src):

        ret = ""

        # Get rid of leading/trailing spaces

        src = src.strip()

        # Formatted ?

        if src.startswith('#!'):

            src = self.parse_format(src)

        for line in src.splitlines():

            # Macro line

            if line.lstrip().startswith("@"):

                ret += self.parse_macro(line)

            # Normal line

            else:

                ret += line + "\n"

        return ret

    def parse_format(self,src):

        src += '\n'
        (typ,src) = src.split('\n',1)
        typ = typ[2:]

        check.not_none(self.__dict__.get(f"format_{typ}"),f"Format handler {typ} not defined")
        return self.__dict__[f"format_{typ}"](src)

    def parse_macro(self,line):

        ret  = ""
        tail = line.lstrip()
        head = line[:len(line) - len(tail)]

        cmnd = Command(tail[1:])
        body = None

        # system macros

        if self.__class__.__dict__.get(f"macro_{cmnd.name}"):
            body = self.__class__.__dict__[f"macro_{cmnd.name}"](self, cmnd)
            if body is None: body = ""
            body = self.parse(dedent(body))

        # shell macros

        elif self.__dict__.get(f"macro_{cmnd.name}"):

            body = self.__dict__[f"macro_{cmnd.name}"](cmnd)
            if body is None: body = ""
            body = self.parse(dedent(body))

        # Body is None means not handled

        check.not_none(body, f"Macro {cmnd.name} not defined")

        # Return indented body

        for part in body.splitlines(): ret += head + part + "\n"

        return ret

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

        # Add declared variables

        lst = self._declare.keys()
        if len(lst):
            tmp += "# Declared Variables\n\n"
            for key in lst:
                tmp += f"{key} = shell._declare.{key}\n"
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

    def load(self,file,as_structure=False):

        file = self.path(file)

        if file.endswith('yaml'):

            ret = utils.load_yaml(file)
            if as_structure: ret = Dictionary(ret)
            return ret

        if file.endswith('json'):

            ret = utils.load_json(file)
            if as_structure: ret = Dictionary(ret)
            return ret

        return utils.load_file(file)

    def save(self,file,data):

        file = self.path(file)

        if file.endswith('yaml'):
            utils.save_yaml(file,data)
        elif file.endswith('json'):
            utils.save_json(file,data)
        else:
            utils.save_file(file,data)

    def declare(self,key,obj,renew=False):

        if self._declare.has(key) & (not renew) :
            raise Exception(f"Global variable {key} already declared, cannot be re-declared unless renew is True")

        self._declare.set(key,obj)

    def extend(self,methods):

        extend(self,methods)

    def set(self,key,val):

        self._variable.set(key, val)

    def get(self,key,default=None):

        return self._variable.get(key, default)

    def has(self,key):

        return self._variable.has(key)

    # system macros

    def macro_include(self,cmnd):

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

    def __init__(self,line,data=None,value=None,flag=None):

        cmd = Tokenizer.Parse(line)

        self.name  = cmd["name"]
        self.text  = cmd["text"]

        self.data  = cmd["data"]
        if data: self.data.extend(data)

        self.value = cmd["value"]
        if value: self.value.update(value)
        self.value = Dictionary(self.value)

        self.flag  = cmd["flag"]
        if flag: self.flag.update(flag)
        self.flag  = Dictionary(self.flag)

    def __str__(self):

        return f"<{self.name} data:{self.data} value:{self.value} flag:{self.flag}>"

    def see(self,chk):

        if len(self.data):

            if self.data[0]==chk:
                self.data.pop(0)
                return True
            else:
                return False

        return False

    def pop(self,expect=None):

        tmp = None

        if len(self.data):
            tmp = self.data.pop(0)

        if expect is not None:
            if expect!=tmp:
                check.failure(f"Command expected '{expect}' but found '{tmp}'")

        return tmp

    def peek(self,wrd):

        if len(self.data):
            return self.data[0]==wrd
        else:
            return False

    def shift(self,into):

        tmp = None

        if len(self.data):
            tmp = self.data.pop(0)

        self.value.set(into,tmp)

        return tmp

    def done(self):

        return len(self.data)==0

class Dictionary:

    Hash = {}

    def __init__(self,data=None):

        if data is None: data = {}

        Dictionary.Hash[f"{id(self)}"]=data

    def data(self):

        return Dictionary.Hash[f"{id(self)}"]

    def set(self,key,value):

        self.data()[key]=value

    def has(self,key):

        return key in self.data().keys()

    # dict api

    def clear(self):
        self.data().clear()

    def copy(self):
        return self.data().copy()

    def fromkeys(self,keys,value=None):
        return self.data().fromkeys(keys,value)

    def get(self,key,value=None):
        return self.data().get(key,value)

    def items(self):
        return self.data().items()

    def keys(self):
        return self.data().keys()

    def pop(self,key,defval):
        return self.data().pop(key,defval)

    def popitem(self):
        return self.data().popitem()

    def setdefault(self,key,defval):
        self.data().setdefault(key,defval)

    def update(self,hash):
        self.data().update(hash)

    def values(self):
        return self.data().keys()

    #

    def __str__(self):

        return f"{self.data()}"

    def __getattr__(self,key):

        if not self.has(key): raise Exception(f"Unknown setting key {key} encountered")
        return self.cast(self.get(key))

    def __setattr__(self, key, value):

        self.data()[key]=value

    def __getitem__(self, idx):
        return self.get(idx)

    def __setitem__(self, idx, val):
        self.set(idx,val)

    def cast(self,obj):

        if isinstance(obj,dict):
            return Dictionary(obj)
        else:
            return obj

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

