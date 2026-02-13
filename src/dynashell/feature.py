from textwrap import dedent
from dynashell.utils import *

# -----
# Local instance of shell
# -----

_shell= None

def shell(instance=None):
    global _shell

    if instance:
        _shell = instance

    return _shell

# -----
# Feature : macros
# -----

def feature_macros(self):

    shell(self)

    # Methods

    def macro(self,*args):

        # macro({...})

        if len(args)==1:

            for typ,fnc in args[0].items(): self.macro(typ,fnc)

        # macro(key,fnc)

        if len(args)==2:

            (typ,fnc)=args
            if not is_none(self._macro.get(typ)) : log_warning(f"Macro for '@{typ}' already defined")
            self._macro[typ] = fnc

    # System Macros

    def include(self,cmnd):

        return self.source(cmnd.pop())

    # Parser

    def parser(self,src):

        ret = ""

        from dynashell.classes import Command

        for line in src.splitlines():

            tail = line.lstrip()

            if tail.startswith("@"):

                head = line[:len(line) - len(tail)]

                cmnd = Command(tail[1:])

                if is_none(self._macro.get(cmnd.name)) : log_failure(f"Macro for '@{cmnd.name}' not defined")

                body = self._macro.get(cmnd.name)(self,cmnd)
                if body is None: body = ""
                body = self.parse(dedent(body))

                # Return indented body

                for part in body.splitlines(): ret += head + part + "\n"

            else:

                ret += line + "\n"

        return ret

    # Define

    self.feature({
        'field'  : {
            '_macro': {
                'include':include
            }
        },
        'method' : {
            'macro':macro
        },
        'parser' : parser
    })

# -----
# Feature : handlers
# -----

def feature_handlers(self):

    shell(self)

    # Methods

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

            if not is_none(self._handler.get(verb).get(noun)): log_warning(f"Handler for '{verb} {noun}' already defined")

            self._handler[verb][noun] = fnc

            return

    # Executor

    def executor(self,cmnd):

        if self._handler.get(cmnd.name):

            verb = cmnd.name
            noun = cmnd.pop()

            if noun is None: return False

            if noun in self._handler[verb].keys():

                self._handler[verb][noun](self,verb,noun,cmnd)
                return True

            if '*' in self._handler[verb].keys():

                self._handler[verb]['*'](self,verb,noun,cmnd)
                return True

            cmnd.push(noun)

        return False

    # Define

    self.feature({
        'field': {
            '_handler': {}
        },
        'method': {
            'handler': handler
        },
        'executor': executor
    })

# -----
# Feature : formatters
# -----

def feature_formatters(self):

    shell(self)

    # Methods

    def formatter(self,*args):

        # formatter({...})

        if len(args)==1:
            for typ,fnc in args[0].items(): self.formatter(typ,fnc)

        # formatter(key,fnc)

        if len(args)==2:
            (typ,fnc)=args

            if not is_none(self._formatter.get(typ)) : log_warning(f"Formatter for '{typ}' already defined")
            self._formatter[typ] = fnc

    # Parser

    def parser(self,src):

        if src.startswith('#!'):

            src += '\n'
            (typ,src) = src.split('\n',1)
            typ = typ[2:]

            if is_none(self._formatter.get(typ)) : log_failure(f"Formatter for '{typ}' not defined")
            src = self._formatter.get(typ)(self,src)

        return src

    # Define

    self.feature({
        'field': {
            '_formatter': {}
        },
        'method': {
            'formatter': formatter
        },
        'parser': parser
    })

# -----
# Feature : processors
# -----

def feature_processors(self):

    from dynashell.classes import Dictionary

    shell(self)

    # Context class

    class Context:

        def __init__(self, dat, hsh):
            self.shell = _shell
            self._data = dat
            self._hash = hsh
            self.value = Dictionary(hsh, lambda val: self.render(val))

        #

        def data(self):
            return self._data

        def empty(self):
            return is_empty(self._data)

        def shift(self):
            return self._data.pop(0)

        #

        def hash(self):
            return self._hash

        def set(self,k,v):
            self._hash[k]=v

        def get(self,k,defval):
            return self._hash.get(k,defval)

        def has(self,k):
            return self._hash.get(k) is not None

        def assign(self, **kwargs):

            for k, v in kwargs.items():
                self._hash[k] = self.render(v)
            return self

        #

        def require(self, **kwargs):

            for k,v in kwargs.items():

                # Callable (obsolete?)

                if is_callable(v):
                    self._hash[k]=v(self,k, self._hash.get(k))

                # Validator

                if isinstance(v,Validator):
                    self._hash[k]=Validator.Validate(self,k,self._hash.get(k,v.default),v.script)

                # Assign value if not already defined

                if k not in self._hash:
                    self._hash[k] = v

                # Apply render to value

                self._hash[k] = self.render(self._hash[k])

                # ???

                if is_none(self._hash.get(k)): log_failure(f"Required value {k} is missing")

            return self

        def report(self, txt, **kwargs):

            print(">" + self.render(txt, **kwargs))
            return self

        def execute(self, src, **kwargs):

            src = dedent(self.render(src, **kwargs))
            obj = self.shell.get("executor")

            if isinstance(obj,dict):
                obj['execute'](src)
            else:
                 obj.execute(src)

            return self

        def render(self, src, **kwargs):

            if isinstance(src, str):
                return src.format(**self._hash, **kwargs, **self.shell.setting)
            else:
                return src

        def validate(self, **kwargs):

            for k, v in kwargs.items():
                v(k, self._hash[k])

            return self

        #

        def __getattr__(self, key):

            return lambda *args, **kwargs: self.__invoke(key, *args, **kwargs)

        def __invoke(self, key, *args, **kwargs):

            Context.Invoke(key, self._hash, *args, **kwargs)
            return self

        #

        @staticmethod
        def Invoke(key,*args, **kwargs):
            fnc = _shell._processor.get(key)
            if is_none(fnc): log_failure(f"Context method {key} has not been registered")
            ctx = Context.Create(*args, **kwargs)
            fnc(ctx)


        @staticmethod
        def Create(*args, **kwargs):

            hsh = {}
            dat = []

            # process args

            for arg in args:
                if isinstance(arg, (dict, Dictionary)):
                    hsh.update(arg)
                else:
                    dat.append(arg)

            # process kwargs

            hsh.update(kwargs)

            # Handle any "{..}" parts in string values

            for k, v in hsh.items():
                if isinstance(v, str):
                    hsh[k] = v.format(**hsh)

            # Return Context object

            return Context(dat, hsh)

    # Methods

    def processor(self,fnc):

        self._processor[fnc.__name__] = fnc

    # Executor

    def executor(self,cmnd):

        if self._processor.get(cmnd.name):

            Context.Invoke(cmnd.name,*cmnd.data, **cmnd.value)
            return True

        return False

    # Define

    self.feature({
        'field': {
            '_processor': {}
        },
        'method': {
            'processor': processor
        },
        'executor': executor
    })

def processor(fnc):

    _shell.processor(fnc)
    return fnc

class Validator:
    def __init__(self,val):
        self.default = val
        self.script  = []

    def __getattr__(self,key):
        return lambda *args, **kwargs: self.__append(key, *args, **kwargs)

    def __append(self,key,*args, **kwargs):
        self.script.append({'id':key,'args':args,'kwargs':kwargs})
        return self

    @staticmethod
    def Validate(ctx,key,val,scr):

        for act in scr:

            if act['id'] == 'shift':
                if val is None: val = ctx.shift()

            if act['id'] == 'is_in':
                lst = act['args']
                log_failure(f"Value of {key} must be in {lst}",not is_val_in(val,*lst))

        return val

#

def default(val=None):
    return Validator(val)
