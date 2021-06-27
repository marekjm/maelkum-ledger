import datetime
import decimal
import sys

from . import constants
from . import ir
from . import util


# Underlying report implementations.
# Add code here instead of to the frontend functions defined lower, unless a
# specific piece of code is not shared between reports or does not use values
# calculated here.
def get_txs_of_period(period_span, txs):
    period_begin, period_end = period_span

    expenses = []
    revenues = []
    for each in txs:
        if not isinstance(each, ir.Transaction_record):
            continue

        if each.effective_date().date() > period_end.date():
            continue
        if each.effective_date().date() < period_begin.date():
            continue

        # FIXME currencies
        if type(each) is ir.Expense_tx:
            expenses.append(each)
        elif type(each) is ir.Revenue_tx:
            revenues.append(each)

    return (expenses, revenues,)

def report_common_impl(to_out, txs, book, default_currency, totals = False):
    book, currency_basket = book

    expenses, revenues = txs

    def p(s = ''):
        screen, column = to_out
        screen.print(column, s)

    if (not expenses) and (not revenues):
        p('  No transactions.')
        p()
        return

    total_expenses = decimal.Decimal()
    for each in expenses:
        ins_sum = decimal.Decimal()
        for exin in each.ins:
            val = exin.value
            currency = val[1]
            if currency == default_currency:
                ins_sum += val[0]
            else:
                pair = (currency, default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, currency,)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for {} account named {}'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            util.colors.colorise(
                                'red',
                                'error',
                            ),
                            util.colors.colorise(
                                'white',
                                currency,
                            ),
                            util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            util.colors.colorise(
                                'white',
                                name,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    ins_sum += (val[0] / rate)
                else:
                    ins_sum += (val[0] * rate)
        total_expenses += ins_sum
    p('  Expenses:   {} {}'.format(
        util.colors.colorise(
            util.colors.COLOR_BALANCE_NEGATIVE,
            '{:7.2f}'.format(abs(total_expenses)),
        ),
        default_currency,
    ))

    if not revenues:
        p()
        return

    total_revenues = decimal.Decimal()
    for rx in revenues:
        for each in rx.outs:
            value_raw, currency = each.value
            if currency == default_currency:
                total_revenues += value_raw
            else:
                pair = (currency, default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, currency,)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for rx transaction'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            util.colors.colorise(
                                'white',
                                rx.text[0].location,
                            ),
                            util.colors.colorise(
                                'red',
                                'error',
                            ),
                            util.colors.colorise(
                                'white',
                                currency,
                            ),
                            util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    total_revenues += (value_raw / rate)
                else:
                    total_revenues += (value_raw * rate)

    p('  Revenues:   {} {}'.format(
        util.colors.colorise(
            util.colors.COLOR_BALANCE_POSITIVE,
            '{:7.2f}'.format(abs(total_revenues)),
        ),
        default_currency,
    ))

    net = (total_revenues + total_expenses)
    fmt = '  Net {} {} {}'
    if net < 0:
        p(fmt.format(
            'loss:  ',
            util.colors.colorise_balance(net, '{:7.2f}'),
            default_currency,
        ))
    elif net > 0:
        p(fmt.format(
            'income:',
            util.colors.colorise_balance(net, '{:7.2f}'),
            default_currency,
        ))

    if not totals:
        return

    p('    ----')

    er = (abs(total_expenses) / total_revenues * 100)
    p('  Expenses are {}% of revenues.'.format(
        util.colors.colorise(
            util.colors.COLOR_SPENT_RATIO(er),
            f'{er:5.2f}',
        ),
    ))
    p()

def report_day_impl(to_out, period_day, period_name, book, default_currency):
    def p(s = ''):
        screen, column = to_out
        screen.print(column, s)

    p('{} ({})'.format(
        util.colors.colorise('white', period_name),
        util.colors.colorise('white',
            period_day.strftime(constants.DAYSTAMP_FORMAT)),
    ))
    book, currency_basket = book
    report_common_impl(
        to_out = to_out,
        txs = get_txs_of_period((period_day, period_day,), book),
        book = (book, currency_basket,),
        default_currency = default_currency,
    )

def report_period_impl(to_out, period_span, period_name, book, default_currency):
    def p(s = ''):
        screen, column = to_out
        screen.print(column, s)

    period_begin, period_end = period_span
    p('{} ({} to {})'.format(
        util.colors.colorise('white', period_name),
        util.colors.colorise('white',
            period_begin.strftime(constants.DAYSTAMP_FORMAT)),
        util.colors.colorise('white',
            period_end.strftime(constants.DAYSTAMP_FORMAT)),
    ))

    book, currency_basket = book
    report_common_impl(
        to_out = to_out,
        txs = get_txs_of_period(period_span, book),
        book = (book, currency_basket,),
        default_currency = default_currency,
        totals = True,
    )


# Frontend report functions.
# Add convenience functions here (eg, for for current day, last month) and call
# them from the UI.
def report_today(to_out, book, default_currency):
    report_day_impl(
        to_out,
        datetime.datetime.now(),
        'Today',
        book,
        default_currency,
    )

def report_yesterday(to_out, book, default_currency):
    report_day_impl(
        to_out,
        (datetime.datetime.now() - datetime.timedelta(days = 1)),
        'Yesterday',
        book,
        default_currency,
    )

def report_this_month(to_out, book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_MONTH_FORMAT),
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        to_out,
        (period_begin, period_end,),
        'This month',
        book,
        default_currency,
    )

def report_last_month(to_out, book, default_currency):
    period_end = datetime.datetime.strptime(
        datetime.datetime.now().strftime(constants.THIS_MONTH_FORMAT),
        constants.THIS_MONTH_FORMAT,
    ) - datetime.timedelta(days = 1)
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_MONTH_FORMAT),
        constants.THIS_MONTH_FORMAT,
    )
    report_period_impl(
        to_out,
        (period_begin, period_end,),
        'Last month',
        book,
        default_currency,
    )

def report_this_year(to_out, book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_YEAR_FORMAT),
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        to_out,
        (period_begin, period_end,),
        'This year',
        book,
        default_currency,
    )

def report_all_time(to_out, book, default_currency):
    first = None
    for each in book[0]:
        if isinstance(each, ir.Transaction_record):
            first = each
            break

    period_end = datetime.datetime.now()
    period_begin = first.effective_date()
    report_period_impl(
        to_out,
        (period_begin, period_end,),
        'All time',
        book,
        default_currency,
    )

ACCOUNT_ASSET_T = 'asset'
ACCOUNT_LIABILITY_T = 'liability'
ACCOUNT_EQUITY_T = 'equity'
ACCOUNT_TYPES = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
)

def to_impl(stream, fmt, *args, **kwargs):
    stream.write((fmt + '\n').format(*args, **kwargs))

to_stdout = lambda fmt, *args, **kwargs: to_impl(sys.stdout, fmt, *args, **kwargs)
to_stderr = lambda fmt, *args, **kwargs: to_impl(sys.stderr, fmt, *args, **kwargs)

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
                            util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            util.colors.colorise(
                                'red',
                                'error',
                            ),
                            util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            util.colors.colorise(
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
        util.colors.colorise(
            util.colors.COLOR_PERIOD_NAME,
            period,
        ),
        no_of_accounts,
        util.colors.colorise_balance(
            reserves_total if reserves_foreign else reserves_default),
        default_currency,
        util.colors.colorise_balance(
            reserves_default if reserves_foreign else reserves_total),
        default_currency,
        util.colors.colorise_balance(reserves_foreign),
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
                util.colors.colorise_balance(balance_raw, '{:8.2f}'),
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
                            util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            util.colors.colorise(
                                'red',
                                'error',
                            ),
                            util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            util.colors.colorise(
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
                    util.colors.colorise_balance(
                        (balance_in_default or 0),
                        '{:7.2f}',
                    ),
                    default_currency,
                    util.colors.colorise(
                        util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    acc['currency'],
                    default_currency,
                )

            to_stdout(m)

def report_total_equity(accounts, book, default_currency):
    eq_accounts = accounts['equity']

    book, currency_basket = book

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
                        util.colors.colorise(
                            'white',
                            account['~'].text[0].location,
                        ),
                        util.colors.colorise(
                            'red',
                            'error',
                        ),
                        util.colors.colorise(
                            'white',
                            account['currency'],
                        ),
                        util.colors.colorise(
                            'white',
                            default_currency,
                        ),
                        t,
                        util.colors.colorise(
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
        util.colors.colorise(
            util.colors.COLOR_PERIOD_NAME,
            'State',
        ),
        len(eq_accounts.keys()),
        ('profit' if nominal_gain >= 0 else 'loss'),
        util.colors.colorise_balance(nominal_gain),
        default_currency,
        util.colors.colorise_balance(percent_gain, gain_sign),
        util.colors.colorise_balance(percent_gain),
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

        if (not account['shares']) or (not total_value):
            continue

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

        if True:
            fmt_overview = '  {} => {} {} ({} {}, {}{}%)'
            m = fmt_overview.format(
                name,
                util.colors.colorise_balance(total_value),
                account['currency'],
                util.colors.colorise_balance(gain_nominal),
                account['currency'],
                util.colors.colorise_balance(gain_nominal, gain_sign),
                util.colors.colorise_balance(gain_percent),
            )

            if account['currency'] != default_currency:
                balance_raw = total_value
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
                            util.colors.colorise(
                                'white',
                                account['~'].text[0].location,
                            ),
                            util.colors.colorise(
                                'red',
                                'error',
                            ),
                            util.colors.colorise(
                                'white',
                                account['currency'],
                            ),
                            util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            util.colors.colorise(
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
                    util.colors.colorise_balance(
                        (balance_in_default or 0),
                        '{:7.2f}',
                    ),
                    default_currency,
                    util.colors.colorise(
                        util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    account['currency'],
                    default_currency,
                )

            to_stdout(m)

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


################################################################################
# LEGACY STUFF BELOW!
################################################################################

def legacy_output_table(expenses, revenues, column, include_percentage = False):
    p = lambda t: Book.screen.print(column = column, text = t)

    if (not expenses) and (not revenues):
        p('  No transactions.')
        return

    total_expenses = abs(sum(map(lambda each:
        (each['value'].get('in_default_currency') or each['value']['amount']),
        expenses
    )))
    total_revenues = sum(map(lambda each: each['value']['amount'], revenues))
    total_balance = (total_revenues - total_expenses)
    padding = ('' if total_balance >= 0 else ' ')

    field_length = max(
        len('{:.2f}'.format(total_expenses)),
        len('{:.2f}'.format(total_revenues)),
    )

    if len(expenses) > 1:
        min_expense = min(map(lambda each: abs(each['value']['amount']), expenses))
        max_expense = max(map(lambda each: abs(each['value']['amount']), expenses))
        mean_expense = util.math.mean(list(map(
            lambda each: abs(each['value']['amount']), expenses)))
        median_expense = util.math.median(list(map(
            lambda each: abs(each['value']['amount']), expenses)))
        p('  Expenses range: {:.2f} - {:.2f} {}'.format(min_expense, max_expense, DEFAULT_CURRENCY))
        if mean_expense != median_expense:
            p('  Mean expense:   {:.2f} {}'.format(mean_expense, DEFAULT_CURRENCY))
        p('  Median expense: {:.2f} {}'.format(median_expense, DEFAULT_CURRENCY))
        p('    ----')

    if expenses:
        p('  Expenses:   {}{} {}'.format(
            padding,
            colorise_if_possible(
                COLOR_EXPENSES,
                '{{:{}.2f}}'.format(field_length).format(total_expenses)
            ),
            DEFAULT_CURRENCY,
        ))
    if revenues:
        p('  Revenues:   {}{} {}'.format(
            padding,
            colorise_if_possible(
                COLOR_REVENUES,
                '{{:{}.2f}}'.format(field_length).format(total_revenues)
            ),
            DEFAULT_CURRENCY,
        ))
    if revenues and expenses:
        name_net_income = 'Net income:'
        name_net_loss   = 'Net loss:  '
        p('  {name} {value} {currency}'.format(
            name = (name_net_income if (total_balance >= 0.0) else name_net_loss),
            value = colorise_if_possible(
                COLOR_BALANCE(total_balance),
                '{{:{}.2f}}'.format(field_length + len(padding)).format(total_balance)
            ),
            currency = DEFAULT_CURRENCY,
        ))
    if include_percentage:
        p('    ----')
        percentage_spent = decimal.Decimal('100.0')
        if total_revenues != 0:
            percentage_spent = (total_expenses / total_revenues) * 100
        p('  Expenses are {}% of revenues.'.format(
            colorise_if_possible(
                COLOR_SPENT_RATIO(percentage_spent),
                '{:.2f}'.format(percentage_spent),
            )
        ))

        DEFICIT_THRESHOLD = 100
        if percentage_spent > DEFICIT_THRESHOLD:
            p('  Deficit is {:.4f}% of revenues, or {:.2f} {}.'.format(
                (percentage_spent - DEFICIT_THRESHOLD),
                (total_expenses - total_revenues),
                DEFAULT_CURRENCY,
            ))
            p('  Revenues covered about {:.4f}% of expenses.'.format(
                (total_revenues / total_expenses) * 100,
            ))

def legacy_report_single_day_impl(book, single_day, single_day_name, column):
    expenses = []
    revenues = []
    for each in book['transactions']:
        if single_day.date() != each['timestamp'].date():
            continue

        if each['type'] == 'expense':
            value = each.get('with', {}).get('calculate_as', each['value'])
            if value['currency'] != DEFAULT_CURRENCY:
                c = value['currency']
                r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                in_default_currency = (value['amount'] * r)
                value['in_default_currency'] = in_default_currency
            expenses.append({
                'value': value,
            })
        elif each['type'] == 'revenue':
            revenues.append(each)

    Book.screen.print(column = column, text = '{} ({})'.format(
        colorise_if_possible(COLOR_PERIOD_NAME, single_day_name),
        colorise_if_possible(COLOR_DATETIME, single_day.strftime(DAYSTAMP_FORMAT)),
    ))
    Book.output_table(expenses, revenues, column)

def legacy_report_today(book, column):
    today = datetime.datetime.strptime(
        datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_single_day_impl(book, today, 'Today', column)

def legacy_report_yesterday(book, column):
    yesterday = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 1)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_single_day_impl(book, yesterday, 'Yesterday', column)

def legacy_report_period_impl(book, period_begin, period_end, period_name, column, table_opts = {}):
    expenses = []
    revenues = []
    for each in book['transactions']:
        too_early = (each['timestamp'].date() < period_begin.date())
        too_late = (each['timestamp'].date() > period_end.date())
        if too_early or too_late:
            continue

        if each['type'] == 'expense':
            value = each.get('with', {}).get('calculate_as', each['value'])
            if value['currency'] != DEFAULT_CURRENCY:
                c = value['currency']
                r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                in_default_currency = (value['amount'] * r)
                value['in_default_currency'] = in_default_currency
            expenses.append({
                'timestamp': each['timestamp'],
                'value': value,
            })
        elif each['type'] == 'revenue':
            revenues.append(each)

    Book.screen.print(column = column, text = '{} ({} to {})'.format(
        colorise_if_possible(COLOR_PERIOD_NAME, period_name),
        colorise_if_possible(COLOR_DATETIME, period_begin.strftime(DAYSTAMP_FORMAT)),
        colorise_if_possible(COLOR_DATETIME, period_end.strftime(DAYSTAMP_FORMAT)),
    ))
    Book.output_table(expenses, revenues, column, **table_opts)

    return (expenses, revenues)

def legacy_report_last_7_days(book, column):
    today = datetime.datetime.strptime(
        datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    last_week = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 7)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_period_impl(book, last_week, today, 'Last 7 days', column)

def legacy_report_prev_7_days(book, column):
    today = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 8)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    last_week = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 14)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_period_impl(book, last_week, today, 'Previous 7 days', column)

def legacy_report_last_14_days(book, column):
    today = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 0)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    last_week = datetime.datetime.strptime(
        (datetime.datetime.now() - datetime.timedelta(days = 14)).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_period_impl(book, last_week, today, 'Last 14 days', column)

def legacy_report_a_month_impl(book, first_day, last_day, name, column):
    expenses, revenues = Book.report_period_impl(book, first_day, last_day, name, column, {
        'include_percentage': True,
    })

    if not expenses:
        return expenses, revenues

    diff = (last_day - first_day)
    total_expenses = abs(sum(
        map(lambda each: each['value']['amount'],
        filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
        expenses
    ))))
    daily_average = (total_expenses / (diff.days or 1))
    Book.screen.print(column = column, text = '  Average daily expense is {:.2f} {}.'.format(
        daily_average,
        DEFAULT_CURRENCY,
    ))

    daily_median = {}
    x = first_day
    while x <= last_day:
        daily_median[x.strftime(DAYSTAMP_FORMAT)] = decimal.Decimal()
        x += datetime.timedelta(days = 1)
    for each in expenses:
        # FIXME Account for expenses in non-default currency.
        if each['value']['currency'] != DEFAULT_CURRENCY:
            continue
        daily_median[each['timestamp'].strftime(DAYSTAMP_FORMAT)] += each['value']['amount']
    daily_median = util.math.median(sorted(map(abs, daily_median.values())))
    Book.screen.print(column = column, text = '  Median daily expense is {:.2f} {}.'.format(
        daily_median,
        DEFAULT_CURRENCY,
    ))
    return expenses, revenues

def legacy_report_this_month(book, column):
    today = datetime.datetime.strptime(
        datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    this_month = datetime.datetime.strptime(
        datetime.datetime.now().strftime(THIS_MONTH_FORMAT),
        TIMESTAMP_FORMAT,
    )
    expenses, revenues = Book.report_a_month_impl(book, this_month, today, 'This month', column)
    total_expenses = sum(
        map(lambda each: each['value']['amount'],
        filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
        expenses
    )))
    total_revenues = sum(
        map(lambda each: each['value']['amount'],
        filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
        revenues
    )))

    spending_target = book.get('budgets', {}).get('_target')
    if spending_target is not None:
        last_day_of_this_month = None
        if today.month == 12:
            last_day_of_this_month = datetime.datetime(
                year = today.year + 1,
                month = 1,
                day = 1,
            )
        else:
            last_day_of_this_month = datetime.datetime(
                year = today.year,
                month = today.month + 1,
                day = 1,
            )
        last_day_of_this_month = last_day_of_this_month - datetime.timedelta(days = 1)
        days_left_in_this_month = (last_day_of_this_month - today).days + 1
        available_budgeted_funds = decimal.Decimal()
        if spending_target[0] == '%':
            target_percentage = (spending_target[1] / 100)
            available_budgeted_funds = (total_revenues * target_percentage) - abs(total_expenses)
        elif spending_target[0] == '$':
            available_budgeted_funds = spending_target[1] - total_expenses
        available_budgeted_funds_per_day = (available_budgeted_funds / days_left_in_this_month)
        fmt = '{:7.2f}'
        Book.screen.print(column = column, text = '  Daily expense cap to meet budget: {} {}'.format(
            colorise_if_possible(
                COLOR_BALANCE(available_budgeted_funds_per_day),
                fmt.format(available_budgeted_funds_per_day),
            ),
            DEFAULT_CURRENCY,
        ))
        Book.screen.print(
            column = column,
            text = '  Total expense cap to meet budget: {} {}'.format(
            colorise_if_possible(
                COLOR_BALANCE(available_budgeted_funds),
                fmt.format(available_budgeted_funds),
            ),
            DEFAULT_CURRENCY,
        ))

def legacy_report_last_month(book, column):
    last_day = datetime.datetime.strptime(
        datetime.datetime.now().strftime(THIS_MONTH_FORMAT),
        THIS_MONTH_FORMAT,
    ) - datetime.timedelta(days = 1)
    first_day = datetime.datetime.strptime(
        last_day.strftime(THIS_MONTH_FORMAT),
        THIS_MONTH_FORMAT,
    )
    Book.report_a_month_impl(book, first_day, last_day, 'Last month', column)

def legacy_report_this_year(book, column):
    today = datetime.datetime.strptime(
        datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    this_year = datetime.datetime.strptime(
        datetime.datetime.now().strftime(THIS_YEAR_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_period_impl(book, this_year, today, 'This year', column, {
        'include_percentage': True,
    })

def legacy_report_last_year(book, column):
    this_year = datetime.datetime.now().year
    first_day = datetime.datetime.strptime(
        datetime.datetime(
            year = this_year - 1,
            month = 1,
            day = 1,
        ).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    last_day = datetime.datetime.strptime(
        datetime.datetime(
            year = this_year - 1,
            month = 12,
            day = 31,
        ).strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    Book.report_period_impl(book, first_day, last_day, 'Last year', column, {
        'include_percentage': True,
    })

def legacy_report_total(book, column):
    today = datetime.datetime.strptime(
        datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
        TIMESTAMP_FORMAT,
    )
    first = today
    if book['transactions']:
        first = Book.first_recorded_transaction(book)['timestamp']
    Book.report_period_impl(book, first, today, 'All time', column, {
        'include_percentage': True,
    })

def legacy_first_recorded_transaction(book):
    return sorted(
        book['transactions'],
        key = lambda each: each['timestamp']
    )[0]

def legacy_last_recorded_transaction(book):
    return sorted(
        book['transactions'],
        key = lambda each: each['timestamp'],
        reverse = True,
    )[0]
