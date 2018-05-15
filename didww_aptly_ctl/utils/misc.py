import logging
logger = logging.getLogger(__name__)
 
def flatten_list(l):
    "flattens list of lists of any depth"
    flat_list = []
    for item in l:
        if isinstance(item, list):
            flat_list.extend(flatten_list(item))
        else:
            flat_list.append(item)
    return flat_list

def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value

def nested_update(src, dst):
    for item in src:
        if item in dst and isinstance(src[item], dict) and isinstance(dst[item], dict):
            nested_update(src[item], dst[item])
        elif item in dst:
            src[item] = dst[item]
        else:
            pass
    for item in dst:
        if item not in src:
            src[item] = dst[item]
