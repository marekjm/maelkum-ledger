import datetime
import decimal
import re

from . import ir


def parse_open_account(lines):
    source = []

    # Parse the `open account DATETIME KIND NAME` line.
    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[2], '%Y-%m-%dT%H:%M')
    kind = parts[3]
    name = parts[4]

    # Parse the `balance: 0.00 CURRENCY` line.
    source.append(lines[1])
    parts = str(source[-1]).split()
    balance_currency = parts[-1]
    balance_amount = decimal.Decimal(parts[-2])
    balance = (balance_amount, balance_currency,)

    # We either handle the end of the parse, or get a list of tags.
    if str(lines[2]) not in ('with', 'end',):
        raise None

    tags = []
    if str(lines[2]) == 'with':
        source.append(lines[2])
        i = 3
        while str(lines[i]) != 'end':
            tags.append(str(lines[i]))
            source.append(lines[i])
            i += 1
        source.append(lines[i])

    return len(source), ir.Account_record(
        source,
        timestamp,
        kind,
        name,
        balance,
        tags,
    )

def parse_currency_rates(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    rates = []
    i = 1
    while str(lines[i]) != 'end':
        source.append(lines[i])
        i += 1

        parts = str(source[-1]).strip().split()
        pair = parts[0]
        rate = decimal.Decimal(parts[1])
        units = (int(parts[2]) if len(parts) > 2 else 1)

        pair = pair.split('/')

        rates.append(ir.Exchange_rate(
            source[-1],
            timestamp,
            pair[0],
            pair[1],
            rate,
            units,
        ))

    source.append(lines[i])

    return len(source), ir.Exchange_rates_record(
        source,
        timestamp,
        rates,
    )

def parse_configuration_line(lines):
    source = [lines[0]]

    key, value = str(source[-1]).strip().split(maxsplit = 2)[1:]

    return 1, ir.Configuration_line(
        source,
        key,
        value,
    )

def parse_balance_record(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    rates = []
    i = 1
    while str(lines[i]) != 'end':
        source.append(lines[i])
        i += 1

        parts = str(source[-1]).strip().split()
        account = parts[0]
        value = decimal.Decimal(parts[1])
        currency = parts[2]

        account = account.split('/')

        rates.append(ir.Account_mod(
            source[-1],
            timestamp,
            account,
            (value, currency,),
        ))

    source.append(lines[i])

    return len(source), ir.Balance_record(
        source,
        timestamp,
        rates,
    )

def parse_expense_record(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    accounts = []
    i = 1
    while str(lines[i]) not in ('with', 'end',):
        source.append(lines[i])
        i += 1

        print(source[-1])
        parts = str(source[-1]).strip().rsplit()
        account = parts[0]
        value = None
        currency = None

        is_own_account = lambda a: (a.split('/')[0] in ('asset', 'liability',
            'equity',))
        if is_own_account(account):
            value = decimal.Decimal(parts[-2])
            currency = parts[-1]
            account = account.split('/')
        else:
            account = (None, account,)

        accounts.append(ir.Account_mod(
            source[-1],
            timestamp,
            account,
            (value, currency,),
        ))

    tags = []
    if str(lines[i]) == 'with':
        source.append(lines[i]) # for the `with` line

        i += 1
        while str(lines[i]) != 'end':
            source.append(lines[i])
            tags.append(source[-1])
            i += 1

    source.append(lines[i]) # for the `end` line

    ins = []
    outs = []
    for each in accounts:
        if each < 0:
            ins.append(each)
        else:
            outs.append(each)

    return len(source), ir.Expense_tx(
        source,
        timestamp,
        ins,
        outs,
        tags,
    )

def parse_revenue_record(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    accounts = []
    i = 1
    while str(lines[i]) not in ('with', 'end',):
        source.append(lines[i])
        i += 1

        print(source[-1])
        parts = str(source[-1]).strip().rsplit()
        account = parts[0]
        value = None
        currency = None

        is_own_account = lambda a: (a.split('/')[0] in ('asset', 'liability', 'stock',))
        if is_own_account(account):
            value = decimal.Decimal(parts[-2])
            currency = parts[-1]
            account = account.split('/')
        else:
            account = (None, account,)

        accounts.append(ir.Account_mod(
            source[-1],
            timestamp,
            account,
            (value, currency,),
        ))

    tags = []
    if str(lines[i]) == 'with':
        source.append(lines[i]) # for the `with` line

        i += 1
        while str(lines[i]) != 'end':
            source.append(lines[i])
            tags.append(source[-1])
            i += 1

    source.append(lines[i]) # for the `end` line

    ins = []
    outs = []
    for each in accounts:
        if each > 0:
            ins.append(each)
        else:
            outs.append(each)

    return len(source), ir.Revenue_tx(
        source,
        timestamp,
        ins,
        outs,
        tags,
    )

def parse(lines):
    items = []

    i = 0
    while i < len(lines):
        each = lines[i]
        parts = str(each).split()

        n = 0
        item = None
        if parts[0] == 'open':
            n, item = parse_open_account(lines[i:])
        elif parts[0] == 'currency_rates':
            n, item = parse_currency_rates(lines[i:])
        elif parts[0] == 'set':
            n, item = parse_configuration_line(lines[i:])
        elif parts[0] == 'balance':
            n, item = parse_balance_record(lines[i:])
        elif parts[0] == 'ex':
            n, item = parse_expense_record(lines[i:])
        elif parts[0] == 'rx':
            n, item = parse_revenue_record(lines[i:])
        else:
            print(each)
            raise # invalid syntax

        if n == 0:
            raise # invalid syntax

        items.append(item)
        i += n

    return items
