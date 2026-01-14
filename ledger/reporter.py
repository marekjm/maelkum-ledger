import datetime
import decimal
import sys

import colored

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

    return (
        expenses,
        revenues,
    )


def aggregate_groups(book, expense_sinks, revenue_faucets):
    for gr in book:
        if type(gr) is ir.Group:
            for streams in (
                expense_sinks,
                revenue_faucets,
            ):
                group_name = f"[[{gr.name}]]"
                streams[group_name] = decimal.Decimal()
                for gr_member in gr.members:
                    match streams.get(gr_member):
                        case None:
                            pass
                        case x:
                            streams[group_name] += x
                            del streams[gr_member]


def report_common_impl(
    to_out,
    txs,
    book,
    default_currency,
    totals=False,
    monthly_breakdown=None,
    sinks=None,
    faucets=None,
    aggregate=False,
):
    book, currency_basket = book

    expenses, revenues = txs

    COLUMN_WIDTH = to_out[0]._width // to_out[0]._columns

    def p(s=""):
        screen, column = to_out
        screen.print(column, s)

    if (not expenses) and (not revenues):
        p("  No transactions.")
        p()
        return

    expense_sinks = {}
    expense_values = []
    total_expenses = decimal.Decimal()
    for each in expenses:
        ins_sum = decimal.Decimal()
        for exin in each.ins:
            val = exin.value
            currency = val[1]
            if currency == default_currency:
                val = val[0]
            else:
                pair = (
                    currency,
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            currency,
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for {} account named {}"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    acc["~"].text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    currency,
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                                t,
                                util.colors.colorise(
                                    "white",
                                    name,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    val = val[0] / rate
                else:
                    val = val[0] * rate

            ins_sum += val
        for exout in each.outs:
            kind, sink = exout.account
            if kind is not None:
                continue
            if sink not in expense_sinks:
                expense_sinks[sink] = decimal.Decimal()
            expense_sinks[sink] += ins_sum
        expense_values.append(ins_sum)
        total_expenses += ins_sum

    revenue_faucets = {}
    revenue_values = []
    total_revenues = decimal.Decimal()
    for rx in revenues:
        rev_sum = decimal.Decimal()
        for each in rx.outs:
            value_raw, currency = each.value
            if currency == default_currency:
                rev_sum += value_raw
            else:
                pair = (
                    currency,
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            currency,
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for rx transaction"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    rx.text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    currency,
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    rev_sum += value_raw / rate
                else:
                    rev_sum += value_raw * rate
        for each in rx.ins:
            kind, faucet = each.account

            # Revenue from an equity account means dividends, and should be
            # recorded with the company's ticker as the faucet. Lumping all
            # revenue sources under the exchange's name would be misleading.
            #
            # The revenue does not come from NYSE but from company XYZ.
            if kind == constants.ACCOUNT_EQUITY_T:
                faucet = "{} ({})".format(
                    each.value[0],  # Name of the company, and of
                    faucet,  # the account in which the shares are held.
                )

            if faucet not in revenue_faucets:
                revenue_faucets[faucet] = decimal.Decimal()
            revenue_faucets[faucet] += rev_sum
        revenue_values.append(rev_sum)
        total_revenues += rev_sum

    if aggregate:
        aggregate_groups(book, expense_sinks, revenue_faucets)

    # Report net flows from sinks and faucets.
    #
    # The same entity can be both an expense sink and a revenue faucet. For
    # example, you can get rent from an apartment but it also costs money to
    # renovate and keep up to standard. Anyway, the code below is responsible
    # for adjusting raw data on the sinks and faucets so that they represent the
    # net cash flows.
    #
    # For personal finance this is a better idea than presenting the same entity
    # as both faucet and sink for money. It is the net flow that matters the
    # most at the level of an individual person, I think.
    faucets_and_sinks = set()
    faucets_and_sinks.update(expense_sinks.keys())
    faucets_and_sinks.update(revenue_faucets.keys())
    for each in faucets_and_sinks:
        sink = expense_sinks.get(each)
        faucet = revenue_faucets.get(each)
        if (sink is None) or (faucet is None):
            continue

        net = sink + faucet

        if abs(net) < decimal.Decimal("0.01"):
            # If the net is 0 then the entity does not really influence the
            # outcome. We can derive $$$ of revenue from it, but if it is also a
            # sink for $$$ then we could ditch interaction with the entity and
            # the net cash flow would be unaffected.
            del expense_sinks[each]
            del revenue_faucets[each]
            continue

        # Otherwise, the entity is either a net sink, or a net faucet.
        if net < 0:
            expense_sinks[each] = net
            del revenue_faucets[each]
        else:
            revenue_faucets[each] = net
            del expense_sinks[each]

    net_expenses = sum(expense_sinks.values())
    net_revenues = sum(revenue_faucets.values())

    # Base values for expenses and revenues can be either the total (ie, every
    # expense incurred and revenue earned during the analysed period) or the net
    # value. The net value is calculated by summing expenses and revenues and
    # only considering the final outcome.
    #
    # Sinks are ALREADY net so reporting precentages makes more sense based on
    # the net value.
    #
    # Keep in mind that this distinction (total vs net) is only meaningful and
    # affects calculations for entities that are both expense sinks and revenue
    # faucets. To give a couple of more concrete examples:
    #
    #  1/ Assume that you are renting a flat. Each month you must pay the
    #     landlord a certain amount of cash. The landlord is a pure expense sink
    #     and WILL NOT be affected by the net/total distintion.
    #  2/ You go to work and receive a paycheck every month. The employer is a
    #     pure revenue faucet.
    #  3/ You and your mother have a birthday the same month, and you both gift
    #     each other $100. In this case the mother is BOTH an expense sink (as
    #     you have given her $100) and a revenue faucet (she has given you $100).
    #     The total cash flow is +$100 and -$100, but the net flow is $0.
    #     Because there is a sink and a faucet for your mother, she WILL be
    #     affected by the net/total distintion.
    BASE_NET = True
    base_expenses = net_expenses if BASE_NET else total_expenses
    base_revenues = net_revenues if BASE_NET else total_revenues

    fmt = "  Expenses:   {} {}".format(
        util.colors.colorise(
            util.colors.COLOR_BALANCE_NEGATIVE,
            "{:9.2f}".format(abs(base_expenses)),
        ),
        default_currency,
    )
    if monthly_breakdown is not None:
        fmt += "  (p/m: {} {})".format(
            util.colors.colorise(
                util.colors.COLOR_BALANCE_NEGATIVE,
                "{:7.2f}".format(abs(base_expenses) / (monthly_breakdown or 1)),
            ),
            default_currency,
        )
    p(fmt)

    if not revenues:
        p()
        return

    fmt = "  Revenues:   {} {}".format(
        util.colors.colorise(
            util.colors.COLOR_BALANCE_POSITIVE,
            "{:9.2f}".format(abs(net_revenues)),
        ),
        default_currency,
    )
    if monthly_breakdown is not None:
        fmt += "  (p/m: {} {})".format(
            util.colors.colorise(
                util.colors.COLOR_BALANCE_POSITIVE,
                "{:7.2f}".format(abs(base_revenues) / (monthly_breakdown or 1)),
            ),
            default_currency,
        )
    p(fmt)

    net = base_revenues + base_expenses
    fmt = "  Net {} {} {}"
    if net <= 0:
        fmt = fmt.format(
            "loss:  ",
            util.colors.colorise_balance(net, "{:9.2f}"),
            default_currency,
        )
    elif net > 0:
        fmt = fmt.format(
            "income:",
            util.colors.colorise_balance(net, "{:9.2f}"),
            default_currency,
        )
    if monthly_breakdown is not None:
        fmt += "  (p/m: {} {})".format(
            util.colors.colorise(
                (
                    util.colors.COLOR_BALANCE_NEGATIVE
                    if net < 0
                    else util.colors.COLOR_BALANCE_POSITIVE
                ),
                "{:7.2f}".format(net / (monthly_breakdown or 1)),
            ),
            default_currency,
        )
    p(fmt)

    if not totals:
        return

    p("    ----")

    er = abs(base_expenses) / base_revenues * 100
    p(
        "  Expenses are {}% of revenues.".format(
            util.colors.colorise(
                util.colors.COLOR_SPENT_RATIO(er),
                f"{er:5.2f}",
            ),
        )
    )

    # Expense value ranges, average and median, and other statistics.
    if expense_values:
        avg_expense = abs(util.math.mean(expense_values))
        med_expense = abs(util.math.median(expense_values))
        max_expense = abs(min(expense_values))
        min_expense = abs(max(expense_values))
        p(
            "  Expense range is {:.2f} ∾ {:.2f} {}.".format(
                min_expense,
                max_expense,
                default_currency,
            )
        )
        p(
            "     ...average is {:.2f} {}.".format(
                avg_expense,
                default_currency,
            )
        )
        p(
            "      ...median is {:.2f} {}.".format(
                med_expense,
                default_currency,
            )
        )

    expense_sinks_sorted = sorted(expense_sinks.items(), key=lambda each: each[1])
    revenue_faucets_sorted = sorted(
        revenue_faucets.items(), key=lambda each: each[1], reverse=True
    )

    report_max_ts = max(revenues[-1].effective_date(), expenses[-1].effective_date())
    report_min_ts = min(revenues[0].effective_date(), expenses[0].effective_date())
    report_time_span = report_max_ts - report_min_ts
    is_all_time_report = report_time_span.days > 367

    sink_faucet_value_len = 0
    if expense_sinks_sorted:
        sink_faucet_value_len = max(
            sink_faucet_value_len, abs(expense_sinks_sorted[0][1])
        )
    if revenue_faucets_sorted:
        sink_faucet_value_len = max(sink_faucet_value_len, revenue_faucets_sorted[0][1])
    sink_faucet_value_len = len("{:.2f}".format(abs(sink_faucet_value_len)))
    fmt_value = lambda value: ("{{:{}.2f}}".format(sink_faucet_value_len).format(value))

    # If sinks and faucets are given some non-default values but we have fewer
    # faucets then requested then let's provide additional info about more
    # sinks. This way we don't waste any screen real estate that may be free.
    #
    # This is unwanted however, if the caller EXPLICITLY (ie, by passing a
    # non-none number of sinks) requested no sinks to be displayed.
    if sinks is not None and faucets is not None and sinks != 0:
        if len(revenue_faucets_sorted) < faucets:
            space_left = faucets - len(revenue_faucets_sorted)
            sinks += space_left

    # Expense sink statistics.
    if expense_sinks_sorted and (sinks or sinks is None):
        sink_1st = expense_sinks_sorted[0] if len(expense_sinks_sorted) > 0 else None
        sink_2nd = expense_sinks_sorted[1] if len(expense_sinks_sorted) > 1 else None
        sink_3rd = expense_sinks_sorted[2] if len(expense_sinks_sorted) > 2 else None

        cv = lambda s: util.colors.colorise(util.colors.COLOR_EXPENSES, s)
        cp = lambda s: util.colors.colorise("white", f"{s:6.2f}%")

        LABEL_BG = "dark_red_1"
        # LABEL_FG = "grey_62" # default fg colour
        LABEL_FG = "grey_78"
        LABEL_WIDTH = COLUMN_WIDTH - 32 - 2
        deepest_sink = (sink_1st[1] / base_expenses) if sink_1st is not None else None

        if sink_1st is not None:
            p(
                "  Sink   1st: {} {} {} {}".format(
                    cv(fmt_value(abs(sink_1st[1]))),
                    default_currency,
                    cp((sink_1st[1] / base_expenses) * 100),
                    (
                        colored.bg(LABEL_BG)
                        + colored.fg(LABEL_FG)
                        + sink_1st[0].ljust(LABEL_WIDTH)
                        + colored.attr("reset")
                    ),
                )
            )
        if sink_2nd is not None:
            ratio = sink_2nd[1] / base_expenses

            label_bg = int(LABEL_WIDTH * (ratio / deepest_sink))
            label = sink_2nd[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                "         2nd: {} {} {} {}".format(
                    cv(fmt_value(abs(sink_2nd[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )
        if sink_3rd is not None:
            ratio = sink_3rd[1] / base_expenses

            label_bg = int(LABEL_WIDTH * (ratio / deepest_sink))
            label = sink_3rd[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                "         3rd: {} {} {} {}".format(
                    cv(fmt_value(abs(sink_3rd[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )

        extra_sinks = 7 + (5 if monthly_breakdown else 0)

        if is_all_time_report:
            extra_sinks += 27

        if sinks is not None:
            extra_sinks = max(0, sinks - 3)

        fmt = (
            "       {:3d}th: {} {} {} {}"
            if (extra_sinks >= 7)
            else "         {:1d}th: {} {} {} {}"
        )
        for n in range(3, 3 + extra_sinks):
            if n >= len(expense_sinks_sorted):
                break

            sink_nth = expense_sinks_sorted[n]

            ratio = sink_nth[1] / base_expenses

            label_bg = int(LABEL_WIDTH * (ratio / deepest_sink))
            label = sink_nth[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                fmt.format(
                    (n + 1),
                    cv(fmt_value(abs(sink_nth[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )

    # Expense faucet statistics.
    if revenue_faucets_sorted and (faucets or faucets is None):
        faucet_1st = (
            revenue_faucets_sorted[0] if len(revenue_faucets_sorted) > 0 else None
        )
        faucet_2nd = (
            revenue_faucets_sorted[1] if len(revenue_faucets_sorted) > 1 else None
        )
        faucet_3rd = (
            revenue_faucets_sorted[2] if len(revenue_faucets_sorted) > 2 else None
        )

        cv = lambda s: util.colors.colorise(util.colors.COLOR_REVENUES, s)
        cp = lambda s: util.colors.colorise("white", f"{s:6.2f}%")

        LABEL_BG = "dark_green"
        LABEL_FG = "grey_82"
        LABEL_WIDTH = COLUMN_WIDTH - 32 - 2

        # Visibility multiplier is only useful when one faucet absolutely dwarfs
        # all the others. Naive implementation would just show a bar for this
        # one faucet and leave all the others without background bars.
        #
        # This breaks down, however, when all the faucets contribute on the same
        # order of mangnitute. This is why the VISIBILITY_MULTIPLIER must be
        # reset to one when there is no single faucet overwhelming the others.
        VISIBILITY_MULTIPLIER = 5
        # FIXME Detect true difference between faucets' contributions, and not
        # hardcode a quick, dirty "fix".
        if len(revenue_faucets_sorted) <= 3:
            VISIBILITY_MULTIPLIER = 1

        deepest_faucet = (
            (faucet_1st[1] / base_revenues) if faucet_1st is not None else None
        )

        if faucet_1st is not None:
            p(
                "  Faucet 1st: {} {} {} {}".format(
                    cv(fmt_value(abs(faucet_1st[1]))),
                    default_currency,
                    cp((faucet_1st[1] / base_revenues) * 100),
                    (
                        colored.bg(LABEL_BG)
                        + colored.fg(LABEL_FG)
                        + faucet_1st[0].ljust(LABEL_WIDTH)
                        + colored.attr("reset")
                    ),
                )
            )
        if faucet_2nd is not None:
            ratio = faucet_2nd[1] / base_revenues

            label_bg = int(
                LABEL_WIDTH * (ratio * VISIBILITY_MULTIPLIER / deepest_faucet)
            )
            label = faucet_2nd[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                "         2nd: {} {} {} {}".format(
                    cv(fmt_value(abs(faucet_2nd[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )
        if faucet_3rd is not None:
            ratio = faucet_3rd[1] / base_revenues

            label_bg = int(
                LABEL_WIDTH * (ratio * VISIBILITY_MULTIPLIER / deepest_faucet)
            )
            label = faucet_3rd[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                "         3rd: {} {} {} {}".format(
                    cv(fmt_value(abs(faucet_3rd[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )

        extra_faucets = 7 + (5 if monthly_breakdown else 0)

        if is_all_time_report:
            extra_faucets += 30

        if faucets is not None:
            extra_faucets = max(0, faucets - 3)

        fmt = (
            "       {:3d}th: {} {} {} {}"
            if (extra_faucets >= 7)
            else "         {:1d}th: {} {} {} {}"
        )
        for n in range(3, 3 + extra_faucets):
            if n >= len(revenue_faucets_sorted):
                break

            faucet_nth = revenue_faucets_sorted[n]

            ratio = faucet_nth[1] / base_revenues

            label_bg = int(
                LABEL_WIDTH * (ratio * VISIBILITY_MULTIPLIER / deepest_faucet)
            )
            label = faucet_nth[0].ljust(LABEL_WIDTH)
            if label_bg:
                with_bg = label[:label_bg]
                plain = label[label_bg:]
                label = (
                    colored.bg(LABEL_BG)
                    + colored.fg(LABEL_FG)
                    + with_bg
                    + colored.attr("reset")
                ) + plain

            p(
                fmt.format(
                    (n + 1),
                    cv(fmt_value(abs(faucet_nth[1]))),
                    default_currency,
                    cp(ratio * 100),
                    label,
                )
            )

    p()


def report_day_impl(to_out, period_day, period_name, book, default_currency):
    def p(s=""):
        screen, column = to_out
        screen.print(column, s)

    p(
        "{} ({})".format(
            util.colors.colorise("white", period_name),
            util.colors.colorise(
                "white", period_day.strftime(constants.DAYSTAMP_FORMAT)
            ),
        )
    )
    book, currency_basket = book
    report_common_impl(
        to_out=to_out,
        txs=get_txs_of_period(
            (
                period_day,
                period_day,
            ),
            book,
        ),
        book=(
            book,
            currency_basket,
        ),
        default_currency=default_currency,
    )


def report_period_impl(
    to_out,
    period_span,
    period_name,
    book,
    default_currency,
    monthly_breakdown=None,
    sinks=None,
    faucets=None,
    aggregate=False,
):
    def p(s=""):
        screen, column = to_out
        screen.print(column, s)

    period_begin, period_end = period_span
    p(
        "{} ({} to {})".format(
            util.colors.colorise("white", period_name),
            util.colors.colorise(
                "white", period_begin.strftime(constants.DAYSTAMP_FORMAT)
            ),
            util.colors.colorise(
                "white", period_end.strftime(constants.DAYSTAMP_FORMAT)
            ),
        )
    )

    if monthly_breakdown:

        def count_months_in_period(begin, end):
            full_years = end.year - begin.year
            months = end.month - begin.month + 1
            return (full_years * 12) + months

        monthly_breakdown = count_months_in_period(period_begin, period_end)
    else:
        monthly_breakdown = None

    book, currency_basket = book
    report_common_impl(
        to_out=to_out,
        txs=get_txs_of_period(period_span, book),
        book=(
            book,
            currency_basket,
        ),
        default_currency=default_currency,
        totals=True,
        monthly_breakdown=monthly_breakdown,
        sinks=sinks,
        faucets=faucets,
        aggregate=aggregate,
    )


# Frontend report functions.
# Add convenience functions here (eg, for for current day, last month) and call
# them from the UI.
def report_today(to_out, book, default_currency):
    report_day_impl(
        to_out,
        datetime.datetime.now(),
        "Today",
        book,
        default_currency,
    )


def report_yesterday(to_out, book, default_currency):
    report_day_impl(
        to_out,
        (datetime.datetime.now() - datetime.timedelta(days=1)),
        "Yesterday",
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
        (
            period_begin,
            period_end,
        ),
        "This month",
        book,
        default_currency,
    )


def report_last_month(to_out, book, default_currency):
    period_end = datetime.datetime.strptime(
        datetime.datetime.now().strftime(constants.THIS_MONTH_FORMAT),
        constants.THIS_MONTH_FORMAT,
    ) - datetime.timedelta(days=1)
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_MONTH_FORMAT),
        constants.THIS_MONTH_FORMAT,
    )
    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        "Last month",
        book,
        default_currency,
    )


def report_month(
    to_out, title, year_and_month, book, default_currency, sinks=None, faucets=None
):
    year, month = year_and_month

    period_begin = datetime.datetime.strptime(
        f"{year}-{month}-01T00:00",
        constants.THIS_MONTH_FORMAT,
    )

    period_end = None
    if month == 12:
        period_end = f"{year + 1}-01-01T00:00"
    else:
        period_end = f"{year}-{month + 1}-01T00:00"
    period_end = datetime.datetime.strptime(
        period_end, constants.THIS_MONTH_FORMAT
    ) - datetime.timedelta(seconds=1)

    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        title,
        book,
        default_currency,
        sinks=sinks,
        faucets=faucets,
    )


def report_this_year(to_out, book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        period_end.strftime(constants.THIS_YEAR_FORMAT),
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        "This year",
        book,
        default_currency,
        monthly_breakdown=True,
    )


def report_last_year(to_out, book, default_currency):
    period_end = datetime.datetime.now()
    period_begin = datetime.datetime.strptime(
        constants.THIS_YEAR_FORMAT.replace("%Y", str(period_end.year - 1)),
        constants.THIS_YEAR_FORMAT,
    )
    period_end = constants.LAST_YEAR_DAY_FORMAT.replace("%Y", str(period_end.year - 1))
    period_end = datetime.datetime.strptime(
        period_end,
        constants.TIMESTAMP_FORMAT,
    )
    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        "Last year",
        book,
        default_currency,
        monthly_breakdown=True,
    )


def report_year(
    to_out,
    title,
    year,
    book,
    default_currency,
    sinks=None,
    faucets=None,
    aggregate=True,
):
    period_begin = datetime.datetime.strptime(
        f"{year}-01-01T00:00",
        constants.TIMESTAMP_FORMAT,
    )

    # Analyse the FULL year, even if it includes the future (in case current
    # year is requested). Use the report_this_year() function if you do not want
    # the future included.
    period_end = datetime.datetime.strptime(
        f"{year}-12-31T23:59",
        constants.TIMESTAMP_FORMAT,
    )

    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        title,
        book,
        default_currency,
        monthly_breakdown=True,
        sinks=sinks,
        faucets=faucets,
        aggregate=aggregate,
    )


def report_all_time(to_out, book, default_currency):
    first = None
    for each in book[0]:
        if isinstance(each, ir.Transaction_record):
            first = each
            break

    if first is None:
        return

    period_end = datetime.datetime.now()
    period_begin = first.effective_date()
    report_period_impl(
        to_out,
        (
            period_begin,
            period_end,
        ),
        "All time",
        book,
        default_currency,
        monthly_breakdown=True,
        aggregate=True,
    )


ACCOUNT_ASSET_T = "asset"
ACCOUNT_LIABILITY_T = "liability"
ACCOUNT_EQUITY_T = "equity"
ACCOUNT_TYPES = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
)


def to_impl(stream, fmt, *args, **kwargs):
    stream.write((fmt + "\n").format(*args, **kwargs))


to_stdout = lambda fmt, *args, **kwargs: to_impl(sys.stdout, fmt, *args, **kwargs)
to_stderr = lambda fmt, *args, **kwargs: to_impl(sys.stderr, fmt, *args, **kwargs)


def report_total_impl(
    to_out, period, account_types, accounts, book, default_currency, filter=None
):
    reserves_default = decimal.Decimal()
    reserves_foreign = decimal.Decimal()
    no_of_accounts = 0
    for t in account_types:
        for name, acc in accounts[t].items():
            if not acc["active"]:
                continue
            if filter is not None and not filter(acc):
                continue

            no_of_accounts += 1
            if acc["currency"] == default_currency:
                reserves_default += acc["balance"]
            else:
                _, currency_basket = book

                pair = (
                    acc["currency"],
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            acc["currency"],
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for {} account named {}"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    acc["~"].text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    acc["currency"],
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                                t,
                                util.colors.colorise(
                                    "white",
                                    name,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    reserves_foreign += acc["balance"] / rate
                else:
                    reserves_foreign += acc["balance"] * rate

    reserves_total = reserves_default + reserves_foreign

    fmt = "{} on all {} account(s): "
    if reserves_foreign:
        fmt += "≈{} {} ({} {} + ≈{} {} in foreign currencies)"
    else:
        fmt += "{} {}"

    def p(s=""):
        screen, column = to_out
        screen.print(column, s)

    (p if to_out is not None else to_stdout)(
        fmt.format(
            util.colors.colorise(
                util.colors.COLOR_PERIOD_NAME,
                period,
            ),
            no_of_accounts,
            util.colors.colorise_balance(
                reserves_total if reserves_foreign else reserves_default
            ),
            default_currency,
            util.colors.colorise_balance(
                reserves_default if reserves_foreign else reserves_total
            ),
            default_currency,
            util.colors.colorise_balance(reserves_foreign),
            default_currency,
        )
    )


def report_total_reserves(to_out, accounts, book, default_currency):
    report_total_impl(
        to_out,
        "Reserve",
        (
            ACCOUNT_ASSET_T,
            ACCOUNT_LIABILITY_T,
        ),
        accounts,
        book,
        default_currency,
        filter=lambda a: ("non_reserve" not in a["tags"]),
    )


def report_total_balances(to_out, accounts, book, default_currency):
    report_total_impl(
        to_out,
        "Balance",
        ACCOUNT_TYPES,
        accounts,
        book,
        default_currency,
    )

    longest_account_name = 0
    for t in ACCOUNT_TYPES:
        for a in accounts[t].keys():
            if not accounts[t][a]["active"]:
                continue
            longest_account_name = max(longest_account_name, len(a))

    def sort_main_on_top(accounts):
        keys = sorted(
            accounts.keys(),
            key=lambda k: (
                "non_reserve" in accounts[k]["tags"],
                k,
            ),
        )
        keys = sorted(
            keys,
            key=lambda k: ("main" in accounts[k]["tags"]),
            reverse=True,
        )
        return keys

    for t in ACCOUNT_TYPES:
        for name in sort_main_on_top(accounts[t]):
            acc = accounts[t][name]
            tags = acc["tags"]

            if not acc["active"]:
                continue

            if "overview" not in tags:
                continue

            m = ""

            balance_raw = acc["balance"]
            if (balance_raw == 0) and ("only_if_negative" in tags):
                continue

            fmt = "  {}: {} {}"
            m += fmt.format(
                name.ljust(longest_account_name),
                util.colors.colorise_balance(balance_raw, "{:9.2f}"),
                acc["currency"],
            )

            balance_in_default = None
            rate = None
            if acc["currency"] != default_currency and acc["balance"]:
                _, currency_basket = book

                pair = (
                    acc["currency"],
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            acc["currency"],
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for {} account named {}"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    acc["~"].text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    acc["currency"],
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                                t,
                                util.colors.colorise(
                                    "white",
                                    name,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    balance_in_default = balance_raw / rate
                else:
                    balance_in_default = balance_raw * rate

                # FIXME display % gain/loss depending on exchange rate
                fmt = " ≅ {} {} at {} {}/{} rate"
                m += fmt.format(
                    util.colors.colorise_balance(
                        (balance_in_default or 0),
                        "{:7.2f}",
                    ),
                    default_currency,
                    util.colors.colorise(
                        util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    acc["currency"],
                    default_currency,
                )

            def p(s=""):
                screen, column = to_out
                screen.print(column, s)

            (p if to_out is not None else to_stdout)(m)


def report_total_equity(to_out, accounts, book, default_currency):
    eq_accounts = accounts["equity"]
    if not eq_accounts:
        return

    book, currency_basket = book

    def p(s=""):
        if to_out is not None:
            screen, column = to_out
            screen.print(column, s)
        else:
            to_stdout(s)

    total_market_value = decimal.Decimal()
    total_cost_basis = decimal.Decimal()
    total_return = decimal.Decimal()
    if True:
        for name, account in eq_accounts.items():
            mv = account["v2_market_value"]
            cb = account["v2_cost_basis"]
            tr = account["v2_total_return"]

            if account["currency"] != default_currency:
                pair = (
                    account["currency"],
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            account["currency"],
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for {} account named {}"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    account["~"].text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    account["currency"],
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                                t,
                                util.colors.colorise(
                                    "white",
                                    name,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    mv = mv / rate
                    cb = cb / rate
                    tr = tr / rate
                else:
                    mv = mv * rate
                    cb = cb * rate
                    tr = tr * rate

            total_market_value += mv
            total_cost_basis += cb
            total_return += tr

        gain_sign = "+" if total_return > 0 else ""

        # Display a basic overview of total market value and return.
        fmt = "{} of {} equity account(s): ≈{} {}, total {} ≈ {} {}, {}{}%"
        p(
            fmt.format(
                util.colors.colorise(
                    util.colors.COLOR_PERIOD_NAME,
                    "State",
                ),
                len(eq_accounts.keys()),
                util.colors.colorise_balance(total_market_value),
                default_currency,
                ("profit" if total_return >= 0 else "loss"),
                util.colors.colorise_balance(total_return),
                default_currency,
                util.colors.colorise_balance(total_return, gain_sign),
                util.colors.colorise_balance(total_return / total_cost_basis * 100),
            )
        )

    # Discover the maximal length of a company name (ie, the ticker) and the
    # maximal length of the shares number. This is used later for to align the
    # report in a readable way.
    company_name_length = 0
    shares_length = 0
    for account in eq_accounts.values():
        for name, shares in account["shares"].items():
            company_name_length = max(company_name_length, len(name))
            shares_length = max(shares_length, len(str(shares["shares"])))

    # Companies for whom total return is not equal to share price fluctuation
    # result (eg, because they paid a dividend) have their names prefixed with a
    # star.
    #
    # To make the marker look good it is attached to the company name BEFORE
    # justification so that it looks like this:
    #
    #         * DIVIDEND
    #        NO-DIVIDEND
    #
    # instead of liket this:
    #
    #      *    DIVIDEND
    #        NO-DIVIDEND
    company_name_length += 2

    shares_length = 0
    if len(account["shares"].keys()):
        shares_length = max(
            map(lambda _: len(str(_["shares"])), account["shares"].values())
        )

    ALT_BG = "grey_11"

    def header_footer():
        p(
            "   {}   {:7}   {:7}          Share   {:7}           {}   Total return".format(
                (" " * company_name_length),
                colored.bg(ALT_BG)
                + util.colors.colorise(
                    util.colors.COLOR_SHARE_PRICE, " Market".ljust(8)
                ),
                "Average",
                "Market",
                colored.bg(ALT_BG)
                + util.colors.colorise(
                    util.colors.COLOR_SHARE_PRICE, "  Cost".ljust(8)
                ),
            )
        )
        p(
            "   {}   {:7}   {:7}          Count   {:7}   Port%   {}    TR$    TR% ".format(
                (" " * company_name_length),
                colored.bg(ALT_BG)
                + util.colors.colorise(
                    util.colors.COLOR_SHARE_PRICE, " Price".ljust(8)
                ),
                " Price",
                "Value",
                colored.bg(ALT_BG)
                + util.colors.colorise(
                    util.colors.COLOR_SHARE_PRICE, "  Basis".ljust(8)
                ),
            )
        )

    header_footer()

    for name in sorted(eq_accounts.keys()):
        account = eq_accounts[name]

        if not account["v2_market_value"]:
            continue

        ac = account["currency"]

        if True:
            mv = account["v2_market_value"]
            cb = account["v2_cost_basis"]
            tr = account["v2_total_return"]
            tr_sign = "+" if tr >= 0 else ""

            # FIXME This is buggy. The total return on an exchange gives...
            # weird results like +2712% return. I don't know if it's that useful
            # anyway. Maybe just remove it.
            title = "  {} => {} {} ({}{} {}, {}{}%)".format(
                name,
                util.colors.colorise_balance(mv),
                ac,
                util.colors.colorise_balance(tr, ("+" if tr >= 0 else "")),
                util.colors.colorise_balance(tr),
                ac,
                util.colors.colorise_balance(tr, tr_sign),
                util.colors.colorise_balance(max((tr / (cb or 1) * 100), -100)),
            )

            title = "  {} => {} {}".format(
                name,
                util.colors.colorise_balance(mv),
                ac,
            )

            if account["currency"] != default_currency:
                mv_in_default = decimal.Decimal()
                tr_in_default = decimal.Decimal()
                pair = (
                    account["currency"],
                    default_currency,
                )
                rev = False
                try:
                    rate = currency_basket["rates"][pair]
                except KeyError:
                    try:
                        pair = (
                            default_currency,
                            account["currency"],
                        )
                        rate = currency_basket["rates"][pair]
                        rev = True
                    except KeyError:
                        fmt = "no currency pair {}/{} for {} account named {}"
                        sys.stderr.write(
                            ("{}: {}: " + fmt + "\n").format(
                                util.colors.colorise(
                                    "white",
                                    account["~"].text[0].location,
                                ),
                                util.colors.colorise(
                                    "red",
                                    "error",
                                ),
                                util.colors.colorise(
                                    "white",
                                    account["currency"],
                                ),
                                util.colors.colorise(
                                    "white",
                                    default_currency,
                                ),
                                t,
                                util.colors.colorise(
                                    "white",
                                    name,
                                ),
                            )
                        )
                        exit(1)

                rate = rate.rate
                if rev:
                    mv_in_default = mv / rate
                    tr_in_default = tr / rate
                else:
                    mv_in_default = mv * rate
                    tr_in_default = tr * rate

                fmt = " ≅ {} {} at {} {}/{}"
                title += fmt.format(
                    util.colors.colorise_balance(
                        (mv_in_default or 0),
                        "{:7.2f}",
                    ),
                    default_currency,
                    util.colors.colorise(
                        util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    account["currency"],
                    default_currency,
                )

            p(title)

        fmt_share_price_mkt = "{:8.4f}"
        fmt_share_price_avg = "{:8.4f}"
        fmt_share_worth = "{:8.2f}"
        fmt_tr_nominal = "{:8.2f}"
        fmt_tr_percent = "{:8.2f}"

        for company, shares in sorted(account["shares"].items()):
            stats = account["shares"][company]

            shares_held = stats["v2_shares_held"]
            if shares_held == 0:
                continue

            market_value = stats["v2_market_value"]
            total_return = stats["v2_total_return"]
            cost_basis = stats["v2_cost_basis"]

            share_price_mkt = stats["price_per_share"]
            share_price_avg = cost_basis / shares_held if shares_held else cost_basis
            share_price_diff = share_price_mkt - share_price_avg

            from ledger.util.colors import colorise_if_possible as c
            from ledger.util.colors import colorise_balance as cb
            from ledger.util.colors import (
                COLOR_SHARE_PRICE,
                COLOR_SHARE_COUNT,
                COLOR_SHARE_PRICE_AVG,
                COLOR_SHARE_WORTH,
                COLOR_BALANCE_NEGATIVE,
            )

            star_spacing = 6 - len(f"{abs(share_price_diff):.2f}")
            star_spacing = " " * star_spacing

            dividends = stats["dividends"]
            dividend_marker = "* " if dividends else ""

            tr_percentage = total_return / cost_basis * 100

            percent_of_portfolio_value = decimal.Decimal()
            if share_price_mkt:
                mv = market_value

                if account["currency"] != default_currency:
                    pair = (
                        account["currency"],
                        default_currency,
                    )
                    rev = False
                    try:
                        rate = currency_basket["rates"][pair]
                    except KeyError:
                        try:
                            pair = (
                                default_currency,
                                account["currency"],
                            )
                            rate = currency_basket["rates"][pair]
                            rev = True
                        except KeyError:
                            fmt = "no currency pair {}/{} for {} account named {}"
                            sys.stderr.write(
                                ("{}: {}: " + fmt + "\n").format(
                                    util.colors.colorise(
                                        "white",
                                        account["~"].text[0].location,
                                    ),
                                    util.colors.colorise(
                                        "red",
                                        "error",
                                    ),
                                    util.colors.colorise(
                                        "white",
                                        account["currency"],
                                    ),
                                    util.colors.colorise(
                                        "white",
                                        default_currency,
                                    ),
                                    t,
                                    util.colors.colorise(
                                        "white",
                                        name,
                                    ),
                                )
                            )
                            exit(1)

                    rate = rate.rate
                    if rev:
                        mv = mv / rate
                    else:
                        mv = mv * rate

                percent_of_portfolio_value = (mv / total_market_value) * 100

            p(
                "    {}: {} ({}{}{}) {}* {} = {} ({}%) {}{} {}%".format(
                    cb(
                        total_return,
                        (dividend_marker + company).rjust(company_name_length),
                    ),
                    colored.bg(ALT_BG)
                    + c(
                        COLOR_SHARE_PRICE_AVG,
                        fmt_share_price_mkt.format(share_price_mkt),
                    ),
                    c(COLOR_SHARE_PRICE, fmt_share_price_avg.format(share_price_avg)),
                    cb(share_price_diff, ("+" if share_price_diff >= 0 else "")),
                    cb(share_price_diff),
                    star_spacing,
                    c(COLOR_SHARE_COUNT, f"{shares_held:4.0f}"),
                    c(COLOR_SHARE_WORTH, fmt_share_worth.format(market_value)),
                    c(COLOR_SHARE_WORTH, f"{percent_of_portfolio_value:5.2f}"),
                    colored.bg(ALT_BG) + c(COLOR_SHARE_PRICE, f"{cost_basis:8.2f}"),
                    cb(total_return, f"{total_return:+8.2f}"),
                    cb(tr_percentage, f"{tr_percentage:+7.2f}"),
                )
            )

    header_footer()
