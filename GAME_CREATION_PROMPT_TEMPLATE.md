# ChatGPT Prompt Template for Creating HTML STEM & Multidisciplinary Games (Zimbabwean HBC Aligned)

Use this prompt template when asking ChatGPT to create standalone HTML educational games for the Game Events Management system (`/akello-game-events`). Generated HTML is pasted into **Game Management → Create New Game**.

Age-range values and subject frameworks strictly align with the **Zimbabwean Heritage-Based Curriculum (HBC)**. Age-range values must match the platform exactly. Do not invent new brackets.

---

## Prompt Template

```
Create a complete, standalone HTML educational game aligned with the Zimbabwean Heritage-Based Curriculum (HBC) that can be embedded in a web application. The game must meet ALL of the following requirements.

**HOST / EMBED REQUIREMENTS:**
1. **Complete HTML Structure**: Full HTML document with <!DOCTYPE html>, <head>, and <body> tags.
2. **Self-contained**: All CSS in <style> tags in <head>; all JavaScript in <script> tags (preferably before </body>).
3. **Score Tracking**: Track a score variable and display it in real-time.
4. **Score Display Element**: An element with id="scoreBox" that displays the current score as "Score: X / Y" (X = current score, Y = maximum possible score).
5. **Completion Button**: A button with id="checkBtn" that, when clicked, shows the final score and triggers score submission.
6. **Score Submission**: When the game is completed (checkBtn clicked), call window.gameScoreSubmit(finalScore, maxScore).
7. **No External Dependencies**: No CDN / external libraries. Vanilla JavaScript and CSS only.
8. **Responsive Design**: Desktop and mobile; touch-friendly.
9. **Clear Instructions**: Age-appropriate instructions aligned with the specified age spec.
10. **Visual Feedback**: Immediate visual feedback for correct/incorrect actions.

---

**ZIMBABWEAN HBC LEARNING AREAS BY AGE BRACKET:**

Select ONLY from the learning areas authorized for your specified target age bracket:

**Group A: Primary Bracket (Ages 9-10, 11-12)**
Allowed Learning Areas (HBC Primary Framework):
- English Language
- Mathematics
- Social Science
- Science and Technology

**Group B: Secondary & Post-Secondary Bracket (Ages 13-14, 15-16, 17-19, Youths & older)**
Allowed Learning Areas (HBC Secondary/Higher Framework):
- English Language
- Mathematics
- Geography
- Combined Science
- ICT (Information and Communication Technology)

---

**AGE RANGE**: [MUST be exactly one of: Infants | 9-10 | 11-12 | 13-14 | 15-16 | 17-19 | 9-19 | Youths & older]

**SELECTED LEARNING AREA**: [Select 1 allowed learning area based on the age range above]

**DIFFICULTY LEVEL**: [easy | medium | hard]

**TOPIC**: [e.g., "Geography - Map Reading & Topography", "Mathematics - Algebra", "Science and Technology - Ecosystems"]

**NUMBER OF QUESTIONS/ROUNDS**: [Default: 10]

**MAXIMUM SCORE**: [Default: 10 — 1 point per round]

---

**AGE-RANGE SPEC:**

### Infants (under 9)
- **Primary Mechanics:** Drag-and-drop, direct matching, tap-to-count, visual/spatial sorting.
- **UX & Visuals:** Audio-first instructions (use speechSynthesis), zero text dependencies, oversized touch targets (min 56px), immediate celebrations.
- **Failure Rules:** Zero penalties; immediate gentle guidance; no deductives; no failure screens.

### 9-10 & 11-12 (Group A Learning Areas Only)
- **Primary Mechanics:** Untimed micro-puzzles, balance scales, tile-matching, resource collection loops, node path navigation.
- **UX & Visuals:** Clean menus, concise tooltips, structured progress dashboards, milestone badges.
- **Failure Rules:** Low-stakes retries with direct diagnostic hint triggers showing where reasoning diverged.

### 13-14 & 15-16 (Group B Learning Areas Only)
- **Primary Mechanics:** Modular skill trees, formula puzzles, multi-variable input sliders, interactive sandboxes, scenario choices.
- **UX & Visuals:** Detailed stats panels, system readouts, dark/light UI toggle, tabbed views.
- **Failure Rules:** Step-by-step mathematical, scientific, or conceptual corrections.

### 17-19 & Youths & older (Group B Learning Areas Only)
- **Primary Mechanics:** High-stakes exam-aligned problem loops, multi-variable system optimization, case-study decision trees.
- **UX & Visuals:** High-density analytics dashboards, keyboard-first navigation shortcuts, clean professional aesthetic.
- **Failure Rules:** Comprehensive diagnostic breakdown identifying exact misapplied formulas, rules, or concepts.

### 9-19
- **Primary Mechanics:** Mixed multidisciplinary shuffle suitable across late primary through late secondary. Use Group A learning areas for primary-leaning rounds and Group B for secondary-leaning rounds only when age-appropriate; prefer topics that work across both. Do NOT use infant-only (audio-only / no-text) UX.
- **UX & Visuals:** Clean, readable UI that works for mixed ages; concise labels; no cartoon-only or adult-only aesthetic.
- **Failure Rules:** Guided diagnostic feedback plus optional hints; no harsh fail screens.

---

**QUESTION POOL, PROCEDURAL GENERATION & NON-REPEATING SHUFFLE RULES:**

1. **Minimum Question Bank**: The engine MUST contain a minimum bank of **10 distinct interactive quizzes/puzzles** tailored to the chosen HBC Learning Area.
2. **Non-Repeating Shuffle Engine**:
   - On game start (or restart), the engine must execute a Fisher-Yates shuffle on the question pool.
   - Questions/puzzles MUST NOT repeat within the same game session.
   - Every question must pull randomized numeric variables, context strings, or localized Zimbabwean examples (e.g., local rivers, national heritage sites, local crops, regional trade) from bounded ranges.
3. **Intrinsic Mechanics**: Game interactions must mirror the educational objective directly (e.g., placing geographical contours, balancing chemical equations, dragging grammatical parts of speech).
4. **Deferred feedback (no spoilers until final submit)**:
   - Choice click only **selects** an option; learner may change answers and navigate Previous/Next until final submit.
   - Do **not** show correct/incorrect styling or score until the learner clicks **Submit answers** (`#checkBtn`).
   - Progress pips show draft status; score box shows `Answered: X / N` until submit, then `Score: X / N`.
   - After final submit: reveal ok/bad per question, explanations, then call `gameScoreSubmit`.
5. Enable `#checkBtn` only after every round has a saved draft.

---

**CONTENT DECOUPLING (JAVASCRIPT OBJECT):**

Put ALL learning content, variable bounds, diagnostic strings, and question banks in a clearly marked JavaScript object at the top of the script:

const CONTENT = {
  learningArea: "...", // Must match HBC bracket
  topic: "...",
  ageRange: "...",
  totalRounds: 10,
  maxScore: 10,
  questionPool: [
    /* Minimum 10 unique parameterized item templates or micro-puzzles */
  ],
  hints: { /* common error mappings */ }
};

The game logic must dynamically pull from `CONTENT.questionPool`, shuffle without duplicates, and render items without hardcoding content into the UI layer.

---

**IMPORTANT - SCORE SUBMISSION CODE:**
At the end of the game's check/completion function, include:

    if (window.gameScoreSubmit) {
        window.gameScoreSubmit(finalScore, maxScore);
    } else if (window.parent && window.parent.submitGameScore) {
        const gameIdMatch = window.location.pathname.match(/\/play-game\/(\d+)/);
        if (gameIdMatch) {
            window.parent.submitGameScore(parseInt(gameIdMatch[1]), finalScore, maxScore);
        }
    }

**OUTPUT FORMAT:**
Provide the complete HTML code that can be copied and pasted directly into the game management system. Do not include explanations or markdown formatting outside the HTML block — output raw executable HTML code only.
```

---

## Example Prompts

### Example 1: Primary Level (Ages 11-12) — Science and Technology

```
Create a complete, standalone HTML educational game that can be embedded in a web application.

HOST / EMBED REQUIREMENTS:
1. Full HTML document; CSS in <style>; JS in <script>
2. Element id="scoreBox" displaying "Score: X / Y"
3. Button id="checkBtn" that submits via window.gameScoreSubmit(finalScore, maxScore)
4. No CDNs — vanilla JS/CSS only

AGE RANGE: 11-12
LEARNING AREA: Science and Technology (Zimbabwean HBC Group A)
DIFFICULTY LEVEL: medium
TOPIC: Renewable Energy Systems and Electrical Circuits
NUMBER OF QUESTIONS/ROUNDS: 10
MAXIMUM SCORE: 10

Apply 11-12 spec mechanics. Build a minimum pool of 10 interactive circuit and energy transformation puzzles inside CONTENT.questionPool. Implement a Fisher-Yates shuffle ensuring zero repeated questions during a session. Include score submission fallback on checkBtn.

Provide ONLY the raw HTML code.
```

### Example 2: Secondary Level (Ages 15-16) — Geography

```
Create a complete, standalone HTML educational game that can be embedded in a web application.

HOST / EMBED REQUIREMENTS:
1. Full HTML document; CSS in <style>; JS in <script>
2. Element id="scoreBox" displaying "Score: X / Y"
3. Button id="checkBtn" that submits via window.gameScoreSubmit(finalScore, maxScore)
4. No CDNs — vanilla JS/CSS only

AGE RANGE: 15-16
LEARNING AREA: Geography (Zimbabwean HBC Group B)
DIFFICULTY LEVEL: hard
TOPIC: Map Work, Scale Calculations, and Zimbabwean Landform Analysis
NUMBER OF QUESTIONS/ROUNDS: 10
MAXIMUM SCORE: 10

Apply 15-16 spec with interactive canvas/SVG map-reading sandboxes. Store 10 parameterized map scenarios (contour reading, gradient calculation, bearing) in CONTENT.questionPool. Ensure non-repeating dynamic shuffle across all 10 rounds with detailed post-attempt mathematical corrections. Include score submission fallback on checkBtn.

Provide ONLY the raw HTML code.
```

---

## Technical Validation Checklist for Shuffling & HBC Compliance

When reviewing generated games, ensure the JavaScript satisfies the non-repeating shuffle requirement:

**Fisher-Yates Shuffle Pattern in Generated Games:**
```javascript
function initializeGameSession(pool) {
    // Clone array to prevent mutating source data
    let shuffledPool = [...pool];
    for (let i = shuffledPool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffledPool[i], shuffledPool[j]] = [shuffledPool[j], shuffledPool[i]];
    }
    // Select exact round count without duplication
    return shuffledPool.slice(0, CONTENT.totalRounds);
}
```

**HBC compliance checks:**
- [ ] `CONTENT.learningArea` matches an allowed area for the selected age bracket (Group A vs Group B)
- [ ] `CONTENT.questionPool` has at least 10 distinct parameterized items
- [ ] Session start uses Fisher-Yates (or equivalent) and does not repeat questions within the session
- [ ] Randomized variables / Zimbabwean localized examples come from bounded ranges
- [ ] Post-attempt diagnostics include correct answer + distractor-specific feedback where applicable

---

## Key Points to Remember

1. **Always specify the score submission requirement** — required for `/play-game`
2. **Request id="scoreBox" and id="checkBtn"** — these IDs are what the host looks for
3. **AGE RANGE must be an existing platform value** — Infants, 9-10, 11-12, 13-14, 15-16, 17-19, 9-19, or Youths & older
4. **Learning area must match the HBC bracket** — Group A for 9-10 / 11-12; Group B for 13-14 / 15-16 / 17-19 / Youths & older
5. **Ask for complete HTML** — full document, not fragments
6. **No external dependencies**
7. **CONTENT.questionPool drives the game** — minimum 10 unique items; UI must not hardcode curriculum
8. **Fisher-Yates non-repeating shuffle** — no duplicate questions in a single session
9. **Intrinsic mechanics** — the interaction is the learning task
10. **Default 10 rounds / max score 10** — used for percentage calculations

---

## Testing Checklist

After generation, verify:
- [ ] Complete HTML structure (DOCTYPE, head, body)
- [ ] CSS in `<style>` tags (not external files)
- [ ] JavaScript in `<script>` tags (not external files)
- [ ] Element with id="scoreBox" exists and uses `Score: X / Y`
- [ ] Button with id="checkBtn" exists and stays disabled until all rounds finish
- [ ] `window.gameScoreSubmit()` is called on completion (with parent fallback)
- [ ] `const CONTENT = { ... }` exists with `learningArea`, `questionPool`, `totalRounds`, `maxScore`
- [ ] `CONTENT.questionPool.length >= 10`
- [ ] Learning area is allowed for the age bracket (Group A or Group B)
- [ ] Fisher-Yates (or equivalent) shuffle runs on start/restart with no in-session repeats
- [ ] Age-range mechanics and failure rules match the spec
- [ ] Game works when pasted into Game Management
- [ ] Score submission works on `/play-game`

---

## Troubleshooting

**If the game doesn't load:**
- Check that all CSS is in `<style>` tags
- Check that all JavaScript is in `<script>` tags
- Verify no external dependencies are required

**If score doesn't submit:**
- Verify id="checkBtn" exists
- Check that `window.gameScoreSubmit()` is called
- Ensure score is written to `#scoreBox` as `Score: X / Y` before submit

**If styling doesn't work:**
- Make sure all CSS is in the `<head>` section
- Scope selectors under a game root class to avoid parent-page conflicts

**If questions repeat within a session:**
- Confirm Fisher-Yates shuffles a clone of `CONTENT.questionPool` and slices to `CONTENT.totalRounds`
- Do not re-pick randomly from the full pool each round without removing used items
- Ensure the pool has at least as many unique items as `totalRounds`

**If learning area looks wrong for the age:**
- Primary (9-10, 11-12): English Language, Mathematics, Social Science, Science and Technology only
- Secondary / Youths: English Language, Mathematics, Geography, Combined Science, ICT only

---

## Best Practices for Game Creation

1. Use semantic HTML and ARIA labels
2. Keep curriculum in `CONTENT` so non-technical authors can edit `questionPool` and `hints`
3. Prefer exact arithmetic (avoid float drift; round display values, compare with a small epsilon only when needed)
4. Localize examples with Zimbabwean context where it strengthens HBC alignment
5. Test drag/drop and sliders on touch devices
6. Keep `#checkBtn` disabled until all rounds are finished
7. Do not reduce Infants scores on wrong taps
8. Name the Game Title in Game Management so it is clear which age range and learning area it targets

---

This template produces HBC-aligned educational games that paste cleanly into Game Events Management and follow the platform's existing age-range buckets.
