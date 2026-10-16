"""Exact paired comparison for *unsafe* approval on manually labeled cases.

To prevent spurious claims, it reports exact McNemar p values only over
cases where the ground truth is unsafe. Like all comparisons it is descriptive
without independent evaluation data and protocol control.
"""
from __future__ import annotations
import math

def exact_mcnemar(a, b):
    """Two equally sized Boolean arrays. Returns discordances and exact p."""
    if len(a) != len(b) or not a:
        raise ValueError('paired and nonempty inputs required')
    n10=sum(bool(x) and not bool(y) for x,y in zip(a,b))
    n01=sum(not bool(x) and bool(y) for x,y in zip(a,b))
    n=n01+n10
    if n==0:p=1.
    else:
        k=min(n01,n10)
        # math.comb has exact integer arithmetic even for hundreds of cases
        p=min(1.,2*sum(math.comb(n,i) for i in range(k+1))/(2**n))
    return {'n':len(a),'a_unsafe_b_safe':n10,'a_safe_b_unsafe':n01,
            'discordances':n,'mcnemar_exact_two_sided_p':round(p,8),
            'note':'Paired binary comparison; unsafe cases only. p-value not evidence of real model performance by itself.'}
