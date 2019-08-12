# Maelkum's ledger HOWTO

This is a document explaining how some common tasks may be achieved, organised
in the form of a FAQ list.

--------------------------------------------------------------------------------

# Accounts

Questions related to account management.

## How do I open an asset or liability account?

You use the `open account` command.

You need to know a few things first:

- the kind of the account you want (asset or liability)
- the name of the account
- the currency of the account

Also, you have to decide if you want the account to appear in overview (probably
yes).

Then, in your ledger:

    open account 2019-08-12 asset bank.main_account
        balance: 0.00 PLN
    with
        main
        overview
    end

For liability accounts just change the "`asset`" to "`liability`". There are two
"tags" added to the account.

The `main` tag tells the ledger that this is the main account. You may have ONLY
ONE main account. The `overview` tag tells the ledger to display the accounts
balance in the overview (i.e. the main report).

In the example the initial balance on the account is set to 0.00 PLN. You can
either start the account with some initial balance or set it later.

----------------------------------------

## How do I set a balance on the account?

You use the `balance` command.

    balance 2019-08-12
        asset/bank.main_account 100.00 PLN
    end

If the balance you set is different than what the ledger calculated it means
that there were some unrecorded transactions. You may want to double-check if
you have recorded everything.

The ledger will complain about balance discrepancies for the current month. It
will be silent about older errors.

If the balance you set is lower than the calculated one the ledger will print a
warning with a "positive" value, e.g.:

    100.00 PLN not accounted for on asset/bank.main_account as of 2019-08-12

If the balance you set is higher than the calculated one the ledger will print a
warning with a "negative" value, e.g.:

    -100.00 PLN not accounted for on asset/bank.main_account as of 2019-08-12

--------------------------------------------------------------------------------

# Transactions

## How do I record a revenue?

You use the `rx` command.

    rx 2019-08-01T10:00 Salary
        EMPLOYER
        asset/bank.main_account 100.00 PLN
    end

----------------------------------------

## How do I record an expense?

You use the `ex` command.

    ex 2019-08-01T14:00 Dinner
        asset/bank.main_account -100.00 PLN
        BEST CHINESE PLACE IN TOWN
    end

----------------------------------------

## How do I record a transfer between two accounts I own?

You use the `tx` command.

    tx 2019-08-01T14:00 Dinner
        asset/bank.main_account    -100.00 PLN
        liability/bank.credit_card  100.00 PLN
    end

Transfers are only availale between the accounts you *own* (i.e. assets and
liabilities). To record a transfer of value between an account you own and an
"external" account use either `rx` or `ex` command.

The amount of money transferred must be specified on both accounts, and must be
balanced. Otherwise the ledger will complain.

--------------------------------------------------------------------------------

# Examples

## How do I maintain a record of bills (e.g. rent)?

You create a liability account for your bills. For example:

    open account 2019-08-12 liability bills.rent
        balance: 0.00 PLN
    with
        overview
        only_if_negative
    end

The `only_if_negative` tag tells the ledger to display the account in overview
only if the balance on it is negative. Which is useful as it reduces the clutter
but still displays the liability if you have unpaid bills.

Then, you record expenses from that account:

    ex 2019-09-01 Rent
        liability/bills.rent -100.00 PLN
        Landlord
    end

The ledger will now display the liability as having a negative balance. You then
transfer money from main (or some other) account to it:

    tx 2019-09-02T13:37
        asset/bank.main_account -100.00 PLN
        liability/bills.rent     100.00 PLN
    end

This will zero-out the liability and the ledger will display it no more.

----------------------------------------

## How do I maintain a foreign currency account?

You first create such an account:

    open account 2019-08-01 asset bank.eur
        balance: 0.00 EUR
    with
        overview
    end

Then you record multi-currency transfers using the `tx` command:

    tx 2019-08-01T13:37
        asset/bank.main_account -100.00 PLN
        asset/currency.eur        22.56 EUR
    with
        rate: EUR/PLN 4.4321
    end

The ledger will compare currencies on both accounts and complain if you make a
mistake and try to push PLN to account in EUR. It will also use the rate you
specify to calculate the amount of currency you should get after exchange and
complain if it differs too much from stated values. The maximum allowed
difference (as of 2019-08-12) is 0.5% (half a percent).

In overview the ledger will display the balanceon the account in its stated
currency as well as in the default currency, e.g.:

    currency.eur: 22.56 EUR ~ 100.00 PLN at 4.4321 EUR/PLN buying rate

The overall balance will also display the approximate value of your finances in
the default currency, like this:

    Balance on all 2 accounts: 100.00 PLN (~200.00 PLN, ~100.00 PLN in foreign currencies)

----------------------------------------

## How do I record a transaction "in the future"?

Simple, you just use the future date and the transaction won't affect ledger's
calculations until that date.

I use it to schedule bill payments. Every month after I pay my bills I add a
future transaction to the ledger with source account being the liability
account I created for that specific kind of bill, e.g. rent. Then when the time
comes to pay that bill I record a `tx` transaction from main account to the
liability account.

It may not be a strict mirror of what really happened, but helps managing the
amount of money you need to pay and that you paid already.

----------------------------------------

## How do I maintain a budget and limit my spending?

You use the `set budget` command, like this:

    set budget 50.0 %
    set budget 100.00 $

The first variant sets the allowed *spending limit* to be 50% of your revenues.
The second variand sets the allowed spending limit to be 100.00 units of your
default currency (the dollar sign is used to differntiate from percentage-based
budget).

If you set a budget ledger will display additional line in the "This month"
report's output, and it will look like this:

    Daily expense cap to meet budget: 20.00 PLN

If you spend this amount of money (or less) you will meet your budget.

The amount you are allowed to spend is calculated dynamically and every
transaction affects it, so if you (for example) receive a half of your salary on
the 1st and the second half on the 15th your "daily cap" will fluctuate.
