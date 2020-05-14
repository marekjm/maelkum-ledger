" Vim syntax file
" Language:	Maelkum's Accounting file
" Maintainer:	Marek Marecki <marekjm@ozro.pw>
" Last Change:	2019 August 06

" quit when a syntax file was already loaded
if exists("b:current_syntax")
  finish
endif

syntax match ledgerComment      "^\s*\zs#.*$"

syntax keyword ledgerPreProc    end begin open match balance set currency_rates
syntax keyword ledgerPreProc    tx ex rx
syntax keyword ledgerKeyword    with
syntax keyword ledgerOperator   account budget
syntax keyword ledgerStatement  asset liability equity

" Define currency shorthands as special syntax.
syntax keyword ledgerSpecial    PLN JPY USD EUR CHF NOK GBP CZK

syntax match ledgerDate         "\<[0-9][0-9][0-9][0-9]-\(1[0-2]\|0[1-9]\)-\(3[01]\|[0-2][0-9]\)\>"
syntax match ledgerDatetime     "\<[0-9][0-9][0-9][0-9]-\(1[0-2]\|0[1-9]\)-\(3[01]\|[0-2][0-9]\)T\([0-1][0-9]\|2[0-3]\):[0-5][0-9]\>"

syntax match ledgerNegativeAmount "-\<[1-9][0-9]*\.[0-9][0-9]\>"
syntax match ledgerNegativeAmount "-\<0\.\([1-9][0-9]\|0[1-9]\)\>"
syntax match ledgerPositiveAmount "\<[1-9][0-9]*\.[0-9][0-9]\>"
syntax match ledgerPositiveAmount "\<0\.\([1-9][0-9]\|0[1-9]\)\>"

" Define the default highlighting.

hi def link ledgerOperator  Operator
hi def link ledgerStatement Statement
hi def link ledgerKeyword   ledgerSpecial
hi def link ledgerSpecial   Special
hi def link ledgerPreProc   PreProc
hi def link ledgerDate      Number
hi def link ledgerDatetime  Number
hi def link ledgerComment   Comment


let b:current_syntax = "ledger"
