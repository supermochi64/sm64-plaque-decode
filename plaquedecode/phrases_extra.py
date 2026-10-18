"""Second curated set: first words with the plaque's measured outline (We, By, Be, Me, My,
He ...) x many middle words x short endings, in sentence- and Title-case, plus free phrases including quirky
Japanese-English ("Engrish") phrasings that a 1996 Japanese team might plausibly have written."""
import itertools

A = "We By Be Me My He Wee We'll We're We've Bye Way".split()
B = """hope hopes hoped hoping with happy here home keep kept sleep help pray play hug hugs have love loves live lives lie rest
wish wishes shine shines star stars glory joy peace ever eyes safe hero our your my the a in at on up ok okay deep step gaze
gone fine nice good kind well free brave strong true bright light dream dreams always forever hold stay pure sure fly go
going get got give gave you yours us all one big best near far wise warm calm""".split()
C = """so so. so! us you me we he it too on up ok all now ever here there again ~ ! you. us. you! us! more one go do be by to
for is in an or no as at my of""".split()
FREE = """Be with us|Be with you|Be with me|Be With Us|Be With You|Be with us~|Be with us!|Be with us.|Be with us all|Be with us ever|
Be with us so|Be here|Be here so|Be here now|By your side|By my side|By our side|By us|Be us|We be|We be ok|We be here|
Be happy|Be happy so|Be happy ~|Be in hope|Be at peace|Be our hope|Be my star|Be my hope|Be the star|Be a star|Be star|
Be eternal|Be ever|Be hope|Be hope so|By hope|By hope us|By hope so|We hope us|We hope you|We hope it so|We are hope|
We hope ever|We hope be ok|We hope ok|We hope go|We hope we|We hope do|We hope by|We wish so|Wish so|Hope so|Be peace|
Be peaceful|Be in peace|Be at ease|We love you|We love us|We pray so|We pray you|We keep hope|We keep on|Keep on hope|
We hope so|We hope so!|We hope so~|We hope he|We hope to|We hope for|We hope on|My hope is|My hope so|Me hope so|
We hope your|We hope yours|We hope all|We hope too|We hope more|We hope one|We hope so too|We hope you ok|Be ok|Be okay|
Be good|Be nice|Be kind|Be well|Be safe|Be free|Be brave|Be strong|Be true|Be bright|Be light|Be always|Be forever|
By the star|By star|By stars|By light|By hope we|Be the hope|Be a hope|We hope it|We hopes|We hopes so|We hopes you""".replace("\n", "").split("|")


def extra():
    t = lambda w: w[:1].upper() + w[1:] if w[:1].isalpha() else w
    out = set()
    for a, b, c in itertools.product(A, B, C):
        out.add("%s %s %s" % (a, b, c)); out.add("%s %s %s" % (a, t(b), t(c)))
    for a, b in itertools.product(A, B):
        out.add("%s %s" % (a, b)); out.add("%s %s" % (a, t(b)))
    out |= {p.strip() for p in FREE if p.strip()}
    return sorted(out)
