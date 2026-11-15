# Chess coaching — rating sheet

You are scoring **60 pieces of coaching**, each written about one chess game that a chess engine has already analysed.

You do **not** need to be a strong chess player. Each item gives you the engine's own findings — treat those as ground truth — and your job is to judge the coaching written from them.

## How to score

Give each item four scores from **1 to 5**:

- **factual correctness** — Does the coaching match the engine facts and avoid inventing moves, evaluations, or tactics? 1 = fabricates or contradicts the facts; 5 = fully consistent with them.
- **clarity** — Is it clear, well-organized, and understandable to an improving player? 1 = confusing or rambling; 5 = crisp and easy to follow.
- **actionability** — Does it give concrete, useful things to work on? 1 = vague or no advice; 5 = specific and directly actionable.
- **identifies key mistake** — Does it correctly identify and lead with the single most important mistake (or correctly recognize there was no single big error)? 1 = misses or misranks it; 5 = nails the key moment.

Put your scores in `ratings.csv` next to this file. One row per item; the item ids are already filled in.

Notes:

- The items are in random order and several different systems wrote them. Don't try to work out which — just score what's in front of you.
- If you're torn between two scores, take the lower one.
- Score each item on its own. Don't revise earlier ones to be consistent.

---

## item-01

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (PseudoBenko), result 1/2-1/2.
Opening: C50 Italian Game: Paris Defense.
You are coaching the WHITE player (DrNykterstein); the opponent is PseudoBenko.

Objective engine summary:
- Your average centipawn loss: 8.7 (opponent: 8.5; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

Your game was a model of precision—no errors, no blunders, and a near-perfect average centipawn loss. That’s a rare achievement! The key takeaway here is that you’re playing at a level where even small improvements in positioning or timing could push your results further. Since there’s no single "mistake" to correct, focus on two things:  
1. **Deepen your opening preparation**—the Italian Game is a classic, but subtle nuances in pawn structures or piece activity can unlock long-term advantages.  
2. **Strengthen your endgame intuition**—a 8.7 centipawn loss suggests your middlegame is rock-solid, but refining your transition to the endgame could elevate your results.  

Keep up the excellent work! 🎉

---

## item-02

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: B01 Scandinavian Defense.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 103.3 (opponent: 26.7; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 6.Qe4?? (blunder): the engine preferred Qh5+; cost about 41% win probability (cp loss 478).
- 10.Qa3?! (inaccuracy): the engine preferred Qh4; cost about 13% win probability (cp loss 368).
```

**The coaching:**

Let's talk about the key moment in your game. The single biggest turning point was **6.Qe4**. This was a blunder that cost you about 41% of your winning chances. The engine preferred **Qh5+** instead. The idea there is that the check forces your opponent to respond to you, keeping the initiative and making it much harder for them to develop comfortably. By playing Qe4, you gave up that pressure and allowed your opponent to seize control of the position.

The other notable moment was **10.Qa3**, where the engine preferred **Qh4**. This was less severe, but it still cost you about 13% of your win probability. It suggests your queen was drifting away from the action rather than staying active and creating threats.

The pattern here is clear: your queen was moving to squares that looked safe or natural, but weren't actually doing much. In the opening, the queen is a powerful piece, but it needs to be placed with purpose — either creating threats, supporting your development, or coordinating with your other pieces. Both of these moves left your queen passive or exposed.

For your next games, focus on this: before moving your queen, ask yourself what concrete threat it creates or what important square it controls. If the answer is "nothing much," look for a more active square. Also, when you have a check available, seriously consider it — checks force your opponent to react and often give you a free tempo to improve your position.

---

## item-03

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 0-1.
Opening: D06 Queen's Gambit Declined: Marshall Defense.
You are coaching the WHITE player (maia5); the opponent is mikesmcc.

Objective engine summary:
- Your average centipawn loss: 34.6 (opponent: 12.4; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 16.Ne2?! (inaccuracy): the engine preferred Na4; cost about 11% win probability (cp loss 130).
```

**The coaching:**

Let's talk about the one moment that really mattered in this game: **16.Ne2**.

It wasn't a blunder — you didn't hang a piece or walk into a tactic — but it was the kind of quiet inaccuracy that slowly lets a game slip. The engine preferred **Na4**, and the difference was meaningful: about 11% of your winning chances. In plain terms, Ne2 put the knight on a passive square where it wasn't fighting for anything important. Na4 would have kept pressure on Black's queenside and given the knight a more active role. When a game is otherwise balanced, these small placement decisions decide who gets to dictate the play.

The good news is that this was your only real blemish. No blunders, no outright mistakes — just one inaccuracy. Your opponent played more accurately overall (12.4 average centipawn loss versus your 34.6), but the game was decided by accumulation, not by a single collapse. That's actually a sign your fundamentals are solid; the next step is sharpening your positional judgment in the middlegame.

**What to work on:**

1. **Knight placement in closed or semi-closed positions.** Before you move a knight, ask: "Which square gives it the most influence?" In this game, the queenside was where the action was, and Na4 would have aimed there. Ne2 retreated from the fight.

2. **When the position is quiet, look for the most active move, not just a safe one.** You didn't make a bad move — you made a slightly passive one. At your level, that's the difference between holding a draw and creating winning chances.

Keep playing with this kind of discipline, and focus on making every piece earn its square. You're close.

---

## item-04

**What the engine found:**

```
Game: White (vyachesiav-9) vs Black (maia5), result 0-1.
Opening: B01 Scandinavian Defense: Valencian Variation.
You are coaching the WHITE player (vyachesiav-9); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 50.8 (opponent: 29.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 10.Qd2?! (inaccuracy): the engine preferred Qe2; cost about 18% win probability (cp loss 204).
- 12.Nxe4?! (inaccuracy): the engine preferred Qe1; cost about 11% win probability (cp loss 135).
- 7.h3?! (inaccuracy): the engine preferred Bb5; cost about 10% win probability (cp loss 110).
```

**The coaching:**

Let's start with the move that hurt you most: **10.Qd2**. This was your biggest inaccuracy of the game, and it cost you roughly a fifth of your winning chances. The engine preferred **Qe2** instead. The idea behind Qe2 is to keep your queen flexible and ready to support central play — it stays on an open file where it can pressure key squares like d5 or e4 without committing to a specific plan. By retreating to d2, you gave up that flexibility and let Black consolidate comfortably.

The second notable slip was **12.Nxe4**, where the engine preferred **Qe1**. Capturing on e4 looks tempting because it wins material, but it often comes at too high a price — you're trading your active knight for a pawn while Black's pieces become more coordinated. Qe1 keeps your queen in the game and maintains pressure without giving up anything concrete.

Earlier, **7.h3** was also a bit slow. The engine preferred **Bb5**, which develops a piece to an active square and challenges Black's setup immediately. h3 is a defensive move that doesn't address the main tension in the position — it just prepares to play d4 later, but you'd have been better off developing with purpose first.

The good news: this was a clean game overall. No blunders or outright mistakes from either side, and your average centipawn loss of 50.8 is respectable for a player who's still learning. The issue wasn't one catastrophic error — it was several small inaccuracies that added up.

**Two things to work on:**

1. **Keep your queen flexible in the opening.** Before committing her to a specific square, ask yourself whether she can stay active and support central play from another position. Qe2 is often better than Qd2 when you're trying to build an attack or hold a center.

2. **Be careful about pawn-grabbing captures that look good but cost development.** Before taking material with a piece, check whether your opponent's pieces will become more active and whether you're giving up something important in return. A pawn is rarely worth trading away your best-placed piece for it alone.

---

## item-05

**What the engine found:**

```
Game: White (maia1) vs Black (ZValeryi), result 0-1.
Opening: C41 Philidor Defense.
You are coaching the WHITE player (maia1); the opponent is ZValeryi.

Objective engine summary:
- Your average centipawn loss: 107.2 (opponent: 32.9; lower is better).
- Across the whole game: 2 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Kxh2?? (blunder): the engine preferred Qh5; cost about 39% win probability (cp loss 451).
- 14.Kf3?? (blunder): the engine preferred Bg5; cost about 31% win probability (cp loss 9778).
```

**The coaching:**

Your game had two critical blunders that cost you significant winning chances. The most damaging was **12.Kxh2??**, where you captured a pawn instead of playing **Qh5** (the engine’s recommendation). This move allowed Black to gain a decisive advantage by threatening checkmate or a strong attack. Capturing the pawn weakened your position and gave Black control of the center.  

The second blunder, **14.Kf3??**, was equally costly. Instead of playing **Bg5** (which would have pinned your knight or created threats), you moved your king to f3, which is a weak square. This move likely allowed Black to exploit your king’s vulnerability or launch a counterattack.  

These mistakes fit a recurring pattern in your play: **hanging pieces** (a "recurring" issue in your history). You’re often sacrificing material or leaving pieces undefended, which gives your opponent easy targets.  

**Actionable steps:**  
1. **Pause and analyze** before moving, especially when under pressure. Ask: *“Is this move safe? Are my pieces protected?”*  
2. **Focus on tactical awareness**—practice identifying pins, forks, and threats in your openings.  
3. **Avoid unnecessary risks** with your king. Keep it safe and central unless you have a clear plan.  

You’re making progress in other areas, but these tactical errors are holding you back. Work on these habits, and your results will improve.

---

## item-06

**What the engine found:**

```
Game: White (maia9) vs Black (Zelessi), result 1-0.
Opening: C40 King's Pawn Game: Damiano Defense.
You are coaching the BLACK player (Zelessi); the opponent is maia9.

Objective engine summary:
- Your average centipawn loss: 81.7 (opponent: 3.8; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 2...f6?! (inaccuracy): the engine preferred Nc6; cost about 11% win probability (cp loss 127).
```

**The coaching:**

That was a tough game, and the numbers tell a clear story: your opponent played almost flawlessly, while you were fighting an uphill battle from very early on. The good news is that there was no single catastrophic blunder — the game slipped away through small, cumulative disadvantages rather than one big mistake.

The most important moment came as early as move two: **2...f6**. This is the Damiano Defense, and it's a move that looks logical — defending the e5 pawn — but it actually creates more problems than it solves. It weakens the king's position, takes away the f6 square from your knight, and doesn't help your development. The engine preferred **Nc6**, which defends the pawn while developing a piece toward the center. That early choice cost you about 11% of your winning chances, and from there you were playing catch-up against an opponent who gave you almost nothing.

The broader pattern here is that your average centipawn loss was much higher than your opponent's, which means you were consistently making slightly suboptimal choices while they were finding precise moves. That's a hard situation — it's not about avoiding blunders, but about tightening up your opening principles and move quality in the early game.

For your next games, I'd suggest two things. First, review the opening principles: develop knights and bishops before moving the f-pawn, control the center, and castle early. Second, when you're considering a move like **2...f6**, ask yourself: does this help my development, or does it just defend a pawn while creating weaknesses? Often the developing move is the better choice.

---

## item-07

**What the engine found:**

```
Game: White (maia5) vs Black (Zelessi), result 1-0.
Opening: D20 Queen's Gambit Accepted.
You are coaching the BLACK player (Zelessi); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 77.8 (opponent: 48.7; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 24...Ne7?! (inaccuracy): the engine preferred Rc4; cost about 18% win probability (cp loss 269).
- 4...Bd5?! (inaccuracy): the engine preferred Nf6; cost about 12% win probability (cp loss 143).
- 22...Nd5?! (inaccuracy): the engine preferred Nc5; cost about 12% win probability (cp loss 177).
- 3...Be6?! (inaccuracy): the engine preferred a6; cost about 11% win probability (cp loss 128).
```

**The coaching:**

You played a solid game overall — no blunders or outright mistakes, which is genuinely good. But the engine flagged a few inaccuracies that quietly let your position slip, and the most important one came at a critical moment.

The key moment was **24...Ne7**. This cost you the most — roughly 18% of your winning chances. The engine preferred **Rc4**, which likely keeps your rook active and puts real pressure on White's position. Instead, the knight move probably let White consolidate or gain time. When you're in a tense middlegame, ask yourself: which piece is doing the least? Your rook may have had a much stronger role to play than the knight did.

Earlier, **4...Bd5** and **3...Be6** both suggest a pattern: developing your bishop to squares where it can be challenged or where it doesn't coordinate well with the rest of your pieces. The engine preferred **Nf6** and **a6** respectively — moves that develop naturally and keep your structure flexible. Try to avoid moving the same piece twice in the opening unless there's a concrete reason.

**22...Nd5** is a similar story — the knight looked active, but **Nc5** would have placed it on a more stable, influential square.

So the main takeaway: your play was fundamentally sound, but you lost ground through slightly suboptimal piece placement rather than tactical errors. Work on asking "which square makes this piece most useful long-term?" before committing, especially in the middlegame. And in the opening, prioritize developing new pieces over repositioning ones you've already moved.

---

## item-08

**What the engine found:**

```
Game: White (maia1) vs Black (Pompoupopoppum), result 0-1.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (maia1); the opponent is Pompoupopoppum.

Objective engine summary:
- Your average centipawn loss: 71.7 (opponent: 55.4; lower is better).
- Across the whole game: 3 blunders, 3 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 20.f3?? (blunder): the engine preferred Nf3; cost about 63% win probability (cp loss 10137).
- 19.Nh4?? (blunder): the engine preferred Qc2; cost about 32% win probability (cp loss 363).
- 26.Qg3? (mistake): the engine preferred Rd1; cost about 26% win probability (cp loss 507).
- 25.g5? (mistake): the engine preferred Rd1; cost about 23% win probability (cp loss 267).
```

**The coaching:**

The game turned decisively around move 20, and it's worth understanding why. You played **20.f3**, which cost you roughly two-thirds of your winning chances in a single move — that's the kind of swing that decides games. The engine preferred **Nf3** instead. The idea is that your knight needed to stay active and coordinated with your pieces, while f3 weakened squares around your king without creating any real counterplay. When you're ahead or fighting for control, every tempo matters, and a quiet pawn move like this can let the initiative slip away.

Just before that, **19.Nh4** was also costly — the engine wanted **Qc2**, which keeps your queen flexible and ready to support your center. Nh4 looks aggressive, but it likely just gave your opponent targets or left your knight exposed without enough follow-up. The pattern here is clear: both of these moves were "active-looking" but actually weakened your position rather than improving it.

Later, **25.g5** and **26.Qg3** compounded the problem. Both times the engine preferred **Rd1**, which brings a rook into the game to support your center and create threats. Instead, you pushed pawns on the kingside without enough coordination — again, moves that look aggressive but don't address what's actually happening in the middle of the board.

The lesson from this game is about *piece activity and king safety*. When you're playing a sharp opening like the Scandinavian, your pieces need to be coordinated and doing real work. Pawn pushes on the wing without support often just create weaknesses. Work on asking yourself before each move: "Does this piece have a job? Does this pawn push actually help my position?" And when you see an aggressive-looking move, pause and check whether it creates more problems than it solves.

Two things to practice:
1. **Before pushing a pawn on the wing**, ask what your opponent's best reply is — if they can simply ignore it or counterattack, it's probably not worth it.
2. **Keep your queen flexible** in the middlegame. A queen that's tied down to one job (like attacking a square) often becomes a target rather than an asset.

---

## item-09

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (Sharkfang), result 1-0.
Opening: E61 King's Indian Defense.
You are coaching the BLACK player (Sharkfang); the opponent is DrNykterstein.

Objective engine summary:
- Your average centipawn loss: 42.5 (opponent: 32.5; lower is better).
- Across the whole game: 0 blunders, 2 mistakes, 5 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 38...Ng2? (mistake): the engine preferred Nxc2; cost about 23% win probability (cp loss 294).
- 21...Bxb5?! (inaccuracy): the engine preferred Ne8; cost about 14% win probability (cp loss 176).
- 31...cxb4?! (inaccuracy): the engine preferred Nxd5; cost about 12% win probability (cp loss 167).
- 17...Nf6?! (inaccuracy): the engine preferred f3; cost about 11% win probability (cp loss 115).
```

**The coaching:**

Your most critical error was **38...Ng2?** — this was a **mistake**, not a blunder, but it cost you **23% of your win chances**. The engine preferred **Nxc2**, which would have been a solid move to capture a pawn and improve your knight’s activity. Instead, your knight’s move to g2 was poorly placed, likely allowing White to exploit weaknesses in your position. This move directly contributed to your loss.  

The other inaccuracies were less severe but still impactful:  
- **21...Bxb5?!** (engine preferred **Ne8**) and **31...cxb4?!** (engine preferred **Nxd5**) both missed opportunities to develop pieces or control key squares.  
- **17...Nf6?!** (engine preferred **f3**) was an inaccuracy that likely weakened your center or left your pieces passive.  

While there’s no clear recurring pattern in your history (no player history data provided), your average centipawn loss of **42.5** (vs. White’s 32.5) suggests your moves were generally less accurate. Focus on:  
1. Studying the engine’s preferred moves for your inaccuracies (e.g., **Ne8**, **Nxd5**, **f3**) to understand why they were better.  
2. Practicing positions where knights are misplaced or where central control is critical — avoid hanging pieces or weakening your king’s safety.  

You’re on the right track, but refining your decision-making in critical moments will help you close games more effectively.

---

## item-10

**What the engine found:**

```
Game: White (lettucesuki) vs Black (maia5), result 0-1.
Opening: C50 Italian Game: Giuoco Piano.
You are coaching the WHITE player (lettucesuki); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 58.4 (opponent: 37.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Nf5?! (inaccuracy): the engine preferred d4; cost about 18% win probability (cp loss 235).
- 10.Ne3?! (inaccuracy): the engine preferred b4; cost about 13% win probability (cp loss 150).
- 7.d3?! (inaccuracy): the engine preferred c3; cost about 12% win probability (cp loss 134).
```

**The coaching:**

Let's look at your game. The good news first: you didn't make any outright blunders or mistakes — no hanging pieces, no catastrophic oversights. That's a solid foundation. Your average centipawn loss of 58.4 is a bit high, but it's being driven by a handful of quiet, positional inaccuracies rather than tactical disasters.

The most costly moment was **12.Nf5**. It's an attractive-looking move — the knight jumps into enemy territory and eyes the king's position — but the engine preferred **d4** instead. The problem is that Nf5 doesn't actually accomplish much concretely. The knight on f5 can often be kicked back or traded off, and while it sits there it isn't helping you fight for the center. Playing d4 would have struck at Black's central pawn chain, opened lines for your pieces, and given you a clear plan. You lost about 18% of your winning chances with that one decision, so it's worth understanding why the flashy knight move was less effective than the central break.

Earlier, **10.Ne3** and **7.d3** show a similar pattern: you're making reasonable, safe moves, but they're a little passive. At move 10, **b4** would have grabbed space on the queenside and disrupted Black's setup. At move 7, **c3** was preferred over d3 because it prepares the central push d4 while keeping the bishop's diagonal open. In all three cases, the engine is pointing toward the same theme: **fight for the center and create active plans rather than just developing pieces to safe squares.**

So here's the actionable takeaway: when you have a choice between a move that looks "fine" and a move that challenges your opponent's position — especially in the center — lean toward the challenging one. Ask yourself after each move: *"What is my plan here? Does this move help me control the center or create a threat?"* If the answer is no, look for something more ambitious.

Work on recognizing those moments in the opening and early middlegame where a central pawn break (like d4 or c3 followed by d4) is available. That alone will sharpen your play considerably.

---

## item-11

**What the engine found:**

```
Game: White (maia9) vs Black (Zelessi), result 1-0.
Opening: C40 King's Pawn Game: Damiano Defense.
You are coaching the BLACK player (Zelessi); the opponent is maia9.

Objective engine summary:
- Your average centipawn loss: 81.7 (opponent: 3.8; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 2...f6?! (inaccuracy): the engine preferred Nc6; cost about 11% win probability (cp loss 127).
```

**The coaching:**

The game was a clean one overall — no blunders, no mistakes from either side, and only one inaccuracy between you. That's genuinely good news. Your average centipawn loss of 81.7 is high, but the context here matters: this was your first real game against maia9, and they played very accurately themselves (3.8). You didn't collapse; you simply faced a strong opponent.

The one moment worth pausing on was **2...f6**. It wasn't catastrophic, but it cost you about 11% of your winning chances. The engine preferred **Nc6**, and the idea is instructive: in the Damiano Defense, developing the knight to c6 keeps your center flexible and prepares to challenge White's central pawn structure. Playing f6 early commits to a specific plan — often one that isn't as strong or as well-supported as simply developing pieces normally. It can also create weaknesses on f7 if it doesn't lead to something concrete.

The good news is that this was the only real slip in an otherwise solid game. You didn't hang anything, you didn't miss any tactics, and you held your own against a player who played very well.

**What to work on:**
1. **In the opening, prioritize development over early pawn moves.** Moves like f6 can feel active, but they often just give White time to develop comfortably while you're left with a slightly weakened position.
2. **When you play a move that commits to a plan (like f6), make sure it actually leads somewhere concrete.** If not, consider whether a quieter developing move would be better.

You played well against a strong opponent — keep doing that.

---

## item-12

**What the engine found:**

```
Game: White (maia1) vs Black (Gaurav677), result 1-0.
Opening: C20 King's Pawn Game: Beyer Gambit.
You are coaching the BLACK player (Gaurav677); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 44.0 (opponent: 13.7; lower is better).
- Across the whole game: 0 blunders, 1 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bd6? (mistake): the engine preferred Kc8; cost about 22% win probability (cp loss 367).
- 2...d5?! (inaccuracy): the engine preferred exd4; cost about 14% win probability (cp loss 160).
```

**The coaching:**

Let's start with the move that really turned things against you: **9...Bd6**. This was your one true mistake of the game, and it cost you a meaningful chunk of your winning chances. The problem is that the bishop on d6 doesn't actually accomplish much there — it just sits on an open diagonal without any real support or purpose. Meanwhile, the engine preferred **Kc8**, which keeps your king safe and prepares to develop naturally. The key idea here is that in the opening, every piece should have a clear job before you commit it to a square where it can be attacked or simply ignored. A bishop on d6 looks active, but if it's not protected and doesn't control anything important, it's just a target.

Earlier, **2...d5?!** was a smaller slip — an inaccuracy rather than a blunder. The engine preferred **exd4**, which would have kept your center flexible and avoided giving White a clear plan. By playing d5 instead, you opened lines for White and let them dictate the early development. It wasn't catastrophic, but it set a slightly uncomfortable tone.

The good news is that this was a clean game overall — no blunders from either side, just one real mistake on your part. Your average centipawn loss of 44 is higher than your opponent's 13, which tells the story: you made fewer small errors but one big one. That's actually a good sign — it means you're not hanging pieces or missing obvious tactics, but you need to tighten up in the opening.

**Two things to work on:**

1. **Before developing a piece, ask what it does there.** If the answer is "nothing much," look for another square where it can be useful and safe.
2. **In the opening, prioritize king safety and flexible development over quick pawn breaks.** Moves like d5 are tempting because they feel active, but if they leave your king exposed or give your opponent a clear plan, they're often not worth it.

You played a solid game against a strong opponent — now focus on refining those early decisions, and you'll convert more of these positions into wins.

---

## item-13

**What the engine found:**

```
Game: White (maia1) vs Black (Advitj), result 1-0.
Opening: A00 Hungarian Opening.
You are coaching the BLACK player (Advitj); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 86.5 (opponent: 35.1; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bxc2?? (blunder): the engine preferred Nxc2; cost about 32% win probability (cp loss 363).
- 10...Nxa2?! (inaccuracy): the engine preferred a5; cost about 18% win probability (cp loss 282).
- 11...Qf5?! (inaccuracy): the engine preferred Bxb3; cost about 11% win probability (cp loss 240).
- 8...Nb4?! (inaccuracy): the engine preferred Bh3; cost about 10% win probability (cp loss 113).
```

**The coaching:**

The big moment in this game was **9...Bxc2**. You captured with your bishop, but the engine wanted you to take with the knight instead — and that one choice cost you roughly a third of your winning chances. The reason is simple: when two pieces can recapture on the same square, taking with the piece that leaves your other piece safer matters more than which piece lands first. Here, capturing with the bishop likely left something important hanging or created a worse structure for Black, while the knight capture would have kept your position healthier.

The follow-up **10...Nxa2** compounded things slightly — it grabbed material but let White consolidate. The engine preferred **a5**, which suggests you were better off keeping tension and improving your pieces rather than trading into a more difficult middlegame. Then **11...Qf5** was another inaccuracy; the engine liked **Bxb3**, grabbing that pawn and staying active. You kept making reasonable moves, but each one let White steadily improve.

The pattern here is clear: you were often choosing between two good-looking captures or trades, and sometimes the "more natural" capture wasn't actually best — it just looked better. The engine's recommendations point to keeping your pieces coordinated and avoiding giving White easy targets.

**Two things to work on:**

1. **When two pieces can recapture, ask which one leaves you better off.** Before taking with a piece, check whether the other capture keeps more of your structure intact or improves your position more.
2. **Prefer active moves over material grabs when the position is tense.** Moves like **a5** and **Bxb3** show that sometimes improving your pieces or grabbing a pawn while keeping tension is stronger than trading into a worse middlegame.

You played well overall — one blunder is a lot to recover from, but this game shows you're capable of holding things together after a mistake. Tighten up those recapture choices and keep looking for the most active option in tense positions, and you'll convert more of these games.

---

## item-14

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1/2-1/2.
Opening: A14 English Opening: Agincourt Defense, Neo-Catalan Declined.
You are coaching the BLACK player (penguingm1); the opponent is BabyfaceAssassin.

Objective engine summary:
- Your average centipawn loss: 26.8 (opponent: 18.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...d4?! (inaccuracy): the engine preferred Bb7; cost about 14% win probability (cp loss 152).
```

**The coaching:**

Let's talk about that one moment that mattered most: **9...d4**.

It wasn't a blunder, and it didn't lose material, but it was the one move where you gave away a meaningful chunk of your position. The engine preferred **Bb7** instead. The idea is that by developing the bishop to b7 first, you keep your central pawn structure flexible and your pieces coordinated. Playing **d4** immediately closed the center and committed you to a structure where your pieces had less room to breathe. It cost you about 14% of your winning chances in one move — not because it was terrible, but because it made your position harder to play than it needed to be.

The good news is that this was your only real slip. Across the whole game, neither side made a single blunder or mistake — just this one inaccuracy. That tells me you played a very solid, disciplined game. Your average centipawn loss of 26.8 is respectable, and against an opponent who was also playing cleanly, a draw is a fair result.

The pattern here isn't about hanging pieces or missing tactics — it's about **timing in the opening**. You made a structural commitment (d4) before finishing your development (Bb7). When you close the center early, make sure your pieces are already placed to support the resulting structure.

**To work on:**
1. In the opening, ask yourself before pushing a central pawn: "Are my pieces ready for the structure this creates?" If not, develop first.
2. When you have a choice between a pawn move and a developing move, lean toward development unless the pawn move wins something concrete.

You're playing at a level where games are decided by small edges. Tightening up those opening decisions will start converting draws into wins.

---

## item-15

**What the engine found:**

```
Game: White (francis0181) vs Black (maia1), result 0-1.
Opening: A40 Englund Gambit.
You are coaching the WHITE player (francis0181); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 51.2 (opponent: 32.4; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 27.Rb7?? (blunder): the engine preferred e4; cost about 55% win probability (cp loss 700).
```

**The coaching:**

The big moment in this game was **27.Rb7**. That single move cost you roughly half your winning chances, and it's worth understanding why.

You had built a position where the center was still alive — the engine wanted **e4**, which would have kept fighting for space and control in the middle of the board. Instead, Rb7 looks like an active-looking rook move, but it actually handed your opponent a clear target. The idea behind e4 is that you keep the tension on the center; by pushing it, you force your opponent to react rather than letting them dictate where the fight happens. When you played Rb7 instead, you gave up that initiative and let Black consolidate.

The good news: this was your only real blunder of the game. You didn't make any mistakes or inaccuracies beyond that one moment — which is actually a solid foundation to build on. Your average centipawn loss of 51.2 isn't terrible, but it's higher than your opponent's 32.4, so there was room for improvement in keeping the position under control.

**What to work on:**

1. **When you have a choice between an active-looking move and a quiet one that keeps tension, pause and ask which keeps more pressure on your opponent.** Moves like Rb7 feel aggressive but can be passive if they don't create real threats or force a response.

2. **Review the center of the position before committing to a flank or rook move.** In this game, keeping e4 alive was worth far more than what you got from Rb7. Before moving a piece to an "active" square, check whether it actually creates a threat your opponent has to answer — and whether leaving the center open is better for you.

You played a clean game overall, so this loss is very fixable with these two ideas in mind.

---

## item-16

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (Sharkfang), result 1-0.
Opening: E61 King's Indian Defense.
You are coaching the BLACK player (Sharkfang); the opponent is DrNykterstein.

Objective engine summary:
- Your average centipawn loss: 42.5 (opponent: 32.5; lower is better).
- Across the whole game: 0 blunders, 2 mistakes, 5 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 38...Ng2? (mistake): the engine preferred Nxc2; cost about 23% win probability (cp loss 294).
- 21...Bxb5?! (inaccuracy): the engine preferred Ne8; cost about 14% win probability (cp loss 176).
- 31...cxb4?! (inaccuracy): the engine preferred Nxd5; cost about 12% win probability (cp loss 167).
- 17...Nf6?! (inaccuracy): the engine preferred f3; cost about 11% win probability (cp loss 115).
```

**The coaching:**

Let's look at your game. The overall numbers weren't bad — no blunders, and your average centipawn loss of 42.5 is respectable. But there was one moment that really changed the game, and a few smaller slips worth noting.

The big one was **38...Ng2?**. This cost you about 23% of your winning chances in a single move. The engine preferred **Nxc2**, which would have kept your knight active and grabbed material. Instead, Ng2 put the knight on a square where it could be contained or driven back, and you lost the initiative at a critical moment. When a game is tight late, one quiet move like this can be the difference between holding and losing.

Earlier, **21...Bxb5?!** was also costly. The engine preferred **Ne8**, which suggests your bishop was doing more work on its original diagonal than you got from the trade. Similarly, **31...cxb4?!** and **17...Nf6?!** both show a pattern: you sometimes made natural-looking moves that released tension or repositioned a piece, when keeping the pressure or improving a different piece would have been stronger.

The theme I'd highlight is **piece activity and patience**. None of these were tactical blunders — they were positional choices that slowly handed your opponent easier play. Work on asking yourself before a move like Ng2 or Bxb5: *"Is this piece better where it is, or where it's going?"* And when the engine suggests a quiet move like Ne8, it's often about keeping flexibility rather than forcing a trade.

For practice: focus on endgame and late-middlegame positions where one side has a slight edge. Try to identify which piece is your worst-placed piece and improve it before making any committal captures or pawn moves. That habit alone would have saved you a lot of equity in this game.

---

## item-17

**What the engine found:**

```
Game: White (francis0181) vs Black (maia1), result 0-1.
Opening: A40 Englund Gambit.
You are coaching the WHITE player (francis0181); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 51.2 (opponent: 32.4; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 27.Rb7?? (blunder): the engine preferred e4; cost about 55% win probability (cp loss 700).
```

**The coaching:**

Your most critical error was **27.Rb7??**, a blunder that cost you **55% of your winning chances** (cp loss 700). This move was a direct giveaway: instead of playing **e4** (the engine’s recommendation), you placed your rook on a square that allowed Black to exploit weaknesses in your position. This single mistake effectively handed Black the game.  

While your overall play had an average centipawn loss of **51.2** (compared to Black’s 32.4), the key takeaway is that **avoiding blunders** is critical in the endgame. Your inaccuracy at move 27 was the decisive factor here.  

**Actionable steps:**  
1. **Review endgame patterns** — focus on avoiding moves that expose your king or weaken your structure.  
2. **Double-check critical positions** (especially when under time pressure) to ensure you’re not sacrificing key pieces or allowing tactical threats.  

This game highlights how a single mistake can erase all prior effort. Stay sharp in the endgame!

---

## item-18

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: B01 Scandinavian Defense.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 103.3 (opponent: 26.7; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 6.Qe4?? (blunder): the engine preferred Qh5+; cost about 41% win probability (cp loss 478).
- 10.Qa3?! (inaccuracy): the engine preferred Qh4; cost about 13% win probability (cp loss 368).
```

**The coaching:**

The game turned on one moment, and it was a big one: **6.Qe4??**. This move cost you roughly 41% of your winning chances in a single stroke. The engine preferred **Qh5+**, which is a much more active idea — putting pressure on the king and keeping your queen centralized where it can influence key squares. By playing Qe4, you likely gave up that initiative or allowed Black to consolidate comfortably.

The second notable moment was **10.Qa3?!**, where **Qh4** would have been stronger. It wasn't a disaster by any means, but it let some of the momentum slip away — about 13% win probability is still meaningful in a sharp opening like this.

The good news: this was your only real blunder of the game, and you didn't make many mistakes beyond that. Your average centipawn loss of 103.3 is high, but it's driven mostly by one big error rather than a pattern of small leaks.

**What to work on:**
1. **Queen activity in the opening.** In positions like this, your queen belongs on open lines and near the enemy king — not tucked away or misplaced. Ask yourself before moving your queen: "Does this put pressure on something important?" If not, look for a more active square.
2. **When you're ahead or have an attack brewing, don't settle for a quiet move.** Qh5+ was the kind of forcing move that wins games — and missing it is exactly what happened here.

One good habit to build: after every opening move, pause and check whether your queen is doing something useful. If not, you're probably giving away your advantage before it even starts.

---

## item-19

**What the engine found:**

```
Game: White (maia1) vs Black (Advitj), result 1-0.
Opening: A00 Hungarian Opening.
You are coaching the BLACK player (Advitj); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 86.5 (opponent: 35.1; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bxc2?? (blunder): the engine preferred Nxc2; cost about 32% win probability (cp loss 363).
- 10...Nxa2?! (inaccuracy): the engine preferred a5; cost about 18% win probability (cp loss 282).
- 11...Qf5?! (inaccuracy): the engine preferred Bxb3; cost about 11% win probability (cp loss 240).
- 8...Nb4?! (inaccuracy): the engine preferred Bh3; cost about 10% win probability (cp loss 113).
```

**The coaching:**

Your most critical error was **9...Bxc2??**, a blunder that cost you over 32% of your winning chances. Capturing with the bishop on c2 was a terrible idea—it left your queen hanging and allowed White to immediately recapture with a powerful piece. The engine’s preferred move, **Nxc2**, would have preserved your queen and kept your pieces active. This was a decisive mistake that tilted the game in White’s favor.  

The other inaccuracies (10...Nxa2?!, 11...Qf5?!, 8...Nb4?!) were less severe but still costly. They reflect a pattern of poor piece placement and missed opportunities to develop your pieces harmoniously. For example, **8...Nb4** weakened your king’s position and blocked your bishop, while **11...Qf5** was an overly aggressive move that didn’t account for White’s counterplay.  

**Actionable steps:**  
1. **Focus on development:** Prioritize moving your pieces to active squares (like the bishop to h3 or knight to c6) rather than making isolated captures.  
2. **Avoid hanging pieces:** Always check if your captures leave your own pieces exposed.  
3. **Study the Hungarian Opening:** This opening is flexible, but you need to balance aggression with solid structure. Consider how White’s queen and bishop coordination gave them an edge.  

You’re making progress, but consistency in development and tactical awareness will help you avoid such costly errors. Keep working on these!

---

## item-20

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: C00 French Defense: Knight Variation.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 121.3 (opponent: 78.3; lower is better).
- Across the whole game: 0 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 13.Bf5+? (mistake): the engine preferred Qg4+; cost about 28% win probability (cp loss 342).
- 11.Qh4? (mistake): the engine preferred Qh5+; cost about 27% win probability (cp loss 306).
- 7.Nxe5? (mistake): the engine preferred Bb5+; cost about 21% win probability (cp loss 240).
- 15.Ne4?! (inaccuracy): the engine preferred d4; cost about 13% win probability (cp loss 228).
- 6.Qe1?! (inaccuracy): the engine preferred Re1; cost about 13% win probability (cp loss 140).
- 23.Rxf2?! (inaccuracy): the engine preferred Qxf2; cost about 11% win probability (cp loss 9427).
```

**The coaching:**

Your most critical error was **13.Bf5+?**, which cost you over 28% of your winning chances. Instead of delivering a check that doesn’t threaten much, the engine preferred **Qg4+**, which attacks the knight on e5 and opens lines for your queen. This move would have forced Black to defend more actively, giving you better control of the center.  

Other key mistakes included **11.Qh4?** (engine suggested **Qh5+** for a sharper attack) and **7.Nxe5?** (engine preferred **Bb5+** to exploit Black’s weakened structure). These show a pattern of missing tactical opportunities to disrupt Black’s setup. The inaccuracies, like **15.Ne4?** and **23.Rxf2?** (where the engine suggested **Qxf2**), highlight inconsistent piece activity—your pieces were often misplaced or not supporting each other.  

**Actionable steps:**  
1. Study tactical patterns like forks, pins, and discovered attacks—these were missed in key moments.  
2. Review games where you played passively in the center (e.g., moves 7–11) and practice dynamic openings to keep Black’s pieces under pressure.  

Focus on sharp, aggressive moves that create immediate threats. Your positional play was solid, but tactical precision needs sharpening!

---

## item-21

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: B01 Scandinavian Defense.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 103.3 (opponent: 26.7; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 6.Qe4?? (blunder): the engine preferred Qh5+; cost about 41% win probability (cp loss 478).
- 10.Qa3?! (inaccuracy): the engine preferred Qh4; cost about 13% win probability (cp loss 368).
```

**The coaching:**

Your most costly mistake was **6.Qe4??**, a blunder that cost you **41% of your winning chances**. This move weakens your queen’s position and allows Black to develop actively. The engine suggested **Qh5+**, which would have attacked Black’s king and forced critical counterplay. Instead, your queen became a target and lost tempo.  

The second key error was **10.Qa3?!**, an inaccuracy that cost **13% of your winning chances**. Moving the queen to a passive square without clear purpose let Black consolidate their position. The engine’s **Qh4** would have pressured your knight on f3 and disrupted your center.  

**Actionable steps:**  
1. **Check for threats** before moving your queen—especially in the opening. A queen on the 7th rank or attacking the king is often more valuable than a central pawn push.  
2. **Study the Scandinavian Defense** to avoid similar traps. Focus on how Black’s queen can become active (e.g., Qh5+) and how to counter it.  
3. **Avoid isolated pawn structures** by developing pieces before committing to central pawns.  

You’re making progress, but consistency in piece activity and threat awareness will help you avoid these costly errors.

---

## item-22

**What the engine found:**

```
Game: White (maia1) vs Black (ZValeryi), result 0-1.
Opening: C41 Philidor Defense.
You are coaching the WHITE player (maia1); the opponent is ZValeryi.

Objective engine summary:
- Your average centipawn loss: 107.2 (opponent: 32.9; lower is better).
- Across the whole game: 2 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Kxh2?? (blunder): the engine preferred Qh5; cost about 39% win probability (cp loss 451).
- 14.Kf3?? (blunder): the engine preferred Bg5; cost about 31% win probability (cp loss 9778).
```

**The coaching:**

Let's talk about the two big moments in this game, because they tell a clear story.

**The critical error: 12.Kxh2??**

This was the turning point. You captured a piece with your king, but in doing so you walked your king out into the open — and once the king is exposed in the middlegame, every enemy piece suddenly has a target. The engine wanted **Qh5** instead, which keeps your king safe and keeps your own attack alive. By taking with the king, you traded long-term safety for short-term material, and that's almost never a good deal when queens and minor pieces are still on the board.

**The follow-up: 14.Kf3??**

This is the move that really ended the game. Your king was already exposed, and now it stepped even further forward, into the center of the board, where it became a sitting target. The engine's suggestion, **Bg5**, develops a piece and creates counterplay — but more importantly, it doesn't move the king again. Once your king is wandering around in the middle of the board while your opponent still has their queen and pieces active, the position is usually lost no matter what else you do.

**The pattern here is clear:** both blunders involved moving the king into danger. That's the lesson to take away. In the opening and middlegame, your king's job is to stay hidden and safe — castled, behind pawns, away from the action. If you're ever tempted to move your king forward to grab material or escape a check, pause and ask: *"Is there any other move that keeps my king safe?"* Usually there is.

**What to work on:**

1. **King safety above all.** Before any move, glance at your king. Is it castled? Are there open lines toward it? If your king is exposed, make fixing that your top priority — even if it means giving back material.

2. **When you see a capture, check who's doing the capturing.** Capturing with the king is almost always wrong in the middlegame. Look for a piece that can do the same job while keeping the king tucked away.

You didn't lose this game because of a slow positional grind — you lost it because your king ended up in the middle of the board with nowhere to hide. Fix that habit and you'll stop giving away games like this one.

---

## item-23

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (PseudoBenko), result 1/2-1/2.
Opening: C50 Italian Game: Paris Defense.
You are coaching the WHITE player (DrNykterstein); the opponent is PseudoBenko.

Objective engine summary:
- Your average centipawn loss: 8.7 (opponent: 8.5; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

That was a genuinely solid game from you — zero flagged inaccuracies, mistakes, or blunders for either side, and an almost identical centipawn loss to your opponent. You played at the level of a strong club player, with no single moment where you walked into trouble.

The key takeaway here is that you didn't need to "fix" anything specific. When a game ends in a draw and both sides are playing cleanly, it's often because neither side created a decisive weakness. That's not a problem — it's the mark of good, solid chess.

One thing worth keeping in mind as you improve: when you're about to make a quiet move, ask yourself whether there's something more active or more purposeful available. In this game, you probably chose safe, reasonable moves without any major concessions, which is exactly what you should aim for at the club level. As you get stronger, you can start looking for ways to create small advantages — but right now, your play was already excellent.

Keep doing what you're doing: clean, principled chess with no big errors.

---

## item-24

**What the engine found:**

```
Game: White (EricRosen) vs Black (Happysanta), result 1-0.
Opening: D02 Queen's Pawn Game: London System.
You are coaching the BLACK player (Happysanta); the opponent is EricRosen.

Objective engine summary:
- Your average centipawn loss: 35.4 (opponent: 10.3; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 7...Be4?! (inaccuracy): the engine preferred Bxc5; cost about 12% win probability (cp loss 132).
```

**The coaching:**

The game was a clean one overall — no blunders, no mistakes from either side. That's genuinely good news. Your average centipawn loss of 35.4 is higher than your opponent's 10.3, but the gap came from just one inaccuracy, and it wasn't a catastrophic one.

The key moment was **7...Be4**. The engine preferred **Bxc5**, and the difference was meaningful: you gave up about 12% of your winning chances. The idea behind Bxc5 is straightforward — you can simply take on c5 and keep your bishop active, while Be4 doesn't accomplish as much. It's a small concession in development, but it let White consolidate slightly.

The good news is that this was the only real slip in an otherwise solid game. You didn't hang anything or miss any big tactical pattern — just one quiet move where a more direct capture would have kept things tighter.

**What to work on:**
1. **When you have a chance to trade pieces, calculate it seriously.** Bxc5 was available and safe; Be4 wasn't worse, but it let White improve their position for free.
2. **Keep playing like this.** Your accuracy is already solid — one inaccuracy isn't a weakness. The next step is converting small advantages into wins, which is exactly what happened here.

You're doing well. Tighten up those quiet moments and you'll convert more of these games.

---

## item-25

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (PseudoBenko), result 1/2-1/2.
Opening: C50 Italian Game: Paris Defense.
You are coaching the WHITE player (DrNykterstein); the opponent is PseudoBenko.

Objective engine summary:
- Your average centipawn loss: 8.7 (opponent: 8.5; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

That was a very clean game — the engine found no inaccuracies, mistakes, or blunders from either side, and your average centipawn loss was essentially level with your opponent's. In practical terms, you played a solid, disciplined game and gave away almost nothing.

Since there are no specific errors to point to, the main takeaway is simply that your consistency was excellent. A draw against a well-matched opponent in a quiet opening like the Italian is a perfectly good result when you never put yourself in real danger.

To keep improving from here, I'd suggest two things. First, review the middlegame moments where the position stayed balanced and ask yourself whether there were any chances to create more imbalance — not by taking risks, but by looking for plans that put your opponent under practical pressure. Second, keep doing whatever you did here in terms of avoiding blunders; that level of reliability is a real strength, and it will win you many games against players who eventually crack.

---

## item-26

**What the engine found:**

```
Game: White (maia1) vs Black (Gaurav677), result 1-0.
Opening: C20 King's Pawn Game: Beyer Gambit.
You are coaching the BLACK player (Gaurav677); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 44.0 (opponent: 13.7; lower is better).
- Across the whole game: 0 blunders, 1 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bd6? (mistake): the engine preferred Kc8; cost about 22% win probability (cp loss 367).
- 2...d5?! (inaccuracy): the engine preferred exd4; cost about 14% win probability (cp loss 160).
```

**The coaching:**

Your most critical error was **9...Bd6?**, which allowed White to dominate the center and gain a decisive edge. By moving the bishop to d6, you weakened your position and missed a stronger development option like **Kc8**, which would have supported your knight and kept your pieces active. This move cost you around 22% of your winning chances — a huge swing.  

The second issue was **2...d5?!**, an inaccuracy that let White solidify their center without pressure. The engine preferred **exd4**, which would have disrupted White’s setup and created immediate tension. While not as costly as the earlier mistake, it shows a pattern of passive central play.  

**Actionable steps:**  
1. **Prioritize development** — avoid moves that block your pieces or weaken your structure.  
2. **Study the Beyer Gambit** (C20) to understand better responses to early pawn advances.  
3. **Focus on central control** — use your pieces to challenge White’s center, not just occupy it.  

You’re making progress, but refining your opening choices will help you avoid these costly errors. Keep working on tactical awareness and positional understanding!

---

## item-27

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 0-1.
Opening: D06 Queen's Gambit Declined: Marshall Defense.
You are coaching the WHITE player (maia5); the opponent is mikesmcc.

Objective engine summary:
- Your average centipawn loss: 34.6 (opponent: 12.4; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 16.Ne2?! (inaccuracy): the engine preferred Na4; cost about 11% win probability (cp loss 130).
```

**The coaching:**

Your most costly move was **16.Ne2?!**, which cost you about 11% of your win probability. This move weakened your position by leaving the knight poorly placed, allowing Black to develop their pieces more actively and gain control of the center. The engine suggested **Na4** instead, which would have maintained better piece activity and pressure on Black’s position.  

While your overall game had only one inaccuracy, your average centipawn loss (34.6) indicates room for improvement in decision-making. Focus on avoiding moves that weaken your structure or let the opponent gain tempo.  

**Actionable steps:**  
1. Review the position after 16.Ne2 to understand why Na4 was better—study how knights should be placed in the Marshall Defense.  
2. Practice recognizing when a knight is misplaced (e.g., on the edge or blocking key squares) and prioritize central control.  

Keep up the strong play elsewhere! This one inaccuracy is fixable with targeted study.

---

## item-28

**What the engine found:**

```
Game: White (EricRosen) vs Black (ankbarn11), result 1-0.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (EricRosen); the opponent is ankbarn11.

Objective engine summary:
- Your average centipawn loss: 15.0 (opponent: 11.9; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

That was a genuinely solid game from you — zero flagged inaccuracies, mistakes, or blunders for either side, and an average centipawn loss of just 15.0, which is excellent. You played at a level where every move was reasonable, and there's no single moment to point to as the turning point.

Since there were no specific errors to correct, the focus should be on what you're already doing well: maintaining a clean game with no concessions in accuracy. The next step is likely about converting small advantages or improving your precision slightly under pressure — but this was not a game where either player needed fixing.

A good habit to build from this performance is to keep playing at that level consistently. When games are this clean, the real work comes in the middlegame and endgame, refining your decision-making rather than avoiding mistakes altogether.

---

## item-29

**What the engine found:**

```
Game: White (lettucesuki) vs Black (maia5), result 0-1.
Opening: C50 Italian Game: Giuoco Piano.
You are coaching the WHITE player (lettucesuki); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 58.4 (opponent: 37.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Nf5?! (inaccuracy): the engine preferred d4; cost about 18% win probability (cp loss 235).
- 10.Ne3?! (inaccuracy): the engine preferred b4; cost about 13% win probability (cp loss 150).
- 7.d3?! (inaccuracy): the engine preferred c3; cost about 12% win probability (cp loss 134).
```

**The coaching:**

You played a solid game overall — no blunders, no mistakes, and only four inaccuracies across both sides. That's genuinely respectable, especially in an opening like the Italian Game where things can get sharp quickly.

The most costly moment was **12.Nf5**. The engine preferred **d4**, and this one cost you about 18% of your winning chances. The idea behind d4 is to fight for space and control the center, while Nf5 looks active but actually gives up some central influence without a clear payoff. When you're ahead in development or have a good position, it's often better to consolidate with moves like d4 than to make an "active-looking" knight move that doesn't address what matters most.

Earlier, **10.Ne3** and **7.d3** were both slightly off-target. The engine preferred b4 and c3 respectively — moves that support your center more directly. In the Italian Game, small pawn moves like d3 or c3 are often better than a knight move to e3 because they prepare for central play rather than just developing a piece.

The pattern here is worth noting: you made three inaccuracies in the opening and early middlegame, all of which involved choosing a "safe-looking" move over one that fights for space or supports your center. That's not terrible — it's actually a very common habit among solid players who want to avoid mistakes. But when you're already doing well, those small concessions add up.

**Two things to work on:**

1. **Before making a "safe" developing move, ask yourself: does this fight for the center or just develop?** If it's the latter, look for a pawn move that does both.
2. **When you're ahead in development, prefer consolidating moves over flashy ones.** Moves like d4 and b4 are often more useful than a knight jumping to e3 or f5.

You're playing at a level where small improvements matter — keep doing this.

---

## item-30

**What the engine found:**

```
Game: White (EricRosen) vs Black (ankbarn11), result 1-0.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (EricRosen); the opponent is ankbarn11.

Objective engine summary:
- Your average centipawn loss: 15.0 (opponent: 11.9; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

You played a clean, error-free game with strong positional understanding and precise execution. The Scandinavian Defense is a solid choice, and your handling of the Mieses-Kotroc Variation was textbook—no mistakes, no blunders, and a clear path to victory. Your average centipawn loss (15.0) is slightly higher than your opponent’s (11.9), but this doesn’t reflect a flaw since the game was tactically sound and your strategy was effective.  

To build on this, focus on refining your **opening preparation**—study deeper variations of the Scandinavian to expand your repertoire. Also, practice **endgame technique** to convert small advantages reliably. Since you’ve already mastered tactical precision, now is the time to sharpen your positional intuition and time management in longer games. Keep up the excellent work!

---

## item-31

**What the engine found:**

```
Game: White (vyachesiav-9) vs Black (maia5), result 0-1.
Opening: B01 Scandinavian Defense: Valencian Variation.
You are coaching the WHITE player (vyachesiav-9); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 50.8 (opponent: 29.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 10.Qd2?! (inaccuracy): the engine preferred Qe2; cost about 18% win probability (cp loss 204).
- 12.Nxe4?! (inaccuracy): the engine preferred Qe1; cost about 11% win probability (cp loss 135).
- 7.h3?! (inaccuracy): the engine preferred Bb5; cost about 10% win probability (cp loss 110).
```

**The coaching:**

Your most costly mistake was **10.Qd2?**. This move weakened your center and allowed Black to gain a strong positional advantage. The engine suggested **Qe2**, which would have maintained control of the center and supported your knight on f3. By moving the queen to d2, you gave Black opportunities to exploit the weakened structure, costing you ~18% win probability.  

The other inaccuracies—**7.h3?** and **12.Nxe4?**—also missed key developmental ideas. At move 7, **Bb5** (instead of h3) would have developed your bishop actively and pressured Black’s knight on c6. At 12, **Qe1** (rather than Nxe4) would have kept your queen in the center, where it could influence key squares and support your pieces. These errors show a pattern of prioritizing pawn structure over active piece play, which let Black dominate the center and limit your options.  

**Actionable steps:**  
1. Practice openings where central control is critical (e.g., Scandinavian variations) and focus on developing pieces before committing to pawn moves.  
2. Avoid passive moves like h3 early on; instead, look for ways to develop your bishop to b5 or c4 to pressure Black’s setup.  
3. Study how to use the queen in the center to control key squares and support your knights.  

You’re making progress, but refining your opening choices and piece activity will help you avoid these costly errors. Keep working on those!

---

## item-32

**What the engine found:**

```
Game: White (lettucesuki) vs Black (maia5), result 0-1.
Opening: C50 Italian Game: Giuoco Piano.
You are coaching the WHITE player (lettucesuki); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 58.4 (opponent: 37.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Nf5?! (inaccuracy): the engine preferred d4; cost about 18% win probability (cp loss 235).
- 10.Ne3?! (inaccuracy): the engine preferred b4; cost about 13% win probability (cp loss 150).
- 7.d3?! (inaccuracy): the engine preferred c3; cost about 12% win probability (cp loss 134).
```

**The coaching:**

Your most costly move was **12.Nf5?!**, which cost you about **18% win probability**. This move weakens your position by overextending the knight and creating a target for Black’s counterplay. The engine preferred **d4**, which develops the knight actively and supports central control—key in the Italian Game. This inaccuracy allowed Black to seize the initiative and eventually win.  

The other inaccuracies—**10.Ne3?!** and **7.d3?!**—also missed solid alternatives. **10.Ne3** was suboptimal compared to **b4**, which would have better supported your knight and central pawns. **7.d3** (instead of **c3**) delayed development and left your pieces passive. These moves collectively show a pattern of hesitating to develop your pieces fully, which let Black dominate the center and dictate the game’s flow.  

**Actionable steps**:  
1. Study the **Italian Game** (C50) to understand how to develop your knights and control the center. Focus on moves like **c3** and **b4** for the knight.  
2. Practice positions where your knight is underdeveloped—try to spot when a move like **d4** or **b4** would be better than a passive move like **d3** or **Ne3**.  
3. Analyze the **12.Nf5** line in detail: why did Black capitalize so effectively? What follow-up moves did they play?  

You’re making progress, but consistency in development and central control will help you avoid these pitfalls. Keep working on those!

---

## item-33

**What the engine found:**

```
Game: White (EricRosen) vs Black (ankbarn11), result 1-0.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (EricRosen); the opponent is ankbarn11.

Objective engine summary:
- Your average centipawn loss: 15.0 (opponent: 11.9; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You made no flagged inaccuracies, mistakes, or blunders, and your average loss was low — a genuinely clean game.
```

**The coaching:**

That was a genuinely clean game — the engine found no inaccuracies, mistakes, or blunders from either side, and your average centipawn loss of 15.0 is very solid. There's no single moment to pick apart here, and that's worth acknowledging: you played a controlled, high-quality game from start to finish.

Since there are no specific errors to correct, the coaching takeaway is simpler. A game like this shows your fundamentals are in good shape — you didn't give your opponent easy targets, and you converted your advantage without drama. The main thing now is to keep doing whatever produced this level of consistency.

For future games, two things to focus on:

1. **Keep your decision quality high in quiet positions.** Clean games often come from not forcing things when there's nothing to force. You clearly did that well here.

2. **Review the moments where you had to choose between safe and ambitious continuations.** Even in a flawless game, those are the spots where you can learn the most about your own decision-making — not because you went wrong, but because they reveal your style.

Well played. This is the kind of game to save as a reference for how you want to approach the Scandinavian as White.

---

## item-34

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 1-0.
Opening: A01 Nimzo-Larsen Attack: Modern Variation.
You are coaching the BLACK player (mikesmcc); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 47.1 (opponent: 16.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 17...Rgd8?! (inaccuracy): the engine preferred Bxc3; cost about 14% win probability (cp loss 200).
```

**The coaching:**

Your most costly move was **17...Rgd8?** — a passive rook move that let White seize the initiative. Instead, the engine suggested **Bxc3**, which would have captured a pawn and immediately improved your position. By playing Rgd8, you weakened your piece activity and allowed White to dominate the center, costing you ~14% win probability.  

No other mistakes were listed, so your overall play was solid — just this one inaccuracy. To improve, focus on **active piece development** (especially your bishop and rook) and avoid passive moves like Rgd8. Practice recognizing when to trade pieces or recapture immediately to maintain pressure.  

Small adjustments here could make a big difference in similar positions. Keep working on tactical awareness and piece coordination!

---

## item-35

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1/2-1/2.
Opening: A14 English Opening: Agincourt Defense, Neo-Catalan Declined.
You are coaching the BLACK player (penguingm1); the opponent is BabyfaceAssassin.

Objective engine summary:
- Your average centipawn loss: 26.8 (opponent: 18.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...d4?! (inaccuracy): the engine preferred Bb7; cost about 14% win probability (cp loss 152).
```

**The coaching:**

Your most critical mistake was **9...d4?** — a missed opportunity to develop your bishop and maintain central control. By advancing the d-pawn, you weakened your position and allowed White to gain a slight edge. The engine’s preferred **Bb7** would have kept your bishop active, supported the center, and avoided unnecessary pawn advances. This single inaccuracy cost you around 14% in winning chances, which is significant in the middlegame.  

While there were no other blunders or mistakes, your overall centipawn loss (26.8) suggests your moves were slightly less precise than White’s. Since no recurring patterns were found in your history, this was a one-off error. To improve:  
1. **Prioritize development** in the opening, especially for the bishop.  
2. **Double-check pawn advances** for tactical soundness — avoid weakening your structure unless you have a clear plan.  
Keep practicing the English Opening’s variations, and focus on balancing piece activity with positional security.

---

## item-36

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: C00 French Defense: Knight Variation.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 121.3 (opponent: 78.3; lower is better).
- Across the whole game: 0 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 13.Bf5+? (mistake): the engine preferred Qg4+; cost about 28% win probability (cp loss 342).
- 11.Qh4? (mistake): the engine preferred Qh5+; cost about 27% win probability (cp loss 306).
- 7.Nxe5? (mistake): the engine preferred Bb5+; cost about 21% win probability (cp loss 240).
- 15.Ne4?! (inaccuracy): the engine preferred d4; cost about 13% win probability (cp loss 228).
- 6.Qe1?! (inaccuracy): the engine preferred Re1; cost about 13% win probability (cp loss 140).
- 23.Rxf2?! (inaccuracy): the engine preferred Qxf2; cost about 11% win probability (cp loss 9427).
```

**The coaching:**

Let's look at the key moments from your game. The most costly decision came on move 13, when you played **13.Bf5+**. The engine preferred **Qg4+** instead. The issue is that your bishop check didn't accomplish much — it let your opponent respond comfortably and you lost a lot of your advantage. **Qg4+** would have kept the pressure on and forced a more awkward response from Black. When you have a check available, ask yourself: which check actually improves my position the most?

Just before that, **11.Qh4** was also a significant slip. The engine wanted **Qh5+**. Your queen on h4 was less active and easier for Black to challenge, while **Qh5+** would have kept the initiative and made it harder for Black to untangle.

Earlier, **7.Nxe5** was a mistake. You grabbed a pawn, but the engine preferred **Bb5+** first. The problem is that taking on e5 allowed Black to develop with tempo and left your pieces uncoordinated. **Bb5+** would have disrupted Black's position before you committed to the capture.

There's a pattern here: in all three of these moments, you went for an immediate, flashy-looking move (a check or a capture) when a quieter move would have kept more long-term pressure. The engine's suggestions — **Qg4+**, **Qh5+**, **Bb5+** — all share a common theme: they improve your piece activity and keep Black on the defensive, rather than just grabbing material or giving a check that's easy to answer.

One more thing worth noting: **23.Rxf2** was a big inaccuracy. The engine preferred **Qxf2**. Capturing with the rook instead of the queen left your position much worse — the queen recapture would have kept your pieces better coordinated.

**To work on:** Before playing a check or a capture, pause and ask: "Does this actually improve my position, or am I just making a move because it's available?" Try to find the move that maximizes your piece activity and keeps your opponent's options limited. Also, when recapturing, think about which piece is best placed to do the job — sometimes the obvious recapture isn't the strongest one.

---

## item-37

**What the engine found:**

```
Game: White (maia1) vs Black (Gaurav677), result 1-0.
Opening: C20 King's Pawn Game: Beyer Gambit.
You are coaching the BLACK player (Gaurav677); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 44.0 (opponent: 13.7; lower is better).
- Across the whole game: 0 blunders, 1 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bd6? (mistake): the engine preferred Kc8; cost about 22% win probability (cp loss 367).
- 2...d5?! (inaccuracy): the engine preferred exd4; cost about 14% win probability (cp loss 160).
```

**The coaching:**

Let’s focus on the moment that really changed the game for you: **9...Bd6**.

That move cost you about 22% of your winning chances, which is a big swing from a single decision. The engine preferred **Kc8** instead. The idea is that after 9...Bd6, your bishop becomes a target and your king’s position gets more exposed. By playing **Kc8**, you would have kept your king safer and avoided giving White an easy way to create threats. In plain terms, 9...Bd6 looked active, but it actually handed your opponent a clear target and made your position harder to defend.

Earlier, **2...d5** was also a bit shaky. It’s not a losing move, but it gave up some of the solidity you could have kept with **exd4**. That choice cost you about 14% winning probability, so it set a slightly uncomfortable tone for the rest of the opening.

The good news is that you didn’t make any outright blunders, and your overall mistake count was very low. The main pattern here is that your two most costly moves both involved committing your pawns or pieces a little too early, which gave White chances to create pressure.

For your next games, I’d suggest working on two things:

1. **King safety first** — before developing a piece aggressively, ask yourself if it leaves your king more exposed or gives your opponent a clear target.
2. **Opening patience** — in the first few moves, prefer solid, flexible development over early pawn thrusts unless you’re sure they gain something concrete.

You’re already avoiding big blunders, which is great. Now it’s about tightening those small decisions so you don’t hand your opponent easy targets.

---

## item-38

**What the engine found:**

```
Game: White (fordonj) vs Black (maia1), result 1-0.
Opening: A40 Horwitz Defense.
You are coaching the BLACK player (maia1); the opponent is fordonj.

Objective engine summary:
- Your average centipawn loss: 153.5 (opponent: 136.8; lower is better).
- Across the whole game: 8 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 43...Qg3+?? (blunder): the engine preferred fxe5; cost about 94% win probability (cp loss 2601).
- 38...Qxc3+?? (blunder): the engine preferred a5; cost about 84% win probability (cp loss 1433).
- 28...Qxh4?? (blunder): the engine preferred Qg2+; cost about 44% win probability (cp loss 519).
- 31...g2?? (blunder): the engine preferred Qh3; cost about 33% win probability (cp loss 409).
- 30...g3? (mistake): the engine preferred Rh7; cost about 25% win probability (cp loss 307).
- 49...Rh6?! (inaccuracy): the engine preferred Kg5; cost about 20% win probability (cp loss 9614).
```

**The coaching:**

The game turned decisively in the late middlegame, and there were several moments where you let a winning position slip away. The most damaging was **43...Qg3+** — this single move cost you nearly the entire win probability. The engine preferred **fxe5**, which would have kept your advantage intact. Instead, the queen check looks tempting because it forces White to respond, but it actually lets White consolidate and eventually force a draw or even take over. When you're ahead in material or space, look for moves that improve your position rather than forcing a reply — especially when the forced reply just gives your opponent time to untangle.

Earlier, **38...Qxc3+** was another critical moment. The engine wanted **a5**, which would have kept pressure on White's queenside and maintained your initiative. Taking on c3 looks like it wins material, but it actually weakens your own position and gives White chances to counterattack. This is a common pattern in your game: you grab something that *looks* good, but it comes with long-term weaknesses.

**28...Qxh4** was also costly — the engine preferred **Qg2+**, which keeps your queen active and creates threats. Capturing on h4 feels like winning material, but it lets White's pieces become more coordinated against you.

The recurring theme across these mistakes is that you're often choosing moves that *look* forcing or material-gaining at the cost of long-term stability. When you have an advantage, prioritize keeping your position solid and your queen active over one-move wins.

**To work on:**
1. Before making a capture or check, ask yourself: "Does this actually improve my position, or does it just give my opponent time to respond?" If the answer is the latter, look for a quieter improving move instead.
2. When you're ahead in material or space, focus on consolidating and keeping your pieces coordinated rather than forcing immediate threats. A solid position with an advantage is often worth more than a slightly better one that's full of weaknesses.

---

## item-39

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1-0.
Opening: A04 Zukertort Opening.
You are coaching the WHITE player (BabyfaceAssassin); the opponent is penguingm1.

Objective engine summary:
- Your average centipawn loss: 21.0 (opponent: 0.0; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You had no single flagged blunder or mistake, but your average loss is high: you lost ground gradually through many small imprecisions rather than one big error — likely defending a steadily worse position.
```

**The coaching:**

You played a solid game and earned the win, but your gradual centipawn loss (21.0) suggests you steadily weakened your position through small, unaddressed errors. While there were no single blunders or tactical mistakes, the cumulative effect of these imprecisions let your opponent steadily improve their position. Focus on maintaining a balanced pawn structure and keeping your pieces actively engaged—small positional errors can snowball in the middlegame.  

Since the engine didn’t flag specific moves, consider reviewing the game to identify where your pieces felt passive or where you allowed your opponent to centralize their forces. Practice games where you prioritize long-term positional clarity over short-term gains. Two actionable steps: 1) Study how to avoid gradual weakening of your center, and 2) Work on keeping your king safe early to prevent your opponent from exploiting space. You’re on the right track—just refine your consistency!

---

## item-40

**What the engine found:**

```
Game: White (EricRosen) vs Black (Happysanta), result 1-0.
Opening: D02 Queen's Pawn Game: London System.
You are coaching the BLACK player (Happysanta); the opponent is EricRosen.

Objective engine summary:
- Your average centipawn loss: 35.4 (opponent: 10.3; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 7...Be4?! (inaccuracy): the engine preferred Bxc5; cost about 12% win probability (cp loss 132).
```

**The coaching:**

Let's talk about the one moment that really mattered in this game: **7...Be4**.

It wasn't a blunder, and it didn't lose material, but it was the kind of move that quietly gives away a lot. You put the bishop on e4, where it looks active, but the engine much preferred **Bxc5** — taking the bishop on c5. Why does that matter? Because after Bxc5, you're simplifying the position and removing one of White's active pieces, while keeping your own structure solid. Instead, Be4 allowed White to keep that bishop and probably gain time against your piece later. It cost you about 12% of your winning chances in one move — not because it was terrible, but because it let a good opportunity slip.

The good news is that this was your only real inaccuracy. No blunders, no outright mistakes. Against a strong opponent like Eric Rosen, that's a solid sign. Your average centipawn loss of 35.4 is higher than his 10.3, but that gap is mostly explained by this one decision and the general pressure of playing a very accurate opponent.

The pattern here isn't "you hang pieces" or "you miss tactics" — it's more subtle. It's about **choosing the most active-looking move instead of the most effective one**. Be4 looks like it does something, but Bxc5 actually accomplishes more: it trades off a key piece and stabilizes your position.

**What to work on:**
1. When you have a chance to trade a piece, ask yourself: *does this trade help me, or am I just keeping pieces on the board because they look active?* Often the quiet trade is stronger.
2. In the London System specifically, be alert to early chances to challenge White's dark-squared bishop. Taking on c5 when it's safe to do so is a common and effective idea.

You played a clean game overall — now it's about turning "solid" into "sharp" by spotting those small improvements.

---

## item-41

**What the engine found:**

```
Game: White (Zelessi) vs Black (maia1), result 0-1.
Opening: C00 French Defense: Knight Variation.
You are coaching the WHITE player (Zelessi); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 121.3 (opponent: 78.3; lower is better).
- Across the whole game: 0 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 13.Bf5+? (mistake): the engine preferred Qg4+; cost about 28% win probability (cp loss 342).
- 11.Qh4? (mistake): the engine preferred Qh5+; cost about 27% win probability (cp loss 306).
- 7.Nxe5? (mistake): the engine preferred Bb5+; cost about 21% win probability (cp loss 240).
- 15.Ne4?! (inaccuracy): the engine preferred d4; cost about 13% win probability (cp loss 228).
- 6.Qe1?! (inaccuracy): the engine preferred Re1; cost about 13% win probability (cp loss 140).
- 23.Rxf2?! (inaccuracy): the engine preferred Qxf2; cost about 11% win probability (cp loss 9427).
```

**The coaching:**

Let's start with the move that hurt you most: **13.Bf5+**. This check looks tempting because it forces a response, but it actually let your opponent off the hook. The engine preferred **Qg4+**, which keeps the pressure on and doesn't give Black time to consolidate. The key idea is that not every check is good — a check can be a wasted tempo if it lets your opponent develop comfortably while you're left with nothing concrete. You spent a move forcing a reply, but Black was able to answer in a way that kept their position solid.

The same theme shows up earlier: **11.Qh4** and **7.Nxe5** were both cases where the engine saw a more active option. At move 11, **Qh5+** would have kept your queen on the board with real pressure; instead, Qh4 let Black develop without immediate consequences. At move 7, **Bb5+** was stronger because it creates immediate threats and forces Black to react — taking on e5 just gave up a tempo for material that wasn't worth much in return.

There's also a pattern of slightly passive choices later: **15.Ne4**, **6.Qe1**, and even the very endgame move **23.Rxf2** (where **Qxf2** was preferred). None of these were catastrophic, but they all share a common thread — choosing a "safe" or routine-looking move when there was something more active available. That's understandable in a long game, but it cost you small chunks of your advantage repeatedly.

Two things to work on:

1. **Before playing a check or capture, ask: "What does this actually accomplish?"** If the answer is "nothing concrete," look for a move that creates real threats instead.
2. **When you have an active option (a queen check, a bishop pin), prefer it over a passive one unless there's a very good reason not to.** Active play keeps your opponent on the back foot.

You played well enough overall — no blunders, and only a few mistakes — but these small positional choices added up. Tighten those decisions in the middlegame and you'll convert more of these positions into wins.

---

## item-42

**What the engine found:**

```
Game: White (fordonj) vs Black (maia1), result 1-0.
Opening: A40 Horwitz Defense.
You are coaching the BLACK player (maia1); the opponent is fordonj.

Objective engine summary:
- Your average centipawn loss: 153.5 (opponent: 136.8; lower is better).
- Across the whole game: 8 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 43...Qg3+?? (blunder): the engine preferred fxe5; cost about 94% win probability (cp loss 2601).
- 38...Qxc3+?? (blunder): the engine preferred a5; cost about 84% win probability (cp loss 1433).
- 28...Qxh4?? (blunder): the engine preferred Qg2+; cost about 44% win probability (cp loss 519).
- 31...g2?? (blunder): the engine preferred Qh3; cost about 33% win probability (cp loss 409).
- 30...g3? (mistake): the engine preferred Rh7; cost about 25% win probability (cp loss 307).
- 49...Rh6?! (inaccuracy): the engine preferred Kg5; cost about 20% win probability (cp loss 9614).
```

**The coaching:**

Your most critical error was **43...Qg3+??**, a blunder that handed White a near-certain win. This move was a forced capture (White could reply 44.Qxg3+), but the engine suggested **fxe5** instead, which would have preserved your queen and kept the game alive. This mistake cost you **94% of your winning chances**—a devastating error in the endgame.  

Other blunders like **38...Qxc3+??** and **28...Qxh4??** also cost significant advantages. These moves allowed White to capture material or expose your king without resistance. The pattern here is clear: you’re making **forced, tactical errors** in critical positions, often sacrificing key pieces or leaving your king vulnerable.  

Your player history shows this is a **recurring issue** (fourth time in your games). While your overall rating trend is improving, this game’s blunders were worse than average.  

**Actionable steps:**  
1. **Study endgame blunders**—focus on avoiding forced captures and protecting your queen.  
2. **Practice tactical puzzles** with a focus on king safety and material gains.  
3. **Slow down in critical positions**—double-check if a move is truly forced before playing.  

You’re on the right track, but consistency in avoiding these errors will make a bigger difference.

---

## item-43

**What the engine found:**

```
Game: White (DrNykterstein) vs Black (Sharkfang), result 1-0.
Opening: E61 King's Indian Defense.
You are coaching the BLACK player (Sharkfang); the opponent is DrNykterstein.

Objective engine summary:
- Your average centipawn loss: 42.5 (opponent: 32.5; lower is better).
- Across the whole game: 0 blunders, 2 mistakes, 5 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 38...Ng2? (mistake): the engine preferred Nxc2; cost about 23% win probability (cp loss 294).
- 21...Bxb5?! (inaccuracy): the engine preferred Ne8; cost about 14% win probability (cp loss 176).
- 31...cxb4?! (inaccuracy): the engine preferred Nxd5; cost about 12% win probability (cp loss 167).
- 17...Nf6?! (inaccuracy): the engine preferred f3; cost about 11% win probability (cp loss 115).
```

**The coaching:**

The game was competitive overall — no single blunder, and your average centipawn loss of 42.5 is respectable for a player at this level. But there were a few moments where the position slipped away from you.

The most costly decision came on move 38: **38...Ng2?**. This was the turning point. The engine preferred **Nxc2**, which keeps your knight active and central, while Ng2 looks tempting because it attacks the pawn but actually just gives White a target to defend. By this stage of the game, you were already under pressure, so every tempo matters — Nxc2 would have kept more options alive for you. The cost was about 23% of your winning chances.

Earlier, **21...Bxb5?!** was also a bit loose. The engine preferred **Ne8**, which develops the knight and keeps your pieces coordinated. Grabbing the pawn on b5 felt natural, but it let White consolidate their position while you were still finishing development.

There's a pattern worth noticing: several of your inaccuracies involved choosing a slightly material or tactical-looking move over one that improves piece coordination or keeps your options open. **31...cxb4?!** and **17...Nf6?!** both fit this theme — taking something or making a developing move when the engine preferred a more solid, flexible choice.

Two things to work on:

1. **Before grabbing material or attacking, ask what you're giving up in return.** In positions where your opponent is already pressing, an active piece like Nxc2 is often worth more than a pawn.
2. **Prioritize development and coordination over early simplification.** Moves like Ne8 and f3 are about finishing your setup cleanly rather than forcing immediate action.

You played well overall — now the goal is to convert these small inaccuracies into solid, principled choices as the game progresses.

---

## item-44

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 1-0.
Opening: A01 Nimzo-Larsen Attack: Modern Variation.
You are coaching the BLACK player (mikesmcc); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 47.1 (opponent: 16.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 17...Rgd8?! (inaccuracy): the engine preferred Bxc3; cost about 14% win probability (cp loss 200).
```

**The coaching:**

The game was a clean one overall — no blunders, no mistakes from either side. That's genuinely good news. Your opponent played very accurately too, so this wasn't a contest decided by one catastrophic error.

The one moment worth pausing on is **17...Rgd8**. It wasn't terrible, but it was the most costly decision of the game, and it cost you about 14% of your winning chances. The engine preferred **Bxc3**, which suggests that capturing with the bishop was a more active or consolidating move at that moment. While I can't say exactly why Rgd8 was less effective without seeing the position, the key idea is worth keeping in mind: when you have a chance to trade pieces or capture something useful, it's often better than simply developing another piece to its natural square — especially if the capture improves your structure or removes an opponent's active piece.

The good news is that this was your only real slip. You didn't hang anything or miss any obvious tactics. Your average centipawn loss of 47.1 is higher than your opponent's 16.2, but that gap came from one inaccuracy rather than a series of small leaks. That tells me you're playing at a solid level — the difference was narrow and fixable.

**What to work on:**
1. **When you have a capture available, take a moment to compare it with your developing move.** Ask yourself whether the capture improves your position more than just moving the piece.
2. **Review this exact position again.** Try to understand why Bxc3 was better — that will help you spot similar opportunities in future games.

You're playing well. One small tweak, and you'll be even stronger.

---

## item-45

**What the engine found:**

```
Game: White (francis0181) vs Black (maia1), result 0-1.
Opening: A40 Englund Gambit.
You are coaching the WHITE player (francis0181); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 51.2 (opponent: 32.4; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 27.Rb7?? (blunder): the engine preferred e4; cost about 55% win probability (cp loss 700).
```

**The coaching:**

Let's talk about the moment that decided the game: **27.Rb7**.

That move was the one big blunder of the game. It cost you roughly 55% of your winning chances in a single stroke. The engine preferred **e4** instead. Why does that matter? Because at that stage of the game, your rook was doing important work where it was — controlling key squares and keeping your position coordinated. By sending it to b7, you likely gave your opponent a tempo or a tactical resource that let them escape or turn the tables. The engine's preference for e4 suggests you needed to grab space in the center and keep your pieces active, rather than going pawn-hunting on the queenside.

The good news: this was your only blunder, and you had no other mistakes. Your average centipawn loss of 51.2 is higher than your opponent's 32.4, but that gap is almost entirely explained by this one move. Before 27.Rb7, you were very much in the game.

So what should you work on?

1. **Before making a "greedy" move like Rb7, ask: what is my rook doing right now, and what does it stop doing if I move it?** Rooks often look inactive when they're actually holding a position together. If the engine wants a central pawn push instead, that's a signal your pieces were already well-placed and you needed to improve your pawn structure, not relocate a piece.

2. **In the endgame or late middlegame, prioritize activity and coordination over material grabs.** One pawn is rarely worth giving your opponent a free move or a tactical shot.

You played a solid game overall — one bad decision undid it. That's very fixable.

---

## item-46

**What the engine found:**

```
Game: White (EricRosen) vs Black (Happysanta), result 1-0.
Opening: D02 Queen's Pawn Game: London System.
You are coaching the BLACK player (Happysanta); the opponent is EricRosen.

Objective engine summary:
- Your average centipawn loss: 35.4 (opponent: 10.3; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 7...Be4?! (inaccuracy): the engine preferred Bxc5; cost about 12% win probability (cp loss 132).
```

**The coaching:**

Your most costly move was **7...Be4?** — a critical inaccuracy that cost you around 12% of your winning chances. By playing Be4, you weakened your bishop’s control over the center and allowed White to centralize their pieces more effectively. The engine’s preferred **Bxc5** would have captured a pawn, immediately improving your position and disrupting White’s development. This move highlights a recurring pattern of passive piece placement in your games (this is your fourth such instance).  

Since there are no other listed mistakes, focus on two things:  
1. **Prioritize active piece development** — avoid moves that weaken your position or let your opponent centralize freely.  
2. **Study the London System** — understand how to balance pawn structure and piece activity in this opening.  

This was a one-off error, but refining your decision-making in the opening will help you avoid similar pitfalls. Keep up the good work!

---

## item-47

**What the engine found:**

```
Game: White (maia1) vs Black (Pompoupopoppum), result 0-1.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (maia1); the opponent is Pompoupopoppum.

Objective engine summary:
- Your average centipawn loss: 71.7 (opponent: 55.4; lower is better).
- Across the whole game: 3 blunders, 3 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 20.f3?? (blunder): the engine preferred Nf3; cost about 63% win probability (cp loss 10137).
- 19.Nh4?? (blunder): the engine preferred Qc2; cost about 32% win probability (cp loss 363).
- 26.Qg3? (mistake): the engine preferred Rd1; cost about 26% win probability (cp loss 507).
- 25.g5? (mistake): the engine preferred Rd1; cost about 23% win probability (cp loss 267).
```

**The coaching:**

Your game had a few critical errors that cost you significant winning chances. The **worst move** was **20.f3??**, which allowed Black to seize a massive advantage. Instead of playing f3, the engine suggested **Nf3**, which would have maintained control of the center and kept your pieces active. This blunder dropped your win probability by over 60%, which is devastating.  

The second blunder, **19.Nh4??**, was similarly costly. The engine preferred **Qc2**, which would have supported your knight and kept your pieces coordinated. Both blunders show a pattern of **overextending** with untested moves, leaving your position vulnerable.  

Your other mistakes—**25.g5?** and **26.Qg3?**—were tactical errors. The engine recommended **Rd1** in both cases, which would have protected your queen and maintained a solid structure. These moves highlight a recurring issue: **hanging pieces** and **missing simple tactical opportunities**.  

**Actionable steps:**  
1. **Always double-check critical moves** (especially in the middle game) by calculating a few variations. Ask: *“What happens if I play this move?”*  
2. **Prioritize piece activity and safety** over flashy moves. For example, avoid weakening your center or exposing your queen without clear compensation.  

You’re making progress, but these errors are avoidable with more careful calculation. Focus on these two areas, and you’ll see improvement!

---

## item-48

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 1-0.
Opening: A01 Nimzo-Larsen Attack: Modern Variation.
You are coaching the BLACK player (mikesmcc); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 47.1 (opponent: 16.2; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 17...Rgd8?! (inaccuracy): the engine preferred Bxc3; cost about 14% win probability (cp loss 200).
```

**The coaching:**

Let's talk about the one moment that really mattered in this game: **17...Rgd8**.

It wasn't a blunder, and it didn't lose material, but it was the kind of move that quietly gives away the thread of the position. The engine preferred **Bxc3** — a move that challenges White's structure and creates immediate tension. By playing Rgd8 instead, you chose a natural-looking developing move, but it let White keep everything comfortable. In practical terms, that choice cost you about 14% of your winning chances. That's significant for a single quiet move.

The rest of the game was clean — no blunders, no outright mistakes. Your average centipawn loss of 47.1 is higher than your opponent's 16.2, but that gap is almost entirely explained by that one inaccuracy. In other words, you weren't outplayed move after move; you just let one critical moment slip.

The lesson here is about **timing and tension**. When you have a chance to change the structure or force your opponent to make a difficult decision — like taking on c3 — it's often worth doing before you continue with routine development. Rgd8 looked safe, but safe moves at the wrong moment can be costly.

For your next games, try this: before playing a natural-looking move, ask yourself, "Is there a more forcing option that creates problems for my opponent right now?" And when you spot a move like Bxc3 that challenges the position, take a moment to calculate it seriously — even if it feels less comfortable than a quiet developing move.

---

## item-49

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1-0.
Opening: A04 Zukertort Opening.
You are coaching the WHITE player (BabyfaceAssassin); the opponent is penguingm1.

Objective engine summary:
- Your average centipawn loss: 21.0 (opponent: 0.0; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You had no single flagged blunder or mistake, but your average loss is high: you lost ground gradually through many small imprecisions rather than one big error — likely defending a steadily worse position.
```

**The coaching:**

That was a genuinely clean game from both sides — zero blunders, zero mistakes, zero inaccuracies for either player. That's extremely rare and worth acknowledging first: you played solidly throughout.

The engine's average centipawn loss of 21 is higher than your opponent's 0, which tells the real story. You weren't outplayed in one big moment; instead, you lost ground gradually through many small imprecisions. That kind of steady drip can be harder to notice as it happens — a position that feels fine on every move ends up worse because each decision was just slightly less accurate than it could have been.

The good news is there's no single glaring error to fix. But the challenge now is converting this solid game into something even stronger. When you're ahead or holding a balanced position, small improvements in accuracy — spotting a slightly better developing move, keeping your pieces coordinated, resisting temptations to make "safe" moves when a more active one exists — will compound over many games.

Two things to work on:

1. **Slow down in quiet positions.** When the board isn't exploding with tactics, take an extra few seconds to ask: "Is there a move that improves my worst-placed piece or adds a second defender?" Often the best move is the one that makes your position slightly more harmonious rather than just avoiding trouble.

2. **Review games like this one critically.** Since there were no big errors, look for the moves where you had a choice between two reasonable options and picked the less accurate one. That's where real improvement happens — not by eliminating mistakes, but by choosing better ones in the ordinary moments.

---

## item-50

**What the engine found:**

```
Game: White (vyachesiav-9) vs Black (maia5), result 0-1.
Opening: B01 Scandinavian Defense: Valencian Variation.
You are coaching the WHITE player (vyachesiav-9); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 50.8 (opponent: 29.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 10.Qd2?! (inaccuracy): the engine preferred Qe2; cost about 18% win probability (cp loss 204).
- 12.Nxe4?! (inaccuracy): the engine preferred Qe1; cost about 11% win probability (cp loss 135).
- 7.h3?! (inaccuracy): the engine preferred Bb5; cost about 10% win probability (cp loss 110).
```

**The coaching:**

Let's look at your game. The good news first: you didn't make any outright blunders or mistakes — no hanging pieces, no tactical disasters. Your average centipawn loss of 50.8 is a bit high, but the game was decided by small, quiet choices rather than one big error.

The most costly moment was **10.Qd2**. This move cost you about 18% of your winning chances. The engine preferred **Qe2**, which keeps the queen more flexible and better placed to support the center and connect your rooks. Qd2 isn't terrible, but it puts the queen on a slightly awkward square where it can become a target or get in the way of your own pieces. In positions like this, small differences in piece placement matter a lot — the queen on e2 would have been more harmonious with your overall setup.

Your other two inaccuracies follow a similar theme. **12.Nxe4** (preferred: Qe1) and **7.h3** (preferred: Bb5) both show a tendency to make moves that feel natural but don't quite address the position's real needs. Nxe4 recaptures a piece, but Qe1 would have kept more tension and given you better coordination. And h3 is a typical "safety" move, but Bb5 would have been more active and put real pressure on your opponent.

The pattern here is clear: you're not losing games through big tactical oversights — you're losing them through slightly passive or slightly misplaced piece placement. Your moves are reasonable, but they're not the *most* purposeful moves available.

**What to work on:**

1. **Before each move, ask "what is my worst-placed piece?"** Then improve it. This simple habit would have caught all three of these inaccuracies — your queen and bishop both had better squares available.

2. **Be careful with automatic "safety" moves like h3.** They're not always wrong, but they're often played on autopilot when a more active move exists. Ask yourself if the threat you're preventing is actually real before spending a tempo on it.

You're playing solid chess — now the next step is making your pieces work harder for you.

---

## item-51

**What the engine found:**

```
Game: White (fordonj) vs Black (maia1), result 1-0.
Opening: A40 Horwitz Defense.
You are coaching the BLACK player (maia1); the opponent is fordonj.

Objective engine summary:
- Your average centipawn loss: 153.5 (opponent: 136.8; lower is better).
- Across the whole game: 8 blunders, 4 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 43...Qg3+?? (blunder): the engine preferred fxe5; cost about 94% win probability (cp loss 2601).
- 38...Qxc3+?? (blunder): the engine preferred a5; cost about 84% win probability (cp loss 1433).
- 28...Qxh4?? (blunder): the engine preferred Qg2+; cost about 44% win probability (cp loss 519).
- 31...g2?? (blunder): the engine preferred Qh3; cost about 33% win probability (cp loss 409).
- 30...g3? (mistake): the engine preferred Rh7; cost about 25% win probability (cp loss 307).
- 49...Rh6?! (inaccuracy): the engine preferred Kg5; cost about 20% win probability (cp loss 9614).
```

**The coaching:**

Let's talk about the moment that really decided the game: **43...Qg3+**.

You were completely winning at that point. The engine says this one move cost you about 94% of your winning chances. Instead of giving that check, the move was to play **fxe5** — capturing the pawn and keeping your position solid. The check felt active, but it didn't actually accomplish anything concrete, and it let your opponent escape. When you're winning, you don't need to force things. You just need to make moves that don't give your opponent counterplay.

There's a clear pattern in your other costly moves too. **38...Qxc3+** and **28...Qxh4** both show the same tendency: grabbing material or giving checks that look tempting, but that let the position slip. At move 28, **Qg2+** was the move — keeping the pressure on instead of taking the pawn. At move 38, **a5** was better than the queen check. And then **31...g2** and **30...g3** show a related issue: pushing pawns forward without making sure they're actually safe or that the position is ready for it. The engine preferred **Qh3** and **Rh7** — moves that keep your pieces coordinated and your king safe.

So the recurring theme is: when you had a winning or very good position, you went for the most forcing-looking or material-grabbing move instead of the move that kept everything under control. That's a very common habit, and it's fixable.

**What to work on:**

1. **When you're winning, slow down.** Before playing a check or a capture, ask yourself: "Does this actually improve my position, or am I just making a move because it looks active?" If you can't name a concrete reason it helps, look for a quieter move that keeps your advantage.

2. **Practice converting winning positions.** Play out positions where you're up material or have a big advantage against a computer or a friend, and focus on making safe, solid moves rather than flashy ones. The goal is to get comfortable with the feeling of "just don't blunder and the win will come."

---

## item-52

**What the engine found:**

```
Game: White (maia5) vs Black (Zelessi), result 1-0.
Opening: D20 Queen's Gambit Accepted.
You are coaching the BLACK player (Zelessi); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 77.8 (opponent: 48.7; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 24...Ne7?! (inaccuracy): the engine preferred Rc4; cost about 18% win probability (cp loss 269).
- 4...Bd5?! (inaccuracy): the engine preferred Nf6; cost about 12% win probability (cp loss 143).
- 22...Nd5?! (inaccuracy): the engine preferred Nc5; cost about 12% win probability (cp loss 177).
- 3...Be6?! (inaccuracy): the engine preferred a6; cost about 11% win probability (cp loss 128).
```

**The coaching:**

Let's start with the move that hurt you most: **24...Ne7**. This was your biggest slip of the game, and it cost you roughly 18% of your winning chances. The engine preferred **Rc4**, which keeps your rook active and puts pressure on White's position. By retreating to e7 instead, you gave up that initiative — a piece that looks safe can still be doing important work elsewhere.

Earlier in the game, there were a few smaller slips worth noting. **22...Nd5** was another moment where **Nc5** would have been better. The knight on d5 is not badly placed, but Nc5 keeps more options open and avoids any long-term weaknesses. Similarly, **4...Bd5** and **3...Be6** both show a pattern: developing the bishop to a square that looks active but doesn't actually accomplish much — the engine preferred quieter, more flexible moves like Nf6 or a6. These aren't catastrophic, but they let White slowly build an advantage.

The good news is there were no blunders and no outright mistakes in this game. Your average centipawn loss of 77.8 is higher than your opponent's 48.7, which tells me you made several small errors rather than one big one — that's actually a sign of solid play under pressure.

**What to work on:**
1. **Keep pieces active and flexible in the opening.** Moves like Nf6 and a6 are quieter but set up better piece coordination later.
2. **When choosing between two developing moves, ask which one leaves your opponent with fewer plans.** Retreating or moving a piece to a "safe" square can sometimes just give them time to improve their own pieces instead.

You played a clean game overall — now the goal is to convert that solid foundation into more precise middle-game choices.

---

## item-53

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1-0.
Opening: A04 Zukertort Opening.
You are coaching the WHITE player (BabyfaceAssassin); the opponent is penguingm1.

Objective engine summary:
- Your average centipawn loss: 21.0 (opponent: 0.0; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 0 inaccuracies (both sides combined).

You had no single flagged blunder or mistake, but your average loss is high: you lost ground gradually through many small imprecisions rather than one big error — likely defending a steadily worse position.
```

**The coaching:**

You played a clean game in the sense that there was no single catastrophic error — no blunders, no mistakes, no inaccuracies flagged for either side. That's genuinely hard to do, and it tells me you weren't giving material away or walking into simple tactics.

But the average centipawn loss of 21.0 tells the real story: you were slowly bleeding position the whole game. Your opponent's 0.0 average means they essentially played the engine's top choice every move, while you were consistently choosing second- or third-best options. None of them were bad enough to be flagged individually, but they added up. You were likely defending a slightly worse position for most of the game, and small imprecisions in defense compound quickly.

Since there are no specific moves to point to, here's what I'd focus on:

**1. When you're defending, fight for activity, not just survival.** Small inaccuracies in worse positions often come from passive moves — retreating pieces to safe squares, making waiting moves, or trading into a slightly worse ending. Instead, look for the move that creates the most counterplay, even if it looks risky. The engine's top choice in a worse position is often a move that challenges the opponent's plan rather than just parrying it.

**2. Compare your candidate moves more carefully in quiet positions.** With no tactics on the board, the difference between a good move and a slightly less good move is often about piece placement, pawn structure, or king safety. Before you move, ask: "Does this improve my worst-placed piece? Does it restrict my opponent's best piece? Does it create a weakness I'll regret in five moves?"

You didn't lose this game because of one bad decision — you lost it because your opponent made slightly better decisions on nearly every move. That's a fixable problem, and it starts with being more demanding of your moves in quiet positions.

---

## item-54

**What the engine found:**

```
Game: White (maia5) vs Black (Zelessi), result 1-0.
Opening: D20 Queen's Gambit Accepted.
You are coaching the BLACK player (Zelessi); the opponent is maia5.

Objective engine summary:
- Your average centipawn loss: 77.8 (opponent: 48.7; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 6 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 24...Ne7?! (inaccuracy): the engine preferred Rc4; cost about 18% win probability (cp loss 269).
- 4...Bd5?! (inaccuracy): the engine preferred Nf6; cost about 12% win probability (cp loss 143).
- 22...Nd5?! (inaccuracy): the engine preferred Nc5; cost about 12% win probability (cp loss 177).
- 3...Be6?! (inaccuracy): the engine preferred a6; cost about 11% win probability (cp loss 128).
```

**The coaching:**

Your most costly move was **24...Ne7?** — this weakened your central control and allowed White to gain a strong initiative. The engine preferred **Rc4**, which would have maintained better piece activity and pressure. This inaccuracy directly cost you around 18% of your winning chances.  

Other notable inaccuracies include **4...Bd5?**, **22...Nd5?**, and **3...Be6?**. These moves all involved suboptimal piece placement, often delaying development or weakening your structure. While less costly than 24...Ne7, they collectively contributed to a gradual loss of momentum.  

There’s no clear recurring pattern in your mistakes, but several moves (like 3...Be6 and 22...Nd5) show a tendency to overcommit to central pawns too early. This can limit flexibility and create weaknesses.  

**Actionable steps:**  
1. Focus on **accurate piece development** in the opening — prioritize moving knights and bishops to natural squares (e.g., Nf6, Bf5) rather than overextending.  
2. Avoid **premature central pawn advances** (like 3...Be6 or 4...Bd5) without clear follow-up. Central pawns should support piece activity, not block it.  

You’re playing solidly overall, but refining these small details will help you hold positions more effectively. Keep up the good work!

---

## item-55

**What the engine found:**

```
Game: White (maia1) vs Black (Advitj), result 1-0.
Opening: A00 Hungarian Opening.
You are coaching the BLACK player (Advitj); the opponent is maia1.

Objective engine summary:
- Your average centipawn loss: 86.5 (opponent: 35.1; lower is better).
- Across the whole game: 1 blunders, 0 mistakes, 4 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...Bxc2?? (blunder): the engine preferred Nxc2; cost about 32% win probability (cp loss 363).
- 10...Nxa2?! (inaccuracy): the engine preferred a5; cost about 18% win probability (cp loss 282).
- 11...Qf5?! (inaccuracy): the engine preferred Bxb3; cost about 11% win probability (cp loss 240).
- 8...Nb4?! (inaccuracy): the engine preferred Bh3; cost about 10% win probability (cp loss 113).
```

**The coaching:**

Let's focus on the moment that really turned the game: **9...Bxc2**. This was the one true blunder, and it cost you about a third of your winning chances in a single move. The problem is that after this capture, your bishop ends up on a square where it can be challenged or trapped, and you've spent time grabbing a pawn while your development stalls. The engine's preference, **Nxc2**, achieves a similar material gain but with a piece that is far better placed and harder to punish. When you're tempted to grab a pawn, always ask: *after I take it, is my piece safe, and am I still developing?*

The next few moves show a related pattern. **10...Nxa2** and **11...Qf5** both look active, but they're really just more pawn-grabbing and piece-shuffling while White consolidates. The engine would have preferred **a5** and **Bxb3** — moves that fight for space and activity rather than chasing material on the edge of the board. And earlier, **8...Nb4** was a small inaccuracy; **Bh3** would have challenged White's bishop and kept your pieces coordinated.

The theme here is clear: you were too focused on winning pawns and not focused enough on piece activity and development. In the opening and early middlegame, every tempo matters. A pawn is rarely worth falling behind in development or placing a piece where it can be attacked.

**To work on:**  
1. Before capturing a pawn, check whether your piece will be safe and whether you're falling behind in development.  
2. In the opening, prioritize piece activity and fighting for the center over material gain. A well-placed piece is worth more than a stray pawn.

---

## item-56

**What the engine found:**

```
Game: White (maia1) vs Black (ZValeryi), result 0-1.
Opening: C41 Philidor Defense.
You are coaching the WHITE player (maia1); the opponent is ZValeryi.

Objective engine summary:
- Your average centipawn loss: 107.2 (opponent: 32.9; lower is better).
- Across the whole game: 2 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 12.Kxh2?? (blunder): the engine preferred Qh5; cost about 39% win probability (cp loss 451).
- 14.Kf3?? (blunder): the engine preferred Bg5; cost about 31% win probability (cp loss 9778).
```

**The coaching:**

The game turned on two moments in the middlegame, and both were costly for you.

**The most important one was 12.Kxh2.** This move looks tempting — grabbing a pawn feels good — but it walked into trouble. The engine preferred Qh5 instead. The key idea is that your king was still too exposed to be wandering off on its own, and the queen could have kept pressure on while staying safe. By taking the pawn with the king, you gave up control of the position and let Black consolidate. That one decision cost you about a third of your winning chances.

**Then came 14.Kf3, which was even worse.** The engine wanted Bg5 — developing a piece to its most active square while keeping your king tucked away. Instead, moving the king again left it vulnerable and gave Black a huge opening to attack. This second blunder nearly cost you the game outright.

The pattern here is clear: both of your biggest errors involved moving your king into danger when it wasn't yet safe. In chess, kings are only strong when they're hidden behind pawns or supported by pieces. Once exposed, every move with the king becomes a target.

**What to work on:**
1. **King safety first.** Before making any king move in the opening and early middlegame, ask yourself: "Is my king safe here?" If not, look for a developing move instead.
2. **Don't grab pawns blindly.** A pawn is only worth taking if you can do so safely and it improves your position — or if it's part of a bigger plan. Here, the pawn was just bait.

You played well enough to fight this game, but these two king-related blunders decided it. Tighten up those early decisions and you'll convert more positions like this one.

---

## item-57

**What the engine found:**

```
Game: White (maia1) vs Black (Pompoupopoppum), result 0-1.
Opening: B01 Scandinavian Defense: Mieses-Kotroc Variation.
You are coaching the WHITE player (maia1); the opponent is Pompoupopoppum.

Objective engine summary:
- Your average centipawn loss: 71.7 (opponent: 55.4; lower is better).
- Across the whole game: 3 blunders, 3 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 20.f3?? (blunder): the engine preferred Nf3; cost about 63% win probability (cp loss 10137).
- 19.Nh4?? (blunder): the engine preferred Qc2; cost about 32% win probability (cp loss 363).
- 26.Qg3? (mistake): the engine preferred Rd1; cost about 26% win probability (cp loss 507).
- 25.g5? (mistake): the engine preferred Rd1; cost about 23% win probability (cp loss 267).
```

**The coaching:**

Let's break down what happened, because there's a clear story in these numbers.

The move that really decided the game was **20.f3**. This was a massive blunder — it cost you almost the entire game in one move. The engine wanted **Nf3**, which would have kept your position solid and your pieces coordinated. Instead, f3 looks like it was meant to grab space or push the opponent back, but it likely created weaknesses around your king and gave your opponent a target. When a move costs 63% of your winning chances, it's usually because it opens lines against your own king or hangs something tactically. That's the moment to study most closely.

Just before that, **19.Nh4** was also a serious error. The knight on h4 is often misplaced — it's on the rim, far from the center, and easy to attack or ignore. The engine preferred **Qc2**, which would have kept your queen active and your pieces connected. These two moves together suggest a pattern: in the late middlegame, you started making aggressive-looking moves that actually weakened your position rather than improving it.

Later, **25.g5** and **26.Qg3** continued that theme. Both were mistakes, and in both cases the engine wanted **Rd1** — a simple, solid developing move that puts a rook on an open or semi-open file. Instead, you kept pushing pawns and moving the queen around, which often creates weaknesses without a clear payoff.

The overall picture: your average centipawn loss was 71.7, meaning you were losing the equivalent of about three-quarters of a pawn per move on average. That's high, and it's driven by a few very costly decisions rather than many small inaccuracies. The good news is that means there are specific, fixable moments.

**What to work on:**

1. **Before making an aggressive pawn move or queen move in the middlegame, ask: does this improve my worst-placed piece?** In several key moments, the engine wanted a simple developing move (Nf3, Rd1) instead of the flashier move you chose. Prioritize piece activity and king safety over pawn pushes.

2. **Study the position after 19.Nh4 and 20.f3 carefully.** Try to understand why the knight belonged on f3 and why f3 was so damaging. Look at what your opponent was threatening and what weaknesses f3 created. That single sequence likely lost the game.

---

## item-58

**What the engine found:**

```
Game: White (maia5) vs Black (mikesmcc), result 0-1.
Opening: D06 Queen's Gambit Declined: Marshall Defense.
You are coaching the WHITE player (maia5); the opponent is mikesmcc.

Objective engine summary:
- Your average centipawn loss: 34.6 (opponent: 12.4; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 16.Ne2?! (inaccuracy): the engine preferred Na4; cost about 11% win probability (cp loss 130).
```

**The coaching:**

You played a solid game overall — no blunders, no mistakes, and only one inaccuracy across both sides. That's genuinely good news to start with.

The one moment worth pausing on was **16.Ne2**. It wasn't catastrophic, but it let the position drift slightly from you. The engine preferred **Na4**, which keeps your knight active and flexible rather than retreating to a passive square. The idea is that when you have a choice between moving a piece forward or backward, prefer the move that improves the piece — especially if the retreat doesn't actually solve any problem.

The good news is that this was your only real slip of the game. You didn't hang anything or miss a big tactical shot; you just had one moment where a slightly more active plan would have kept things tighter.

**To work on:** When you're deciding between two knight moves, ask yourself which one improves the piece more — not just whether it's safe. And keep playing like this: solid, clean chess is very hard to beat.

---

## item-59

**What the engine found:**

```
Game: White (BabyfaceAssassin) vs Black (penguingm1), result 1/2-1/2.
Opening: A14 English Opening: Agincourt Defense, Neo-Catalan Declined.
You are coaching the BLACK player (penguingm1); the opponent is BabyfaceAssassin.

Objective engine summary:
- Your average centipawn loss: 26.8 (opponent: 18.1; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 9...d4?! (inaccuracy): the engine preferred Bb7; cost about 14% win probability (cp loss 152).
```

**The coaching:**

The game was a solid draw, and there's no single moment where you lost control — that's worth noting. Your average centipawn loss of 26.8 is respectable, and both sides played cleanly with zero blunders or mistakes.

The one inaccuracy came at move 9: **9...d4?!**. The engine preferred **Bb7**, and the difference was meaningful — roughly a 14% swing in your winning chances. The idea behind Bb7 is to develop a piece toward the center while keeping your position flexible, rather than committing pawns early on d4. By playing d4, you may have opened lines or created weaknesses that weren't immediately compensated for, and it cost you some of the initiative.

The good news: this wasn't a catastrophic error. You didn't hang anything or miss a tactic — just a small positional slip. The lesson here is about patience in the opening. When you're not sure which pawn break is best, prefer developing with Bb7 over committing to d4 unless you have a concrete reason (like gaining space or attacking something specific).

For your next games, two things to work on:
1. **Be careful with early pawn breaks** — ask yourself whether the pawn push actually improves your position or just creates weaknesses.
2. **Keep developing pieces first** in the opening. Pawn moves are often more dangerous than piece moves because they're harder to undo.

You played a clean game overall, and this draw is a fair result against an opponent who also held things together well. Keep building on that solid foundation.

---

## item-60

**What the engine found:**

```
Game: White (maia9) vs Black (Zelessi), result 1-0.
Opening: C40 King's Pawn Game: Damiano Defense.
You are coaching the BLACK player (Zelessi); the opponent is maia9.

Objective engine summary:
- Your average centipawn loss: 81.7 (opponent: 3.8; lower is better).
- Across the whole game: 0 blunders, 0 mistakes, 1 inaccuracies (both sides combined).

Your most costly moves (worst first):
- 2...f6?! (inaccuracy): the engine preferred Nc6; cost about 11% win probability (cp loss 127).
```

**The coaching:**

Your single inaccuracy at **2...f6** was the key issue. This move weakens your kingside and allows White to control the center more effectively. The engine preferred **Nc6**, which develops a piece and maintains structural balance. By playing f6, you gave White a tempo advantage and created long-term weaknesses in your position.  

Since there were no other mistakes, this was the sole misstep. To improve, focus on:  
1. **Studying the Damiano Defense** to understand optimal development (e.g., Nc6, Bb4+).  
2. **Avoiding early pawn advances** on the kingside unless they serve a clear purpose (like preparing a counterattack).  

Your game was otherwise solid, so keep building on that foundation!

---
