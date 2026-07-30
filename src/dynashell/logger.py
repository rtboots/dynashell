class Logger:

    DEBUG   = 0
    INFORM  = 1
    WARNING = 2
    ERROR   = 3
    Level   = DEBUG
    Handle  = lambda msg: print(msg)

def debug(msg, fire=True):
    if fire & Logger.Level<=Logger.DEBUG:
        Logger.Handle(f"DEBUG   : {msg}")
    pass

def inform(msg, fire=True):
    if fire & Logger.Level<=Logger.INFORM:
        Logger.Handle(f"INFORM  : {msg}")

def warning(msg, fire=True):
    if fire & Logger.Level<=Logger.WARNING:
        Logger.Handle(f"WARNING : {msg}")

def error(msg, fire=True):
    if fire  & Logger.Level<=Logger.ERROR:
        Logger.Handle(f"ERROR   : {msg}")

def failure(msg, fire=True):
    if fire:
        Logger.Handle(f"FAILURE : {msg}")
        raise Exception(msg)

def level(lvl):
    if isinstance(lvl,str): lvl = {'DEBUG':0,'INFORM':1,'WARNING':2,'ERROR':3}[lvl]
    Logger.Level = lvl

def handle(hdl):
    Logger.Handle = hdl