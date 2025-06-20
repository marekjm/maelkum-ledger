# Maelkum's ledger

A simple tool to keep track of expenses and revnues.
Based on accounts and transactions.

--------------------------------------------------------------------------------

## How to...

A selection of examples of the events you can record in a ledger.

### Open an account?

```
open account 2019-08-01 asset bank.main_account
    balance: 0.00 PLN
with
    main
    overview
end
open account 2019-08-01 asset bank.savings_account
    balance: 100.00 PLN
with
    overview
end
```

### Force a balance on an account?

You may set balance on as many accounts as you want using a single `balance`
record.

```
balance 2019-08-01
    asset/bank.main_account 1000.00 PLN
end
```

### Record revenues?

A revenue transaction means "I got some money":

```
rx 2019-08-01T09:42 Salary
    EMPLOYER
    asset/bank.main_account 1000.00 PLN
end
```

### Record expenses?

An expense transaction means "I spent some money":

```
ex 2019-08-01T12:48
    asset/bank.main_account -15.00 PLN
    BEST ASIAN FOOD PLACE IN TOWN
end
```

### Record transfers between accounts?

A transfer moves money between your own accounts, and does not change the amount
of money you have.

```
tx 2019-08-01T13:37
    asset/bank.main_account    -100.00 PLN
    asset/bank.savings_account  100.00 PLN
end
```

### Record revenues in the future?

```
rx 2022-06-14T12:00 Summer bonus
    asset/bank.main_account 1.00 PLN
    EMPLOYER
with
    effective_date: 2022-07-01T00:00
end
```

### Record currency exchanges?

```
tx 2022-06-29T12:00
    asset/bank.eur -1.00 EUR
    asset/bank.pln  4.69 PLN
end
```

### Record buying stocks?

You need to have an equity account opened.
Every such transactin requires the `shares` tag within the `with` part of a
record.

```
tx 2022-06-29T12:00
    asset/broker.usd       -3.00 USD
    equity/broker.EXCHANGE  2.00 USD
with
    shares: COMPANY 1
    fee: -1.00 USD
    intermediary: BROKER INC.
end
```

### Record dividends?

```
dividend 2022-06-29T12:01
    asset/broker.usd 1.00 USD
    equity/broker.EXCHANGE COMPANY
end
```

### Record share prices?

You may set prices of as many companies as you want using a single `balance`
record.

```
balance 2022-06-29T12:02
    equity/broker.EXCHANGE COMPANY 1.00 USD
end
```

--------------------------------------------------------------------------------

## Running the report

The examples below assume you keep your books in a file called `book.txt`.

To get the default report execute the following command:

```
]$ maelkum-ledger book.txt
```

You can also get a report for a particular year or month of the year:

```
]$ maelkum-ledger book.txt year 2025
]$ maelkum-ledger book.txt month 2025 6
```

A "yearly overview" report with per-month summaries is also available:

```
]$ maelkum-ledger book.txt overyear 2025
```

--------------------------------------------------------------------------------

# Copyright and license

Copyright (C) 2019-2025 Marek Marecki

This is Free Software published under GNU GPL v3 license. See LICENSE for full
text of the license and educate yourself about your rights.
