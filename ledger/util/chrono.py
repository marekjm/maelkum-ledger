import datetime

from .. import constants


def parse_timestamp(s : str) -> datetime.datetime:
    s = s.strip()  # Just to make sure.

    try:
        # Try the full timestamp format first. It is nice to get as much
        # information as possible, so let's assume that we get the full amount
        # of it: date and time.
        return datetime.datetime.strptime(
            s,
            constants.TIMESTAMP_FORMAT,
        )
    except ValueError:
        # If the input cannot be parsed as a full timestamp let's hope we can at
        # least treat it as a datestamp.
        return datetime.datetime.strptime(
            s,
            constants.DAYSTAMP_FORMAT,
        )
