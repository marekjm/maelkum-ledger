def mean(seq):
    return sum(seq) / len(seq)

def mean_weighted(seq):
    s = sum(map(lambda e: (e[0] * e[1]), seq))
    w = sum(map(lambda e: e[0], seq))
    return (s / w)

def median(seq):
    seq = sorted(seq)
    n = len(seq) // 2
    if len(seq) % 2 == 0:
        return mean(( seq[n - 1], seq[n], ))
    else:
        return seq[n]

def diff_less_than(a, b, percent_diff):
    a_more = a * (1 + percent_diff)
    a_less = a * (1 - percent_diff)
    return (b < a_more) and (b > a_less)
