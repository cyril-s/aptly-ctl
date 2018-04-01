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

