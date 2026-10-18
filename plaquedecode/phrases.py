"""Curated meaningful candidate phrases for line 2: template product A x B x C (first word / middle word / short
ending; sentence- and Title-case) + free natural phrases, including the readings proposed by others."""
import itertools


def curated():
    A = """We I You My Our No So To The Tis 'Tis Thy Its It Is In Of On Oh O All May Let For As By Be Do Go He She They His Her
    Thou Ye Now Not And But Or If Yes Two One Mr Mrs St Dr Lo Ah Hi This That Thee Then Thus Too Who Why How What Was Are Has""".split()
    B = """hope hopes hoped hoping huge keep keeps kept sleep sleeps weep deep help helps hug hugs pray prays play plays day days
    age ages way ways eye eyes joy joys jump peace light lights night nights might right bright magic sky rays gaze gate
    shape gods god long song songs wing wings king kings reign sign legend glory glow glows gleam grows grow grew give gives
    gave got get gets go goes going guy guys gay gem gems page pages type yes yet you your young yours yearn pure upon open
    opens happy hero heroes love loves lives live shine shines rest rise rises star stars stay stays stand sing sings ring
    rings bring brings dream dreams wish wishes wait waits watch fly flies grace gift gifts hug ego egg eggs pig big dig
    fog jog log dog dogs gap gaps cap cup cups map maps top tops pop hop hip pip pipe pipes ripe rope ropes soap soup
    step steps stop stops ship ships shop sharp sleepy spy pyre type gypsy tiny envy enjoy enjoys lay lays say says
    pays obey obeys pay apple grape grapes plum pyramid empty empire prize spring springs sprite spirit spirits""".split()
    C = """so so. so! on is in of us to be me we it as at an oh er ye up go do my no or by he am all you too now
    yet one two too ok for ever more sir now. on. us. too! ~ ! . ... ? me! us! of. ok!""".split()
    title = lambda w: w[:1].upper() + w[1:] if w[:1].isalpha() else w
    out = set()
    for a, b, c in itertools.product(A, B, C):
        out.add("%s %s %s" % (a, b, c))
        out.add("%s %s %s" % (a, title(b), title(c)))                 # Title Case like "Eternal Star"
    for a, b in itertools.product(A, B):
        out.add("%s %s" % (a, b)); out.add("%s %s" % (a, title(b)))
    FREE = """We hope so|We Hope So|'Tis hope so|No hope so|Rest in peace|Rest In Peace|Here lies|Here it lies|May it shine|Shine on|
    Shine forever|Forever more|Evermore|Always shining|We love you|Wish upon it|Make a wish|Wish on a star|Shine bright|Hope for all|
    Our hope|The hope of all|Hope lives on|Hope is eternal|Thank you|Thank You|Thanks Mario|Peace on earth|Love and peace|To you|For you|
    For all|For Mario|For Peach|To Mario|To Peach|To Yoshi|By Nintendo|Nintendo 1996|EAD 1996|Since 1996|Est. 1996|In memory|
    In Memory|In memory of|Long live it|Long live us|Long may it shine|Keep the hope|Keep hope alive|Keep on dreaming|Dream on|Dream big|
    Sweet dreams|Good night|Good luck|Bless you|God bless|Pray for us|Play on|Play it again|Let it shine|Let it be|So be it|
    Amen|It is so|Ever so|Ever on|Yours truly|Your star|My star|Our star|Our Star|The star|Light of hope|Light the way|Lights the way|
    Guide us|Guiding light|Lead the way|Show the way|Hope springs|Hope springs eternal|Joy to all|Joy to you|Joy for all|
    Happy days|Happy end|The End|The end|Fin|The Legend|A Legend|Legend of hope|Glory to all|Glory be|All is well|
    Tis my hope|Tis the hope|Tis hope|Thy hope|Thy hope is|Thy light|Thy glory|To hope is|To hope on|We pray so|We play on|
    We keep it|We keep on|We sleep on|We weep so|No hope|No hope in|My hope is|Our hope is|Is hope so|Is hope on|Oh hope so|
    I hope so|I Hope So|You hope so|We hope to|We hope on|We hope it|We hope we|Two hope so|Two hopes|The hope so|The hope is|
    L is real|L is real 2401|2401|Luigi is real|Luigi lives|Mario 64|Super Mario|Wario|Waluigi""".replace("\n", "").split("|")
    out |= {p.strip() for p in FREE if p.strip()}
    return sorted(out)
