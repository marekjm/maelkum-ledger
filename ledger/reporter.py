import datetime
import decimal

from . import constants
from . import ir
from . import util


def report_day_impl(period_day, period_name, book, default_currency):
    book, currency_basket = book

    expenses = []
    revenues = []
    for each in book:
        if each.timestamp.date() != period_day.date():
            continue
        if type(each) is ir.Expense_tx:
            expenses.append(each)
        elif type(each) is ir.Revenue_tx:
            revenues.append(each)

    p = print

    p('{} ({})'.format(
        util.colors.colorise('white', period_name),
        util.colors.colorise('white',
            period_day.strftime(constants.DAYSTAMP_FORMAT)),
    ))
    if (not expenses) and (not revenues):
        p('  No transactions.')
        p()
        return

    total_expenses = decimal.Decimal()
    for each in expenses:
        ins_sum = sum(map(lambda x: x.value[0], each.ins))
        total_expenses += ins_sum
    p('  Expenses: {} {}'.format(
        util.colors.colorise(
            util.colors.COLOR_BALANCE_NEGATIVE,
            '{:.2f}'.format(abs(total_expenses)),
        ),
        default_currency,
    ))
    p()

    total_revenues = decimal.Decimal()

def report_today(book, default_currency):
    report_day_impl(
        datetime.datetime.now(),
        'Today',
        book,
        default_currency,
    )

def report_yesterday(book, default_currency):
    report_day_impl(
        (datetime.datetime.now() - datetime.timedelta(days = 1)),
        'Yesterday',
        book,
        default_currency,
    )

def report_period_impl(period_span, period_name, book, default_currency):
    book, currency_basket = book

    period_begin, period_end = period_span

    p = print

    p('{} ({} to {})'.format(
        util.colors.colorise('white', period_name),
        util.colors.colorise('white',
            period_begin.strftime(constants.DAYSTAMP_FORMAT)),
        util.colors.colorise('white',
            period_end.strftime(constants.DAYSTAMP_FORMAT)),
    ))

    expenses = []
    revenues = []
    for each in book:
        if not isinstance(each, ir.Transaction_record):
            continue
        if each.effective_date() > period_end:
            continue
        if each.effective_date() < period_begin:
            continue
        if type(each) is ir.Expense_tx:
            expenses.append(each)
        elif type(each) is ir.Revenue_tx:
            revenues.append(each)

    if (not expenses) and (not revenues):
        p('  No transactions.')
        p()
        return

    total_expenses = decimal.Decimal()
    for each in expenses:
        ins_sum = sum(map(lambda x: x.value[0], each.ins))
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
    for each in revenues:
        outs_sum = sum(filter(lambda x: x is not None, map(lambda x: x.value[0],
            each.outs)))
        total_revenues += outs_sum
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

    p('    ----')

    er = (abs(total_expenses) / total_revenues * 100)
    p('  Expenses are {}% of revenues.'.format(
        util.colors.colorise(
            util.colors.COLOR_SPENT_RATIO(er),
            f'{er:5.2f}',
        ),
    ))
    p()

def report_this_month(book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_MONTH_FORMAT),
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        (period_begin, period_end,),
        'This month',
        book,
        default_currency,
    )

def report_this_year(book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_YEAR_FORMAT),
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        (period_begin, period_end,),
        'This year',
        book,
        default_currency,
    )


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
        mean_expense = ledger.util.math.mean(list(map(
            lambda each: abs(each['value']['amount']), expenses)))
        median_expense = ledger.util.math.median(list(map(
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
    daily_median = ledger.util.math.median(sorted(map(abs, daily_median.values())))
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
