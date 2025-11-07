#!/usr/bin/env python3

import datetime
import decimal
import os
import sys

try:
    import colored
except ImportError:
    colored = None

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
    stream.write((fmt + "\n").format(*args, **kwargs))


to_stdout = lambda fmt, *args, **kwargs: to_impl(sys.stdout, fmt, *args, **kwargs)
to_stderr = lambda fmt, *args, **kwargs: to_impl(sys.stderr, fmt, *args, **kwargs)


MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def print_short_help():
    exe = sys.argv[0]
    print(f"{exe} <book> [default]")
    print(f"{exe} <book> year <year>")
    print(f"{exe} <book> month <year> <month>")
    print(f"{exe} <book> overyear <year>")


def main(args):
    if colored is not None:
        colored.set_tty_aware(False)

    if not args:
        print_short_help()
        exit(1)

    match args[0]:
        case "--version":
            to_stdout(
                "maelkum-ledger {} ({})".format(
                    ledger.__version__,
                    ledger.__commit__,
                )
            )
            exit(0)
        case "--help":
            print_short_help()
            exit(0)
        case _:
            pass

    BOOK_MAIN = args[0]
    if not os.path.exists(BOOK_MAIN):
        to_stderr(
            "{}: given book path does not exist: {}".format(
                ledger.util.colors.colorise(
                    ledger.util.colors.COLOR_CATASTROPHE,
                    "error",
                ),
                BOOK_MAIN,
            )
        )
        exit(1)
    if not os.path.isfile(BOOK_MAIN):
        to_stderr(
            "{}: given book path is not a file: {}".format(
                ledger.util.colors.colorise(
                    ledger.util.colors.COLOR_CATASTROPHE,
                    "error",
                ),
                BOOK_MAIN,
            )
        )
        exit(1)

    REPORT_TYPE = args[1] if len(args) > 1 else "default"

    book_lines = ledger.loader.load(BOOK_MAIN)
    # to_stdout('\n'.join(map(repr, book_lines)))

    book_ir = ledger.parser.parse(book_lines)
    # to_stdout('{} item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(repr, book_ir)))

    def sorting_key(item):
        if isinstance(item, ledger.ir.Transaction_record):
            return item.effective_date()
        return item.timestamp

    book_ir = sorted(book_ir, key=sorting_key)
    # to_stdout('chronologically sorted item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(lambda x: '{} {}'.format(x.timestamp, repr(x)), book_ir)))

    ####

    default_currency = "EUR"
    accounts = {
        "asset": {},
        "liability": {},
        "equity": {},
    }
    txs = []

    # First, process configuration to see if there is anything the ledger should
    # be aware of - default currency, budger levels, etc.
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            if each.key == "default-currency":
                default_currency = str(each.value)
            elif each.key == "budget":  # FIXME TODO
                pass
            else:
                raise

    # Then, set up accounts to be able to track balances and verify that
    # transactions refer to recognised accounts.
    ledger.book.setup_accounts(accounts, book_ir)

    # Then, process transactions (ie, revenues, expenses, dividends, transfers)
    # to get an accurate picture of balances.
    currency_basket = {
        "rates": {},
        "txs": [],
    }

    book = (
        book_ir,
        currency_basket,
    )

    ledger.book.calculate_balances(accounts, book, default_currency)
    ledger.book.calculate_equity_values(accounts, book, default_currency)

    if REPORT_TYPE == "default":
        # Default report.
        # A high-level overview of income and expenses during several
        # immediately important periods of time:
        #
        #  - last two days
        #  - last two months
        #  - last two years
        #  - all time
        #
        # It also includes overview of accounts.
        #
        # Useful for quick assesment of how the financial situation is
        # developing.
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
        ledger.reporter.report_last_year((screen, 1), book, default_currency)
        to_stdout(screen.str())
        screen.reset()

        ledger.reporter.report_all_time((screen, 1), book, default_currency)
        ledger.reporter.report_total_reserves(
            (screen, 0), accounts, book, default_currency
        )
        ledger.reporter.report_total_balances(
            (screen, 0), accounts, book, default_currency
        )
        screen.print(0, "")
        ledger.reporter.report_total_equity(
            (screen, 0), accounts, book, default_currency
        )
        to_stdout(screen.str())
        screen.reset()

    if REPORT_TYPE == "overyear":
        # Yearly report.
        # A high-level overview of income and expenses; with per-month and
        # whole-year breakdowns.
        Screen = ledger.util.screen.Screen
        screen = Screen(Screen.get_tty_width(), 3)

        NOW = datetime.datetime.now()
        if len(args) > 2:
            year = args[2]
            NOW = datetime.datetime.strptime(
                f"{year}-12-31T23:59", ledger.constants.TIMESTAMP_FORMAT
            )

        no_of_streams = Screen.get_tty_height() - 1
        months_in_column = round(NOW.month / 2)
        no_of_streams = no_of_streams - (months_in_column * 10)
        no_of_streams = int(no_of_streams / months_in_column / 2)
        # no_of_streams = 1000

        i = 0
        while i < len(MONTHS):
            ledger.reporter.report_month(
                (screen, i % 2),
                MONTHS[i],
                (
                    NOW.year,
                    i + 1,
                ),
                book,
                default_currency,
                sinks=no_of_streams,
                faucets=no_of_streams,
            )
            i += 1
            if i >= NOW.month:
                break

            ledger.reporter.report_month(
                (screen, i % 2),
                MONTHS[i],
                (
                    NOW.year,
                    i + 1,
                ),
                book,
                default_currency,
                sinks=no_of_streams,
                faucets=no_of_streams,
            )
            i += 1
            if i >= NOW.month:
                break

            screen.fill(up_to_column=1)

        no_of_streams = (Screen.get_tty_height() - 10) // 2
        ledger.reporter.report_year(
            (screen, 2),
            "Year",
            NOW.year,
            book,
            default_currency,
            sinks=no_of_streams,
            faucets=no_of_streams,
        )

        to_stdout(screen.str().strip())
        screen.reset()

    if REPORT_TYPE == "month":
        # Detailed report for a single month.
        Screen = ledger.util.screen.Screen
        screen = Screen(Screen.get_tty_width(), 2)

        if len(args) <= 3:
            exit(1)

        year = int(args[2])
        month = int(args[3])
        BEGIN = datetime.datetime.strptime(
            f"{year}-{month:02d}-01T00:00", ledger.constants.TIMESTAMP_FORMAT
        )

        end_month = month + 1 if month != 12 else month
        end_year = year if month != 12 else year + 1
        END = datetime.datetime.strptime(
            f"{year}-{month:02d}-01T00:00", ledger.constants.TIMESTAMP_FORMAT
        ) - datetime.timedelta(milliseconds=1)

        no_of_streams = Screen.get_tty_height() - 10

        ledger.reporter.report_month(
            (screen, 0),
            MONTHS[month - 1],
            (
                BEGIN.year,
                BEGIN.month,
            ),
            book,
            default_currency,
            sinks=no_of_streams,
            faucets=0,
        )

        ledger.reporter.report_month(
            (screen, 1),
            MONTHS[month - 1],
            (
                BEGIN.year,
                BEGIN.month,
            ),
            book,
            default_currency,
            sinks=0,
            faucets=no_of_streams,
        )

        to_stdout(screen.str().strip())
        screen.reset()

    if REPORT_TYPE == "year":
        # Detailed report for a single year.
        Screen = ledger.util.screen.Screen
        screen = Screen(Screen.get_tty_width(), 2)

        if len(args) <= 2:
            exit(1)

        year = int(args[2])

        no_of_streams = Screen.get_tty_height() - 10

        ledger.reporter.report_year(
            (screen, 0),
            f"Year {year}",
            year,
            book,
            default_currency,
            sinks=no_of_streams,
            faucets=0,
            aggregate=False,
        )

        ledger.reporter.report_year(
            (screen, 1),
            f"Year {year}",
            year,
            book,
            default_currency,
            sinks=0,
            faucets=no_of_streams,
            aggregate=False,
        )

        to_stdout(screen.str().strip())
        screen.reset()

    if REPORT_TYPE == "span":
        # Detailed report for a single year.
        Screen = ledger.util.screen.Screen
        screen = Screen(Screen.get_tty_width(), 2)

        if len(args) <= 2:
            print("maelkum-ledger span <begin> [<end>]")
            print("Both <begin> and <end> must be valid datestamps eg, 2024-06-13.")
            exit(1)

        begin = args[2]
        end = args[3] if len(args) > 3 else datetime.datetime.now().strftime(ledger.constants.DAYSTAMP_FORMAT)

        BEGIN = datetime.datetime.strptime(
            begin, ledger.constants.DAYSTAMP_FORMAT
        )
        END = datetime.datetime.strptime(
            end, ledger.constants.DAYSTAMP_FORMAT
        )

        no_of_streams = Screen.get_tty_height() - 10

        ledger.reporter.report_period_impl(
            (screen, 0),
            (BEGIN, END,),
            f"Span",
            book,
            default_currency,
            sinks=no_of_streams,
            faucets=0,
            aggregate=False,
        )

        ledger.reporter.report_period_impl(
            (screen, 1),
            (BEGIN, END,),
            f"Span",
            book,
            default_currency,
            sinks=0,
            faucets=no_of_streams,
            aggregate=False,
        )

        to_stdout(screen.str().strip())
        screen.reset()


main(sys.argv[1:])
