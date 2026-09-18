class Logger:

    DEBUG   = 0
    INFORM  = 1
    WARNING = 2
    ERROR   = 3
    FAILURE = 4
    Level   = DEBUG
    String  = ("DEBUG","INFORM","WARNING","ERROR","FAILURE")
    Handle  = lambda lvl,msg: print(f"{Logger.String[lvl]:<9} : {msg}")

def debug(msg, fire=True):
    if fire & Logger.Level<=Logger.DEBUG:
        Logger.Handle(Logger.DEBUG,msg)
    pass

def inform(msg, fire=True):
    if fire & Logger.Level<=Logger.INFORM:
        Logger.Handle(Logger.INFORM,msg)

def warning(msg, fire=True):
    if fire & Logger.Level<=Logger.WARNING:
        Logger.Handle(Logger.WARNING,msg)

def error(msg, fire=True):
    if fire  & Logger.Level<=Logger.ERROR:
        Logger.Handle(Logger.ERROR,msg)

def failure(msg, fire=True):
    if fire:
        Logger.Handle(Logger.FAILURE,msg)
        raise Exception(msg)

def level(lvl):
    if isinstance(lvl,str): lvl = {'DEBUG':0,'INFORM':1,'WARNING':2,'ERROR':3}[lvl]
    Logger.Level = lvl

def handle(hdl):
    Logger.Handle = hdl