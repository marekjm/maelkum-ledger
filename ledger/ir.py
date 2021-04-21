import datetime

from . import constants


class Item:
    def __init__(self, text, timestamp):
        self.text = text
        self.timestamp = timestamp


class Account_record(Item):
    def __init__(self, text, timestamp, kind, name, balance, tags):
        super().__init__(text, timestamp)
        self.kind = kind
        self.name = name
        self.balance = balance
        self.tags = tags

class Account_mod(Item):
    def __init__(self, text, timestamp, account, value):
        super().__init__(text, timestamp)
        self.account = account
        self.value = value

    def __lt__(self, x):
        return (self.value[0] < x) if self.value[0] is not None else False

    def __gt__(self, x):
        return (self.value[0] > x) if self.value[0] is not None else False

class Balance_record(Item):
    def __init__(self, text, timestamp, accounts):
        super().__init__(text, timestamp)
        self.accounts = accounts

    def effective_date(self):
        return self.timestamp


class Transaction_record(Item):
    def __init__(self, text, timestamp, ins, outs, tags):
        super().__init__(text, timestamp)
        self.ins = ins
        self.outs = outs
        self.tags = tags

        self._effective_date = None

    def effective_date(self):
        if self._effective_date:
            return self._effective_date
        for each in self.tags:
            k, v = str(each).strip().split(':', maxsplit = 1)
            if k == 'effective_date':
                ed = datetime.datetime.strptime(
                    v.strip(),
                    constants.TIMESTAMP_FORMAT,
                )
                self._effective_date = ed
                break
        if self._effective_date is None:
            self._effective_date = self.timestamp
        return self._effective_date


class Revenue_tx(Transaction_record):
    pass
class Expense_tx(Transaction_record):
    pass
class Transfer_tx(Transaction_record):
    pass


class Exchange_rate(Item):
    def __init__(self, text, timestamp, src, dst, rate, units = 1):
        super().__init__(text, timestamp)
        self.src = src
        self.dst = dst
        self.rate = rate
        self.units = units

class Exchange_rates_record(Item):
    def __init__(self, text, timestamp, rates):
        super().__init__(text, timestamp)
        self.rates = rates


class Configuration_line(Item):
    def __init__(self, text, key, value):
        super().__init__(text, datetime.datetime(1970, 1, 1)) # no timestamp
        self.key = key
        self.value = value
