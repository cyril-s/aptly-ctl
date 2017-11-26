import json
import yaml
import logging
import sys

logger = logging.getLogger(__name__)

def get_input(f):
    if f == "-":
        try:
            in = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            raise DidwwAptlyCtlError("Cannot load from stdin:", e, logger)
    else:
        try:
            with open(args.file, "r") as f:
                remove_list = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise DidwwAptlyCtlError("Cannot load from file -f:", e, logger)



def print_output(fmt):


