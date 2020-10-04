import re
import unidecode
from .const import *

def getIncrement(entity_id):
        lastNum = entity_id[entity_id.rindex('_')+1:]
        if(lastNum.isnumeric()):
            return int(lastNum)+1
        return 1

def addTapoEntityID(tapo, requested_entity_id, requested_value):
    regex = r"^"+requested_entity_id.replace(".","\.")+"_[0-9]+$"
    if(requested_entity_id in tapo):
        biggestIncrement = 0
        for id in tapo:
            r1 = re.findall(regex,id)
            if r1:
                inc = getIncrement(requested_entity_id) 
                if(inc > biggestIncrement):
                    biggestIncrement = inc
        if(biggestIncrement == 0):
            oldVal = tapo[requested_entity_id]
            tapo.pop(requested_entity_id, None)
            tapo[requested_entity_id+"_1"] = oldVal
            tapo[requested_entity_id+"_2"] = requested_value
        else:
            tapo[requested_entity_id+"_"+str(biggestIncrement)] = requested_value
    else:
        biggestIncrement = 0
        for id in tapo:
            r1 = re.findall(regex,id)
            if r1:
                inc = getIncrement(id) 
                if(inc > biggestIncrement):
                    biggestIncrement = inc
        if(biggestIncrement == 0):
            tapo[requested_entity_id] = requested_value
        else:
            tapo[requested_entity_id+"_"+str(biggestIncrement)] = requested_value
    return tapo

def generateEntityIDFromName(name):
    str = unidecode.unidecode(name.rstrip().replace(".","_").replace(" ", "_").lower())
    str = re.sub("_"+'{2,}',"_",''.join(filter(ENTITY_CHAR_WHITELIST.__contains__, str)))
    return DOMAIN+"."+str