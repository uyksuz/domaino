import re

VOWELS = frozenset('aeiou')
RARE   = frozenset('qxzj')


def calc_score(domain: str) -> int:
    name = domain.lower().replace('.com', '')
    ln = len(name)
    if ln < 3 or ln > 6:
        return 0

    score = 0

    # Uzunluk (40p)
    score += {3: 40, 4: 26, 5: 12, 6: 4}[ln]

    # Nadir harf yok (20p)
    rare = sum(1 for c in name if c in RARE)
    score += max(0, 20 - rare * 8)

    # Sesli/sessiz dengesi (20p)
    vowels = sum(1 for c in name if c in VOWELS)
    r = vowels / ln
    if 0.33 <= r <= 0.55:
        score += 20
    elif 0.20 <= r <= 0.70:
        score += 10
    else:
        score += 3

    # Consonant cluster (20p)
    cur = mx = 0
    for c in name:
        if c in VOWELS:
            cur = 0
        else:
            cur += 1
            mx = max(mx, cur)
    if mx <= 1:
        score += 20
    elif mx == 2:
        score += 10

    # Marka paterni bonusu (10p)
    pat = ''.join('V' if c in VOWELS else 'C' for c in name)
    if re.match(r'^(CV)+C?$|^(VC)+V?$', pat):
        score += 10
    elif not re.search(r'CCC|VVV', pat):
        score += 5

    return min(100, score)
