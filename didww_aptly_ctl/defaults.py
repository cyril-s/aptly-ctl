defaults = {
        "global": {
            "url": "http://10.15.70.6:8090/api",
            },
        "publish": {
            "gpg_key_name": "57D20558",
            "passphraze_file": "/home/pkg/gpg_pass",
            },
        "files": {
            "upload_timeout": 300,
            },
        }

# map number of '-v' args to log level
VERBOSITY = frozenset("WARN", "INFO", "DEBUG")
