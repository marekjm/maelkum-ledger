#!/usr/bin/env python3

import datetime
import decimal
import os
import sys

import ledger

# USEFUL CHARACTERS
#
# ≅ U+2245 APPROXIMATELY EQUAL TO
# ≈ U+2248 ALMOST EQUAL TO
# ∾
# ∝
# ⊕
# ⊖
# ⊗
# ⊘
# ⊙
# ⊜
# ∫
# ∗
# ∘
# ∙

def to_impl(stream, fmt, *args, **kwargs):
    stream.write((fmt + '\n').format(*args, **kwargs))

to_stdout = lambda fmt, *args, **kwargs: to_impl(sys.stdout, fmt, *args, **kwargs)
to_stderr = lambda fmt, *args, **kwargs: to_impl(sys.stderr, fmt, *args, **kwargs)

ACCOUNT_ASSET_T = 'asset'
ACCOUNT_LIABILITY_T = 'liability'
ACCOUNT_EQUITY_T = 'equity'
ACCOUNT_TYPES = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
)

def report_total_impl(period, account_types, accounts, book, default_currency):
    reserves_default = decimal.Decimal()
    reserves_foreign = decimal.Decimal()
    for t in account_types:
        for name, acc in accounts[t].items():
            if not acc['active']:
                continue
            if acc['currency'] == default_currency:
                reserves_default += acc['balance']
            else:
                _, currency_basket = book

                pair = (acc['currency'], default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, acc['currency'],)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for {} account named {}'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            ledger.util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            ledger.util.colors.colorise(
                                'red',
                                'error',
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            ledger.util.colors.colorise(
                                'white',
                                name,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    reserves_foreign += (acc['balance'] / rate)
                else:
                    reserves_foreign += (acc['balance'] * rate)

    reserves_total = (reserves_default + reserves_foreign)

    no_of_accounts = 0
    for t in account_types:
        no_of_accounts += len(accounts[t].keys())

    fmt = '{} on all {} account(s): '
    if reserves_foreign:
        fmt += '≈{} {} ({} {} + ≈{} {} in foreign currencies)'
    else:
        fmt += '{} {}'

    to_stdout(fmt.format(
        ledger.util.colors.colorise(
            ledger.util.colors.COLOR_PERIOD_NAME,
            period,
        ),
        no_of_accounts,
        ledger.util.colors.colorise_balance(
            reserves_total if reserves_foreign else reserves_default),
        default_currency,
        ledger.util.colors.colorise_balance(
            reserves_default if reserves_foreign else reserves_total),
        default_currency,
        ledger.util.colors.colorise_balance(reserves_foreign),
        default_currency,
    ))

def report_total_reserves(accounts, book, default_currency):
    report_total_impl(
        'Reserve',
        (ACCOUNT_ASSET_T, ACCOUNT_LIABILITY_T,),
        accounts,
        book,
        default_currency,
    )

def report_total_balances(accounts, book, default_currency):
    report_total_impl(
        'Balance',
        ACCOUNT_TYPES,
        accounts,
        book,
        default_currency,
    )

    longest_account_name = 0
    for t in ACCOUNT_TYPES:
        for a in accounts[t].keys():
            if not accounts[t][a]['active']:
                continue
            longest_account_name = max(longest_account_name, len(a))

    def sort_main_on_top(accounts):
        keys = sorted(accounts.keys())
        keys = sorted(
            keys,
            key = lambda k: ('main' in accounts[k]['tags']),
            reverse = True,
        )
        return keys
    for t in ACCOUNT_TYPES:
        for name in sort_main_on_top(accounts[t]):
            acc = accounts[t][name]
            tags = acc['tags']

            if not acc['active']:
                continue

            if 'overview' not in tags:
                continue

            m = ''

            balance_raw = acc['balance']
            fmt = '  {}: {} {}'
            m += fmt.format(
                name.ljust(longest_account_name),
                ledger.util.colors.colorise_balance(balance_raw, '{:8.2f}'),
                acc['currency'],
            )

            balance_in_default = None
            rate = None
            if acc['currency'] != default_currency and acc['balance']:
                _, currency_basket = book

                pair = (acc['currency'], default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, acc['currency'],)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for {} account named {}'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            ledger.util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            ledger.util.colors.colorise(
                                'red',
                                'error',
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            ledger.util.colors.colorise(
                                'white',
                                name,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    balance_in_default = (balance_raw / rate)
                else:
                    balance_in_default = (balance_raw * rate)

                # FIXME display % gain/loss depending on exchange rate
                fmt = ' ≅ {} {} at {} {}/{} rate'
                m += fmt.format(
                    ledger.util.colors.colorise_balance(
                        (balance_in_default or 0),
                        '{:7.2f}',
                    ),
                    default_currency,
                    ledger.util.colors.colorise(
                        ledger.util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    acc['currency'],
                    default_currency,
                )

            to_stdout(m)

def report_total_equity(accounts, book, default_currency):
    eq_accounts = accounts['equity']

    book, currency_basket = book

    for name, account in eq_accounts.items():
        account['balance'] = decimal.Decimal()
        account['paid'] = decimal.Decimal()
        account['value'] = decimal.Decimal()
        account['dividends'] = decimal.Decimal()
        account['worth'] = decimal.Decimal()

        for company, shares in account['shares'].items():
            share_price = shares['price_per_share']
            dividends = shares['dividends']

            # Fees paid to acquire the shares.
            fees = decimal.Decimal()

            # Total amount of money paid for the shares: share price plus any
            # fees to intermediaries.
            paid = decimal.Decimal()

            shares_no = 0
            for each in shares['txs']:
                paid += each['value']
                fee = each['shares']['fee']['amount']
                paid -= fee
                fees -= fee
                shares_no += each['shares']['no']

            # Shares worth at the time.
            worth = (shares_no * share_price)

            # Value of the shares; ie, the value that they represent to the
            # owner after subtracting fees and adding dividends.
            value = (worth - fees + dividends)

            gain_nominal = (worth - paid)
            gain_percent = ((worth / paid * 100) - 100)

            tr_nominal = (worth - paid + dividends)
            tr_percent = ((tr_nominal / paid) * 100)
            tr = {
                'relevant': (dividends != 0),
                'nominal': tr_nominal,
                'percent': tr_percent,
            }

            shares['shares'] = shares_no
            shares['balance'] = worth
            shares['paid'] = paid
            shares['value'] = value
            shares['total_return'] = tr
            shares['gain'] = {
                'nominal': gain_nominal,
                'percent': gain_percent,
            }

            if shares_no:
                account['balance'] += worth
                account['paid'] += paid
                account['value'] += value
            account['dividends'] += dividends

            continue

            # Here is the total money that you had to pay to obtain the
            # shares. It is the source price because what you paid not only
            # includes the shares' worth, but also the fees.
            #
            # Note that the amount may be negative (if you were only buying
            # shares or sold them with a loss) or positive (if you sold
            # shares with a profit).
            #
            # FIXME Calculations should be reset of the amount of shares
            # ever reaches 0 as that means we sold all our shares, and using
            # old prices after such a point does not make much sense.
            paid = sum(map(
                lambda x: (
                    x['value']
                    # A clever way of obtaining 1 if the operation was a buy
                    # and -1 if the operation was a sell.
                    #
                    # We need this to correctly calculate the total amount
                    # of money we have paid for the shares we have. If we
                    # were buying then we should add the amount to the total
                    # cost, but if we were selling then we should subtract.
                    # Multiplying the source amount by either 1 or -1 makes
                    # it possible to do it in a simple map/sum operation.
                    #
                    # Why do we sum source amounts? Because when buying we
                    # should consider the amount of money we had to give to
                    # the trading organisation to obtain the shares, and
                    # when selling we should consider the amount of money we
                    # got from the market.
                    * (x['shares']['no'] / abs(x['shares']['no']))
                ),
                shares['txs']))

            # What the shares are worth is simple: you take price of one
            # share and multiply it by the amount of shares you own.
            worth = (shares_no * share_price)

            # The value of shares for you is not exactly what they are worth
            # on the market. Remember that you paid some fees to acquite
            # them, and that they may have yielded you some dividends.
            value = (worth - fees + dividends)

            # Account's balance tells you the worth of your account and is
            # not concerned with any fees that you may have incurred while
            # acquiting the wealth.
            #
            # The balance should not be modified if there are no shares for
            # a company. This means that all shares were sold and including
            # their cost in the report would be hugely misleading.
            account['balance'] += (worth
                if shares_no
                else decimal.Decimal(0))
            account['paid'] += (paid
                if shares_no
                else decimal.Decimal(0))
            account['value'] += (value
                if shares_no
                else decimal.Decimal(0))
            account['dividends'] += dividends

            tr_nominal = (worth + paid + dividends)
            tr_percent = -((tr_nominal / paid) * 100)
            tr = {
                'relevant': (dividends != 0),
                'nominal': tr_nominal,
                'percent': tr_percent,
            }

            shares['balance'] = worth
            shares['paid'] = paid
            shares['value'] = value
            shares['total_return'] = tr

        # Include dividends in profit calculations. If the shares went down,
        # but the dividends were healthy then you are still OK.
        nominal_value = (account['balance'] + account['dividends'])
        nominal_profit = (nominal_value - account['paid'])
        percent_profit = decimal.Decimal()
        if account['paid']:  # beware zero division!
            percent_profit = (((nominal_value / account['paid']) - 1) * 100)
        account['gain'] = {
            'nominal': nominal_profit,
            'percent': percent_profit,
        }

    total_gain = []
    for name, account in eq_accounts.items():
        gain = account['gain']
        gain_nominal = gain['nominal']
        gain_percent = gain['percent']

        if account['currency'] != default_currency:
            pair = (account['currency'], default_currency,)
            rev = False
            try:
                rate = currency_basket['rates'][pair]
            except KeyError:
                try:
                    pair = (default_currency, account['currency'],)
                    rate = currency_basket['rates'][pair]
                    rev = True
                except KeyError:
                    fmt = 'no currency pair {}/{} for {} account named {}'
                    sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                        ledger.util.colors.colorise(
                            'white',
                            account['~'].text[0].location,
                        ),
                        ledger.util.colors.colorise(
                            'red',
                            'error',
                        ),
                        ledger.util.colors.colorise(
                            'white',
                            account['currency'],
                        ),
                        ledger.util.colors.colorise(
                            'white',
                            default_currency,
                        ),
                        t,
                        ledger.util.colors.colorise(
                            'white',
                            name,
                        ),
                    ))
                    exit(1)

            rate = rate.rate
            if rev:
                gain_nominal = (gain_nominal / rate)
            else:
                gain_nominal = (gain_nominal * rate)

        total_gain.append((gain_nominal, gain_percent,))

    nominal_gain = sum(map(lambda e: e[0], total_gain))
    percent_gain = []
    for n, p in total_gain:
        if p == 0:
            continue  # Avoid a division by zero on empty accounts.
        r = ((n / nominal_gain) * p) * (p / abs(p))
        percent_gain.append(r)
    percent_gain = sum(percent_gain)

    gain_sign = ('+' if nominal_gain > 0 else '')

    # Display the header. A basic overview of how many equity accounts there
    # are.
    fmt = '{} of {} equity account(s): total {} ≈ {} {}, {}{}%'
    to_stdout(fmt.format(
        ledger.util.colors.colorise(
            ledger.util.colors.COLOR_PERIOD_NAME,
            'State',
        ),
        len(eq_accounts.keys()),
        ('profit' if nominal_gain >= 0 else 'loss'),
        ledger.util.colors.colorise_balance(nominal_gain),
        default_currency,
        ledger.util.colors.colorise_balance(percent_gain, gain_sign),
        ledger.util.colors.colorise_balance(percent_gain),
    ))

    # Discover the maximal length of a company name (ie, the ticker) and the
    # maximal length of the shares number. This is used later for to align the
    # report in a readable way.
    company_name_length = 0
    shares_length = 0
    for account in eq_accounts.values():
        for name, shares in account['shares'].items():
            company_name_length = max(company_name_length, len(name))
            shares_length = max(shares_length, len(str(shares['shares'])))

    shares_length = 0
    if len(account['shares'].keys()):
        shares_length = max(map(lambda _: len(str(_['shares'])),
            account['shares'].values()))

    for name in sorted(eq_accounts.keys()):
        account = eq_accounts[name]
        total_value = account['balance']

        gain = account['gain']
        gain_nominal = gain['nominal']
        gain_percent = gain['percent']
        gain_sign = ('+' if gain_percent > 0 else '')

        companies_with_loss = len(list(
            filter(lambda x: (x < 0),
            map(lambda x: x['total_return']['nominal'],
            filter(lambda x: x['shares'],
            account['shares'].values(),
        )))))

        fmt_overview = '  {} => {} {} ({} {}, {}{}%)'
        to_stdout(fmt_overview.format(
            name,
            ledger.util.colors.colorise_balance(total_value),
            account['currency'],
            ledger.util.colors.colorise_balance(gain_nominal),
            account['currency'],
            ledger.util.colors.colorise_balance(gain_nominal, gain_sign),
            ledger.util.colors.colorise_balance(gain_percent),
        ))

        if not account['shares']:
            continue

        fmt = '    {}: {} * {} = {} ({} {}, {}% @ {}{}{} {})'
        fmt_share_price = '{:8.4f}'
        fmt_share_count = '{:3.0f}'
        fmt_share_worth = '{:8.2f}'
        fmt_gain_nominal = '{:8.2f}'
        fmt_gain_percent = '{:8.4f}'
        for company in sorted(account['shares'].keys()):
            shares = account['shares'][company]

            paid = shares['paid']
            no_of_shares = shares['shares']

            if no_of_shares == 0:
                # Perhaps all the shares were sold.
                continue

            share_price = shares['price_per_share']
            share_price_avg = abs(paid / no_of_shares)
            worth = (share_price * no_of_shares)

            gain_nominal = shares['gain']['nominal']
            gain_percent = shares['gain']['percent']
            gain_sign = ('+' if gain_percent >= 0 else '')
            gain_nominal_per_share = (gain_nominal / no_of_shares)

            from ledger.util.colors import colorise_if_possible as c
            from ledger.util.colors import colorise_balance as cb
            from ledger.util.colors import (
                COLOR_SHARE_PRICE,
                COLOR_SHARE_COUNT,
                COLOR_SHARE_PRICE_AVG,
                COLOR_SHARE_WORTH,
            )
            this_fmt = fmt[:]

            tr = shares['total_return']
            value_for_color = gain_percent
            if tr['relevant']:
                this_fmt += ', TR: {} {}, {}%'.format(
                    cb(tr['nominal']),
                    account['currency'],
                    cb(tr['percent']),
                )
                value_for_color = tr['percent']

            to_stdout(this_fmt.format(
                cb(value_for_color, company.rjust(company_name_length)),
                c(COLOR_SHARE_PRICE, fmt_share_price.format(share_price)),
                c(COLOR_SHARE_COUNT, fmt_share_count.format(no_of_shares)),
                c(COLOR_SHARE_WORTH, fmt_share_worth.format(worth)),
                cb(gain_nominal, fmt_gain_nominal),
                account['currency'],
                cb(gain_percent, fmt_gain_percent),
                c(COLOR_SHARE_PRICE_AVG, '{:6.2f}'.format(share_price_avg)),
                cb(gain_nominal_per_share, gain_sign),
                cb(gain_nominal_per_share, '{:.4f}'),
                account['currency'],
                repr(gain_sign),
            ))

def main(args):
    to_stdout("Maelkum's ledger {} ({})".format(
        ledger.__version__,
        ledger.__commit__,
    ))

    book_main = args[0]
    book_lines = ledger.loader.load(book_main)
    # to_stdout('\n'.join(map(repr, book_lines)))

    book_ir = ledger.parser.parse(book_lines)
    # to_stdout('{} item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(repr, book_ir)))

    def sorting_key(item):
        if isinstance(item, ledger.ir.Transaction_record):
            return item.effective_date()
        return item.timestamp
    book_ir = sorted(book_ir, key = sorting_key)
    # to_stdout('chronologically sorted item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(lambda x: '{} {}'.format(x.timestamp, repr(x)), book_ir)))

    ####

    default_currency = 'EUR'
    accounts = { 'asset': {}, 'liability': {}, 'equity': {}, }
    txs = []

    # First, process configuration to see if there is anything the ledger should
    # be aware of - default currency, budger levels, etc.
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            if each.key == 'default-currency':
                default_currency = str(each.value)
            elif each.key == 'budget': # FIXME TODO
                pass
            else:
                raise

    # Then, set up accounts to be able to track balances and verify that
    # transactions refer to recognised accounts.
    for each in book_ir:
        if type(each) is ledger.ir.Account_record:
            kind = each.kind
            name = each.name

            if name in accounts[kind]:
                sys.stderr.write('{}: error: {} account `{}` already exists\n'.format(
                    each.text[0].location,
                    kind,
                    name,
                ))
                sys.stderr.write('note: {} account `{}` is defined at {}\n'.format(
                    kind,
                    name,
                    accounts[kind][name]['~'].text[0].location,
                ))
                exit(1)

            account_data = {
                'active': True,
                'balance': each.balance[0],
                'currency': each.balance[1],
                'created': each.timestamp,
                'tags': each.tags,
                '~': each,
            }

            # If the account represents an equity account, we need to track a
            # bit more information than for a regular asset account. Equity is
            # somewhat dynamic - shares change valuations, divindend are paid
            # out, and transactions usually have fees. This all needs to be
            # accounted for.
            if kind == ledger.constants.ACCOUNT_EQUITY_T:
                # First, let's track shares. This is the basic feature of an
                # equity account and will be the basis of the fluctuating value
                # of the account.
                account_data['shares'] = {}

                # We also need to track the list of companies that are held in
                # shares. This is useful where the amount of shares reaches zero
                # and profit-loss calculations must be reset.
                account_data['companies'] = set()

                # We also need to track profits (or, hopefully not, losses).
                # Profits are tracked as "nominal" ie, measured in monetary
                # units (eg, USD, EUR) and "percent" ie, measured in a
                # percentage increase (or decrease) in value of shares held.
                account_data['gain'] = {
                    'nominal': decimal.Decimal(),
                    'percent': decimal.Decimal(),
                }

            accounts[kind][name] = account_data
        if type(each) is ledger.ir.Account_close:
            kind = each.kind
            name = each.name

            if name not in accounts[kind]:
                sys.stderr.write('{}: error: {} account `{}` does not exists\n'.format(
                    each.text[0].location,
                    kind,
                    name,
                ))
                exit(1)

            accounts[kind][name]['active'] = False

    # Then, process transactions (ie, revenues, expenses, dividends, transfers)
    # to get an accurate picture of balances.
    currency_basket = { 'rates': {}, 'txs': [], }
    def ensure_currency_match(accounts, a):
        kind, name = a.account
        if kind is None:
            fmt = 'no currency for non-owned account {}'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                ledger.util.colors.colorise(
                    'white',
                    a.text.location,
                ),
                ledger.util.colors.colorise(
                    'red',
                    'error',
                ),
                ledger.util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
            ))
            exit(1)
        if name not in accounts[kind]:
            fmt = 'account {} does not exist'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                ledger.util.colors.colorise(
                    'white',
                    a.to_location(),
                ),
                ledger.util.colors.colorise(
                    'red',
                    'error',
                ),
                ledger.util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
            ))
            exit(1)
        account_currency = accounts[kind][name]['currency']
        tx_currency = a.value[1]
        if account_currency != tx_currency:
            fmt = 'mismatched currency: account {} is in {}, but value is in {}'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                ledger.util.colors.colorise(
                    'white',
                    a.text.location,
                ),
                ledger.util.colors.colorise(
                    'red',
                    'error',
                ),
                ledger.util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
                ledger.util.colors.colorise(
                    'light_green',
                    account_currency,
                ),
                ledger.util.colors.colorise(
                    'red_1',
                    tx_currency,
                ),
            ))
            exit(1)
    this_moment_in_time = datetime.datetime.now()

    # Calculate balances.
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            continue
        if type(each) is ledger.ir.Account_record:
            continue

        if type(each) is ledger.ir.Exchange_rates_record:
            for r in each.rates:
                currency_basket['rates'][(str(r.src), str(r.dst),)] = r
            continue

        if each.effective_date() > this_moment_in_time:
            continue

        if type(each) is ledger.ir.Balance_record:
            for b in each.accounts:
                kind, name = b.account
                if kind == ledger.constants.ACCOUNT_EQUITY_T:
                    company, share_price, _ = b.value
                    shares = accounts[kind][name]['shares']
                    shares[company]['price_per_share'] = share_price
                else:
                    ensure_currency_match(accounts, b)
                    accounts[kind][name]['balance'] = b.value[0]
        if type(each) is ledger.ir.Revenue_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Expense_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Transfer_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Equity_tx:
            inflow = decimal.Decimal()
            outflow = decimal.Decimal()

            # There is only one destination account since we can only deposit
            # shares in one account using a single transfer.
            dst_account = None
            src_account = None
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
                inflow += a.value[0]
                src_account = a.account
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                outflow += a.value[0]
                accounts[kind][name]['balance'] += a.value[0]
                dst_account = a.account

            fee_value = decimal.Decimal()
            fee_currency = default_currency
            for t in each.tags:
                s = str(t).strip()
                if s.startswith('fee:'):
                    fee = s.split()[1:]
                    fee_currency = fee[1]
                    fee_value = decimal.Decimal(fee[0])

            # FIXME check currency
            if fee_value:
                kind, name = src_account
                accounts[kind][name]['balance'] += fee_value

            this_shares = None
            for t in each.tags:
                s = str(t).strip()
                if s.startswith('shares:'):
                    shares = s.split()[1:]

                    company = shares[0]
                    this_shares = {
                        'company': company,
                        'no': decimal.Decimal(shares[1]),
                        'fee': {
                            'currency': fee_currency,
                            'amount': fee_value,
                        },
                    }

            pps = abs(-inflow / this_shares['no'])

            this_tx = {
                'base': each,
                'value': -inflow,
                'shares': this_shares,
            }

            if -outflow != (inflow - fee_value):
                fmt = 'inflow {} from {} does not equal outflow {} to {} plus fees {}'
                sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                    ledger.util.colors.colorise(
                        'white',
                        each.to_location(),
                    ),
                    ledger.util.colors.colorise(
                        'red',
                        'error',
                    ),
                    ledger.util.colors.colorise(
                        'white',
                        inflow,
                    ),
                    ledger.util.colors.colorise(
                        'white',
                        '/'.join(src_account),
                    ),
                    ledger.util.colors.colorise(
                        'white',
                        '/'.join(dst_account),
                    ),
                    ledger.util.colors.colorise(
                        'white',
                        outflow,
                    ),
                    ledger.util.colors.colorise(
                        'white',
                        fee_value,
                    ),
                ))
                exit(1)

            both_equity = (
                    dst_account[0] == ledger.constants.ACCOUNT_EQUITY_T
                and src_account[0] == ledger.constants.ACCOUNT_EQUITY_T)
            if both_equity:
                dst_kind, dst_name = dst_account
                src_kind, src_name = src_account

                company = this_shares['company']
                if company not in accounts[dst_kind][dst_name]['shares']:
                    accounts[dst_kind][dst_name]['shares'][company] = {
                        'shares': 0,
                        'price_per_share': decimal.Decimal(),
                        'fees': decimal.Decimal(),
                        'dividends': decimal.Decimal(),
                        'txs': [],
                        # FIXME are these fields below really needed?
                        'balance': decimal.Decimal(),
                        'paid': decimal.Decimal(),
                        'value': decimal.Decimal(),
                        'total_return': decimal.Decimal(),
                    }

                accounts[dst_kind][dst_name]['shares'][company]['txs'].append(this_tx)
                accounts[dst_kind][dst_name]['shares'][company]['price_per_share'] = pps
                accounts[dst_kind][dst_name]['companies'].add(company)

                this_tx = {
                    'base': each,
                    'value': inflow,
                    'shares': {
                        'company': company,
                        'no': -decimal.Decimal(shares[1]),
                        'fee': {
                            'currency': fee_currency,
                            'amount': decimal.Decimal(),
                        },
                    },
                }
                accounts[src_kind][src_name]['shares'][company]['txs'].append(this_tx)
                accounts[src_kind][src_name]['shares'][company]['price_per_share'] = pps
                accounts[src_kind][src_name]['companies'].add(company)
            else:
                kind, name = dst_account
                if kind != ledger.constants.ACCOUNT_EQUITY_T:
                    kind, name = src_account
                if kind != ledger.constants.ACCOUNT_EQUITY_T:
                    fmt = 'no equity account in transfer of {} shares'
                    sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                        ledger.util.colors.colorise(
                            'white',
                            each.to_location(),
                        ),
                        ledger.util.colors.colorise(
                            'red',
                            'error',
                        ),
                        ledger.util.colors.colorise(
                            'white',
                            company,
                        ),
                    ))
                    exit(1)
                company = this_shares['company']
                if company not in accounts[kind][name]['shares']:
                    accounts[kind][name]['shares'][company] = {
                        'shares': 0,
                        'price_per_share': decimal.Decimal(),
                        'fees': decimal.Decimal(),
                        'dividends': decimal.Decimal(),
                        'txs': [],
                        # FIXME are these fields below really needed?
                        'balance': decimal.Decimal(),
                        'paid': decimal.Decimal(),
                        'value': decimal.Decimal(),
                        'total_return': decimal.Decimal(),
                    }

                accounts[kind][name]['shares'][company]['txs'].append(this_tx)
                accounts[kind][name]['shares'][company]['price_per_share'] = pps
                accounts[kind][name]['companies'].add(company)
        if type(each) is ledger.ir.Dividend_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
            for a in each.ins:
                kind, name = a.account
                company, value, _ = a.value
                shares = accounts[kind][name]['shares']
                shares[company]['dividends'] += value

        # FIXME dividends

    book = (book_ir, currency_basket,)

    Screen = ledger.util.screen.Screen
    screen = Screen(Screen.get_tty_width(), 2)

    # Then, prepare and display a report.

    ledger.reporter.report_today((screen, 0), book, default_currency)
    ledger.reporter.report_yesterday((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    ledger.reporter.report_this_month((screen, 0), book, default_currency)
    ledger.reporter.report_last_month((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    ledger.reporter.report_this_year((screen, 0), book, default_currency)
    ledger.reporter.report_all_time((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    report_total_reserves(accounts, book, default_currency)
    report_total_balances(accounts, book, default_currency)
    report_total_equity(accounts, book, default_currency)

main(sys.argv[1:])
