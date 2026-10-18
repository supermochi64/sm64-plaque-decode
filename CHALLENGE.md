# The plaque challenge: prove me wrong

I claim that the courtyard plaque in Super Mario 64 says **"Eternal Star / We hope so"**. Below are two ways to show I'm
wrong. Both use the same open code and the same scoring that produced my answer. Every attempt goes on the leaderboard,
won or lost.

Contact: [whitemochi64@proton.me](mailto:whitemochi64@proton.me) · [@supermochi64](https://x.com/supermochi64) on X ·
or open an issue in this repository.

## Challenge 1: beat "Eternal Star"

Find a reading that fits the real plaque better than mine.

**How scoring works.** Your text is typed in a font, shrunk to 32 × 32 pixels on the plaque's stone background, and
compared with the real plaque, pixel by pixel. The program tries hundreds of letter sizes, canvases, shrinking filters,
blur and contrast settings for your line 1, and every size and position for your line 2, then keeps your best result.
That is exactly how every reading on the board was scored, mine included. Lower is better.

**Rules**

1. **Real English.** Every word must be in the common-word list [`data/vocab_en_core.txt`](data/vocab_en_core.txt)
   (17,707 words), and the line must read as English. No abbreviations, initials, names or misspellings: at 3 to 5
   pixels per letter, gibberish like "Lternal" always gets close, and that proves nothing.
2. **A font from before 1996.** Adobe Palatino Bold Italic (1990) is the default. Use any other font that existed
   when the game was made and tell me where it came from.
3. **Unchanged code.** Score your entry with the command below. I rerun every entry myself before it goes on the board.
4. **To win**, beat **1,128.7** for the whole plaque (two lines), or **788.7** for line 1 alone.

```
python -m plaquedecode.challenge score "Your line 1" "Your line 2"
python -m plaquedecode.challenge score "Your line 1"                       # line 1 only
python -m plaquedecode.challenge score "Your line 1" "Your line 2" --font OtherFont.ttf
```

Setup (once): see the main [README](README.md#reproduce-it). You need your own copy of the game to extract the texture.

**My weakest spot, so you know where to dig:** the last word of line 2. "We hope as" (1,148.5) and "We hope he"
(1,155.8) are close behind "We hope so". Line 1 is not close: the best real word after "Eternal" is far behind.

### Leaderboard: whole plaque

| # | Reading | Source | Line 1 | Line 2 | Whole plaque |
|---|---|---|---|---|---|
| 1 | "Eternal Star / We hope so" | mochi64 | 788.7 | 340.1 | **1,128.7** |
| 2 | "Eternal Star / We hope as" | close rival (mochi64 check) | 788.7 | 359.8 | 1,148.5 |
| 3 | "Eternal Star / We hope he" | close rival (mochi64 check) | 788.7 | 367.1 | 1,155.8 |
| 4 | "Eternal Star / We hope us" | close rival (mochi64 check) | 788.7 | 368.4 | 1,157.0 |
| 5 | "Eternal Star / We hops so" | close rival (mochi64 check) | 788.7 | 372.9 | 1,161.5 |
| 6 | "Eternal Star / We hope or" | close rival (mochi64 check) | 788.7 | 378.0 | 1,166.7 |
| 7 | "Eternal Star / We hope we" | close rival (mochi64 check) | 788.7 | 394.8 | 1,183.4 |
| 8 | "Eternal Star / We hope be" | close rival (mochi64 check) | 788.7 | 400.8 | 1,189.5 |
| 9 | "Eternal Star / Me hope so" | close rival (mochi64 check) | 788.7 | 409.5 | 1,198.2 |
| 10 | "Eternal Star / We hope on" | close rival (mochi64 check) | 788.7 | 410.5 | 1,199.2 |
| 11 | "Eternal Star / We hope to" | close rival (mochi64 check) | 788.7 | 421.8 | 1,210.4 |
| 12 | "Eternal Star / He hope so" | close rival (mochi64 check) | 788.7 | 425.5 | 1,214.2 |
| 13 | "Eternal Star / We hope is" | close rival (mochi64 check) | 788.7 | 433.4 | 1,222.0 |
| 14 | "Eternal Star / We hope in" | close rival (mochi64 check) | 788.7 | 438.3 | 1,227.0 |
| 15 | "Eternal star / We hope so" | mochi64 (small s) | 881.7 | 354.9 | 1,236.6 |
| 16 | "Eternal Star / We hope it" | close rival (mochi64 check) | 788.7 | 536.9 | 1,325.5 |
| 17 | "Eternal Star / My hope is" | proposed reading | 788.7 | 538.0 | 1,326.7 |
| 18 | "Eternal Star / my hope is" | proposed reading | 788.7 | 553.7 | 1,342.3 |
| 19 | "Eternal Star / We pray so" | close rival (mochi64 check) | 788.7 | 646.6 | 1,435.3 |
| 20 | "Eternal Star / We hope ~" | close rival (mochi64 check) | 788.7 | 793.6 | 1,582.3 |
| 21 | "Eternal Star / We hope." | close rival (mochi64 check) | 788.7 | 1,019.9 | 1,808.5 |
| 22 | "Eternal Star / lie here ~" | Nintendo Life line 2 with Eternal Star | 788.7 | 1,044.0 | 1,832.7 |
| 23 | "Eternal Star / We hope!" | close rival (mochi64 check) | 788.7 | 1,081.2 | 1,869.8 |
| 24 | "Eternal Star / I hope so" | close rival (mochi64 check) | 788.7 | 1,444.2 | 2,232.9 |
| 25 | "A Secret star / lie here ~" | Nintendo Life 2019 (TV photos) | 2,087.8 | 2,216.6 | 4,304.4 |

### Leaderboard: line 1

| # | Line 1 | Source | Score |
|---|---|---|---|
| 1 | "Eternal Star" | Super Mario Wiki / mochi64 | 788.7 |
| 2 | "Eternal star" | mochi64 (small s) | 881.7 |
| 3 | "L is real star" | reader comment, Nintendo Life 2019 | 1,797.1 |
| 4 | "L is real 2401" | the 1990s Luigi rumour | 2,031.3 |
| 5 | "L is real 2041" | variant spelling (MobyGames) | 2,049.4 |
| 6 | "A Secret star" | Nintendo Life 2019 (TV photos) | 2,087.8 |
| 7 | "スターのいずみ" | Japanese test (best of two Japanese fonts) | 3,493.7 |
| 8 | "スーパーマリオ64" | Japanese test (best of two Japanese fonts) | 3,525.8 |
| 9 | "エターナルスター" | Japanese test (best of two Japanese fonts) | 3,565.7 |
| 10 | "えいえんのほし" | Japanese test (best of two Japanese fonts) | 3,821.7 |
| 11 | "ひみつのスター" | Japanese test (best of two Japanese fonts) | 4,027.8 |
| 12 | "星の銅像" | Japanese test (best of two Japanese fonts) | 5,074.0 |
| 13 | "永遠の星" | Japanese test (best of two Japanese fonts) | 5,428.3 |
| 14 | "ピーチ城" | Japanese test (best of two Japanese fonts) | 5,588.6 |

## Challenge 2: fool the decoder

Hide a secret word in the plaque and see whether my method finds it. This is the blind test that already found 50 of 50
words ([`results/blind_firstword.json`](results/blind_firstword.json)), played live with your word.

1. **Pick one English word**, 4 to 10 letters, from the common-word list. The tool checks that it fits the plaque.
2. **Make your plaque.** The tool writes "<your word> Star" into the real plaque, the same way the blind test did, and
   prints a hash (a fingerprint of your word and a secret salt):
   ```
   python -m plaquedecode.challenge make --word YourWord --out my_plaque.png
   ```
3. **Publish the image and the hash** as a reply on X or as an issue here. Keep the word and the salt to yourself.
4. **I decode it in public within 24 hours** and post my answer.
5. **You reveal the word and the salt.** Anyone can check that the image really came from that word:
   ```
   python -m plaquedecode.challenge verify --png my_plaque.png --word YourWord --salt YourSalt
   ```
   The tool is deterministic: the same word always produces the same image, byte for byte. A hand-edited image fails
   this check.

**You win the round** if my answer is not your word. Every round, won or lost, gets listed here.

### Rounds played

| # | Date | Player | Hidden word | My answer | Result |
|---|---|---|---|---|---|
| | | | | | *no rounds yet* |
