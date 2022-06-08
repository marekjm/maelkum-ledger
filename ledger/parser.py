import datetime
import decimal
import re
import sys

from . import ir
from . import util
from . import constants


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
            tags.append(str(lines[i]).strip())
            source.append(lines[i])
            i += 1
        source.append(lines[i])
    else:
        source.append(lines[2])

    return len(source), ir.Account_record(
        source,
        timestamp,
        kind,
        name,
        balance,
        tags,
    )

def parse_close_account(lines):
    source = []

    # Parse the `open account DATETIME KIND NAME` line.
    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[2], '%Y-%m-%dT%H:%M')
    kind = parts[3]
    name = parts[4]

    return len(source), ir.Account_close(
        source,
        timestamp,
        kind,
        name,
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
        account = account.split('/')

        if account[0] == constants.ACCOUNT_EQUITY_T:
            company = parts[1]
            value = decimal.Decimal(parts[2])
            currency = parts[3]
            rates.append(ir.Account_mod(
                source[-1],
                timestamp,
                account,
                (company, value, currency,),
            ))
        else:
            value = decimal.Decimal(parts[1])
            currency = parts[2]
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

    non_owned_account_present = False

    accounts = []
    i = 1
    while str(lines[i]) not in ('with', 'end',):
        source.append(lines[i])
        i += 1

        # print(source[-1])
        parts = str(source[-1]).strip().rsplit()
        account = parts[0]
        value = None
        currency = None

        is_own_account = lambda a: (a.split('/')[0] in constants.ACCOUNT_TYPES)
        if is_own_account(account):
            try:
                value = decimal.Decimal(parts[-2])
            except decimal.InvalidOperation:
                fmt = 'invalid decimal literal: `{}\''
                sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                    util.colors.colorise(
                        'white',
                        source[-1].location,
                    ),
                    util.colors.colorise(
                        'red',
                        'error',
                    ),
                    util.colors.colorise(
                        'white',
                        str(parts[-2]),
                    ),
                ))
                exit(1)

            if value >= 0:
                fmt = 'non-negative expense value: `{}\''
                sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                    util.colors.colorise(
                        'white',
                        source[-1].location,
                    ),
                    util.colors.colorise(
                        'red',
                        'error',
                    ),
                    util.colors.colorise(
                        'white',
                        str(parts[-2]),
                    ),
                ))

                fmt = 'expense values from own accounts must be negative'
                sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                    util.colors.colorise(
                        'white',
                        source[-1].location,
                    ),
                    util.colors.colorise(
                        'blue',
                        'note',
                    ),
                ))
                exit(1)

            currency = parts[-1]
            account = account.split('/')
        else:
            non_owned_account_present = True
            account = (None, str(source[-1]).strip(),)

        accounts.append(ir.Account_mod(
            source[-1],
            timestamp,
            account,
            (value, currency,),
        ))

    if not non_owned_account_present:
        fmt = 'only own accounts in expense record'
        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
            util.colors.colorise(
                'white',
                source[0].location,
            ),
            util.colors.colorise(
                'red',
                'error',
            ),
        ))

        fmt = 'expense records must include a non-owned account'
        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
            util.colors.colorise(
                'white',
                source[0].location,
            ),
            util.colors.colorise(
                'blue',
                'note',
            ),
        ))
        exit(1)

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

        # print(source[-1])
        parts = str(source[-1]).strip().rsplit()
        account = parts[0]
        value = None
        currency = None

        is_own_account = lambda a: (a.split('/')[0] in constants.ACCOUNT_TYPES)
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
            outs.append(each)
        else:
            ins.append(each)

    return len(source), ir.Revenue_tx(
        source,
        timestamp,
        ins,
        outs,
        tags,
    )

def parse_transfer_record(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    accounts = []
    i = 1
    while str(lines[i]) not in ('with', 'end',):
        source.append(lines[i])
        i += 1

        # print(source[-1])
        parts = str(source[-1]).strip().rsplit()
        account = parts[0]
        value = None
        currency = None

        is_own_account = lambda a: (a.split('/')[0] in constants.ACCOUNT_TYPES)
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

    is_equity_tx = False
    tags = []
    if str(lines[i]) == 'with':
        source.append(lines[i]) # for the `with` line

        i += 1
        while str(lines[i]) != 'end':
            source.append(lines[i])
            tags.append(source[-1])
            if str(tags[-1]).strip().startswith('shares:'):
                is_equity_tx = True
            i += 1

    source.append(lines[i]) # for the `end` line

    ins = []
    outs = []
    for each in accounts:
        if each > 0:
            outs.append(each)
        else:
            ins.append(each)

    return len(source), (ir.Equity_tx if is_equity_tx else ir.Transfer_tx)(
        source,
        timestamp,
        ins,
        outs,
        tags,
    )

def parse_dividend_record(lines):
    source = []

    source.append(lines[0])
    parts = str(source[-1]).split()
    timestamp = datetime.datetime.strptime(parts[1], '%Y-%m-%dT%H:%M')

    company = None
    eq_account = None

    accounts = []
    i = 1
    while str(lines[i]) not in ('with', 'end',):
        source.append(lines[i])
        i += 1

        # print(source[-1])
        parts = str(source[-1]).strip().rsplit()

        account = parts[0]
        account = account.split('/')
        kind, name = account
        if kind == constants.ACCOUNT_EQUITY_T:
            company = parts[1]
            eq_account = account
            continue

        value = decimal.Decimal(parts[1])
        currency = parts[2]

        accounts.append(ir.Account_mod(
            source[-1],
            timestamp,
            account,
            (value, currency,),
        ))

    source.append(lines[i]) # for the `end` line

    ins = []
    outs = []
    for each in accounts:
        if each > 0:
            outs.append(each)
        else:
            ins.append(each)

    ins.append(ir.Account_mod(
        source[-2],
        outs[0].timestamp,
        eq_account,
        (company, *outs[0].value,)
    ))

    tags = []

    return len(source), ir.Dividend_tx(
        source,
        timestamp,
        ins,
        outs,
        tags,
    ), ir.Revenue_tx(
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
        elif parts[0] == 'close':
            n, item = parse_close_account(lines[i:])
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
        elif parts[0] == 'tx':
            n, item = parse_transfer_record(lines[i:])
        elif parts[0] == 'dividend':
            n, item, rx = parse_dividend_record(lines[i:])
            items.append(rx)
        else:
            print(type(each), repr(each))
            fmt = 'invalid syntax in `{}`'
            sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                util.colors.colorise(
                    'white',
                    each.location,
                ),
                util.colors.colorise(
                    'red',
                    'error',
                ),
                str(each),
            ))
            exit(1)
            raise # invalid syntax

        if n == 0:
            raise # invalid syntax

        if item is not None:
            items.append(item)
        i += n

    return items
