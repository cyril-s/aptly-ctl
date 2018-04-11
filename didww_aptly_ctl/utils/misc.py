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

