import site
import time
import importlib
import traceback
import atexit
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from dynashell.utils import *
import dynashell.feature as feature

class Shell:

    # Shell Instance storage

    Instance = None

    #

    def __init__(self,line):

        # Set shell instance

        if not is_none(Shell.Instance): log_failure("Only 1 instance of Shell allowed")
        Shell.Instance = self

        # Public properties

        self.cmdline    = Command(line)
        self.config     = None
        self.setting    = {}
        self.command    = None
        self.reader     = None

        # Private properties

        self._path      = {}
        self._module    = []
        self._source    = []
        self._counter   = 100
        self._variable  = {}
        self._parser    = []
        self._executor  = []

        # Declare cmdline

        self.set("cmdline",self.cmdline,declared=True,protect=True)

        # Set "system:" path

        system_path = slashed_path(os.getcwd())
        self._path['system']=system_path

        # Get configuration file

        config_file = self.cmdline.flag.get('config', './config.yaml')

        # Set "shell:" path

        shell_path = slashed_path(os.path.abspath(os.path.dirname(config_file)))
        self._path['shell']=shell_path

        # Load shell configuration

        self.config = self.load(config_file,True)
        self.set("config",self.config,declared=True,protect=True)

        # Process config.feature section

        lst = self.config.get('feature',[])
        for itm in lst:
            getattr(feature,f"feature_{itm}")(self)

        # Process config.path section

        hsh = self.config.get('path',{})
        for key in hsh.keys():
            self._path[key]=slashed_path(self.path(hsh.get(key)))

        # Load dynashell settings

        res = load_resource("setting.yaml","dynashell")

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
                res = load_resource(self.path(itm))
                if res.get('default'):
                    setting.update(res.get('default',{}))
                    setting.update(res.get(platform,{}))
                else:
                    setting.update(res)

        # Create setting object

        self.setting = Dictionary(setting)
        self.set("setting",self.setting,declared=True,protect=True)

        # Handle USE_READLINE

        if self.setting.USE_READLINE: import readline

        # Determine temp path (for dynascript storage)

        if self._path.get('temp') is None:
            self._path['temp'] = self.path("shell:/temp")

        reset_dir(self._path['temp'])

        # Process config.module section

        lst = self.config.get('module',[])
        for itm in lst:
            pth = slashed_path(self.path(itm))
            self._module.append(pth)
            site.addsitedir(pth)

        # Add shell temp path (for dynascript storage) to module locations

        self._module.append(self._path['temp'])
        site.addsitedir(self._path['temp'])

        # Process config.script section

        lst = self.config.get('source',[])
        for itm in lst:
            pth = slashed_path(self.path(itm))
            self._source.append(pth)

        # Process config.import section

        lst = self.config.get('import',[])
        for itm in lst:
            __import__(itm)

        # Define atexit handler to deal with ctrl-c exit

        atexit.register(lambda : Shell.Instance.shutdown())

        # Execute startup scripts

        self.startup()

        # Start command reader

        self.config.running=True
        self.reader = Reader(self)
        self.reader.start()

        # Execute shutdown scripts

        self.shutdown()

    def feature(self,cfg):

        if cfg.get('field'):
            for key,val in cfg.get('field').items():
                setattr(self,key,val)

        if cfg.get('method'):
            self.extend(cfg.get('method'))

        if cfg.get('parser'):
            self._parser.append(cfg.get('parser'))

        if cfg.get('executor'):
            self._executor.append(cfg.get('executor'))

    def startup(self):

        # Execute STARTUP scripts

        for itm in self.resolve("STARTUP",collect=True): self.link(self.source(itm))

        # Execute startup scripts

        for itm in self.config.get('startup',[]): self.execute(Command(itm))

    def shutdown(self):

        if self.config.running:

            # Execute shutdown scripts

            lst = self.config.get('shutdown',[])
            for itm in lst:
                self.execute(Command(itm))

            # Execute SHUTDOWN scripts

            for itm in self.resolve("SHUTDOWN", collect=True): self.link(self.source(itm))

            # Only run shutdown() once.

            self.config.running=False

    def execute(self,cmnd):

        try:

            self.command = cmnd
            self.set("command",cmnd,declared=True)

            # Try executors

            for fnc in self._executor:
                if fnc(self,cmnd): return

            # Default

            source = self.source(cmnd.name)
            label  = cmnd.name

            self.link(source, label)

        except:
            traceback.print_exc()

    def link(self, source, label='Anonymous'):

        if not is_empty(source):

            time.sleep(float(self.setting.LINK_DELAY))

            src = self.compile(source, label)

            modname = f"script{self._counter}"
            self._counter += 1

            if self.setting.LINK_DEBUG:
                save_file(self.path(f"temp:{modname}.py"),src)
                mod = importlib.import_module(modname)
            else:
                mod=import_from_string(modname,src)

            # call onImport (optional)

            if hasattr(mod,"onImport"): getattr(mod,"onImport")(self,mod)

    def compile(self, source, label):

        tmp = ""

        # Global imports

        tmp += "# Global imports\n\n"
        tmp += "from dynashell.utils import *\n\n"

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

        lst = []

        for key,cfg in self._variable.items():
            if cfg.get('declared'): lst.append(key)

        if len(lst):
            tmp += "# Declared Variables\n\n"
            for key in lst:
                tmp += f"{key} = shell.get('{key}')\n"
            tmp += "\n"

        # Add script source

        tmp += f"# Source '{label}'\n\n"
        tmp += source

        return tmp

    def resolve(self,name,collect=False):

        # If already resolved previously, just return it

        if is_file(name): return name

        # Needed for collect

        lst = []

        # explicit source

        if ":" in name:

            name = self.path(name)
            if is_file(name):
                if collect:
                    lst.append(name)
                else:
                    return name

        # implicit source

        else:

            for pth in self._source:
                if is_file(f"{pth}/{name}"):
                    if collect:
                        lst.append(f"{pth}/{name}")
                    else:
                        return f"{pth}/{name}"

        if collect:
            return lst
        else:
            return None

    def source(self,name,silent=False):

        file = self.resolve(name)

        if file:
            return self.parse(load_file(file))

        if not silent: log_failure(f"Could not find source for '{name}'")

        return None

    def parse(self,src):

        # Get rid of leading/trailing spaces

        src = src.strip()

        # Run parsers

        for fnc in self._parser:
            src = fnc(self,src)

        return src

    def path(self,val):

        for key in self._path.keys():

            if val.startswith(f"{key}:"):
                val = val[len(key)+1:]
                if not val.startswith("/"): val = f"/{val}"
                return self._path[key]+val

        return val

    def load(self, file, as_dictionary=False):

        file = self.path(file)

        if file.endswith('yaml'):

            ret = load_yaml(file)
            if as_dictionary: ret = Dictionary(ret)
            return ret

        if file.endswith('json'):

            ret = load_json(file)
            if as_dictionary: ret = Dictionary(ret)
            return ret

        return load_file(file)

    def save(self,file,data):

        file = self.path(file)

        if file.endswith('yaml'):
            save_yaml(file,data)
        elif file.endswith('json'):
            save_json(file,data)
        else:
            save_file(file,data)

    def extend(self,methods):

        extend(self,methods)

    def set(self,key,val,declared=False,protect=False):

        if self.has(key):
            if self._variable.get(key).get('protect'): log_failure(f"Cannot reset protected variable {key}")

        self._variable[key]={'value':val,'declared':declared,'protect':protect}

    def get(self,key,default=None):

        if self.has(key):
            return self._variable.get(key).get('value')
        else:
            return default

    def has(self,key):

        return self._variable.get(key,False)

class Reader:

    def __init__(self,shell):

        self._shell   = shell
        self._session = PromptSession(history=FileHistory(".example-history-file"))
        self._running = True
        self._stdin   = shell.cmdline.flag.get('stdin', True)
        self._lines   = []

    def read_line(self):

        if len(self._lines)!=0:
            return self._lines.pop(0)
        else:
            if self._stdin:
                #return input('>')
                return self._session.prompt('>')
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
                log_failure(f"Command expected '{expect}' but found '{tmp}'")

        return tmp

    def push(self,val):

        self.data.append(val)

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

    Data   = {}
    Render = {}

    def __init__(self,data=None,render=lambda val: val):

        if data is None: data = {}

        Dictionary.Data[f"{id(self)}"]   = data
        Dictionary.Render[f"{id(self)}"] = render

    def data(self):

        return Dictionary.Data[f"{id(self)}"]

    def render(self,value):

        return Dictionary.Render[f"{id(self)}"](value)

    def set(self,key,value):

        self.data()[key]=self.render(value)

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
        self.data().setdefault(key,self.render(defval))

    def update(self,hash):
        self.data().update(hash)

    def values(self):
        return self.data().values()

    #

    def __str__(self):

        return f"{self.data()}"

    def __getattr__(self,key):

        if not self.has(key): log_failure(f"Undefined dictionary entry {key} encountered")
        return self.cast(self.get(key))

    def __setattr__(self,key,value):

        self.data()[key]=self.render(value)

    def __getitem__(self,idx):

        return self.get(idx)

    def __setitem__(self, idx, value):

        self.set(idx,self.render(value))

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

    def expect(self,exp):

        ch = self.next()
        if ch!=exp: log_failure(f"Expected '{exp}' but got '{ch}'")

    def skip_spaces(self):

        while self.peek().isspace(): self.next()

    def read_chars(self,cset):

        tmp = ''
        while self.peek(lambda ch: ch in cset): tmp += self.next()
        return tmp

    def read_word(self):

        word = ''
        while self.peek() not in ' =': word += self.next()
        if is_empty(word): log_failure("Word is empty")
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