import json
import yaml
import logging
import sys
import os.path
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError

logger = logging.getLogger(__name__)

class SerializedIO:
    """ Class to handle common I/O opertaions for plugins.
    Handles input and output in yaml or json, in file or stdout,
    colored or not, etc."""

    def __init__(self, input_f, output_f, output_f_fmt):

        if input_f in ["-", "stdin"]:
            self.input_f = '-'
        elif os.path.isfile(input_f):
            self.input_f = input_f
        else:
            raise ValueError("Incorrect input file: %s" % input_f)

        if output_f in ["-", "stdout"]:
            self.output_f = '-'
        else:
            self.output_f = output_f

        if output_f_fmt.lower() not in ["yaml", "json"]:
            raise ValueError("Not supported output format: %s" % output_f_fmt)
        else:
            self.output_f_fmt = output_f_fmt.lower()


    def get_input(self):
        """Get input for plugin. Automatically detects input format and return dict object"""
        if self.input_f == '-':
            logger.debug("Reading from stdin")
            inp = sys.stdin.read()
        else:
            logger.debug("Reading from file {}".format(self.input_f))
            with open(self.input_f, 'r') as f:
                inp = f.read()

        try:
            data = json.loads(inp)
            logger.debug("Input is serialized as json")
        except json.JSONDecodeError as e1:
            logger.debug("Input is not serialized as json")
            try:
                data = yaml.load(inp)
                logger.debug("Stdin is serialized as yaml")
            except yaml.YAMLError as e2:
                logger.exception(e1)
                logger.exception(e2)
                raise DidwwAptlyCtlError("Cannot load from input")

        return data


    def _print_output(self, struct, f):
        if self.output_f_fmt == "yaml":
            yaml.dump(struct, f, default_flow_style=False, indent=2)
        elif self.output_f_fmt == "json":
            json.dump(struct, f)
        else:
            raise ValueError("Not supported output format %s" % self.output_f_fmt)


    def print_output(self, struct):
        if self.output_f == '-':
            self._print_output(struct, sys.stdout)
        else:
            with open(self.output_f, 'a') as f:
                self._print_output(struct, f)
