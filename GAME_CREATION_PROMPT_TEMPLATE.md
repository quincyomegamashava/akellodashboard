# ChatGPT Prompt Template for Creating HTML Games

Use this prompt template when asking ChatGPT to create HTML games that will work seamlessly with the game system.

---

## Prompt Template

```
Create a complete, standalone HTML game that can be embedded in a web application. The game must meet the following requirements:

**GAME REQUIREMENTS:**
1. **Complete HTML Structure**: Include a full HTML document with <!DOCTYPE html>, <head>, and <body> tags
2. **Self-contained**: All CSS must be in <style> tags in the <head> section, and all JavaScript must be in <script> tags (preferably before </body>)
3. **Score Tracking**: The game must track a score variable and display it in real-time
4. **Score Display Element**: Include an element with id="scoreBox" that displays the current score in the format: "Score: X / Y" where X is current score and Y is maximum possible score
5. **Completion Button**: Include a button with id="checkBtn" that, when clicked, shows the final score and triggers score submission
6. **Score Submission**: When the game is completed (checkBtn clicked), call window.gameScoreSubmit(finalScore, maxScore) to submit the score
7. **No External Dependencies**: Do not use external CDN links for libraries unless absolutely necessary. Use vanilla JavaScript and CSS
8. **Responsive Design**: Make it work on both desktop and mobile devices
9. **Clear Instructions**: Include clear instructions for the player on how to play
10. **Visual Feedback**: Provide visual feedback for correct/incorrect answers or actions

**GAME TYPE**: [Specify the type of game you want, e.g., "Math Quiz", "Word Puzzle", "Memory Game", "Drag and Drop Matching", etc.]

**DIFFICULTY LEVEL**: [Specify: Easy, Medium, or Hard]

**TOPIC/SUBJECT**: [Specify the educational topic or subject, e.g., "Mathematics - Multiplication", "English - Vocabulary", "Science - Planets", etc.]

**NUMBER OF QUESTIONS/ROUNDS**: [Specify how many questions or rounds the game should have]

**MAXIMUM SCORE**: [Specify the maximum possible score, e.g., 10, 20, 100]

**ADDITIONAL REQUIREMENTS**: [Add any specific features, mechanics, or styling preferences]

**IMPORTANT - SCORE SUBMISSION CODE:**
At the end of your game's check/completion function, include this code:
```javascript
// Submit score to backend
if (window.gameScoreSubmit) {
    window.gameScoreSubmit(finalScore, maxScore);
} else if (window.parent && window.parent.submitGameScore) {
    // Fallback for iframe context
    const gameIdMatch = window.location.pathname.match(/\/play-game\/(\d+)/);
    if (gameIdMatch) {
        window.parent.submitGameScore(parseInt(gameIdMatch[1]), finalScore, maxScore);
    }
}
```

**OUTPUT FORMAT:**
Provide the complete HTML code that I can copy and paste directly into the game management system. Do not include explanations or markdown formatting - just the raw HTML code.
```

---

## Example Prompts

### Example 1: Math Quiz Game
```
Create a complete, standalone HTML game that can be embedded in a web application. The game must meet the following requirements:

**GAME REQUIREMENTS:**
1. Complete HTML Structure with all CSS in <style> tags and JavaScript in <script> tags
2. Score tracking with an element id="scoreBox" displaying "Score: X / Y"
3. A button with id="checkBtn" that triggers score submission
4. Call window.gameScoreSubmit(finalScore, maxScore) when game completes
5. No external dependencies - vanilla JavaScript only
6. Responsive design for mobile and desktop
7. Clear instructions and visual feedback

**GAME TYPE**: Math Quiz - Multiple Choice

**DIFFICULTY LEVEL**: Medium

**TOPIC/SUBJECT**: Mathematics - Multiplication Tables

**NUMBER OF QUESTIONS/ROUNDS**: 10 questions

**MAXIMUM SCORE**: 10

**ADDITIONAL REQUIREMENTS**: 
- Show random multiplication problems (e.g., "7 × 8 = ?")
- 4 multiple choice options per question
- Green background for correct answers, red for incorrect
- Timer: 30 seconds per question
- Show final score with percentage

Include the score submission code at the end of the check function.
Provide only the raw HTML code.
```

### Example 2: Word Matching Game
```
Create a complete, standalone HTML game that can be embedded in a web application. The game must meet the following requirements:

**GAME REQUIREMENTS:**
1. Complete HTML Structure with all CSS in <style> tags and JavaScript in <script> tags
2. Score tracking with an element id="scoreBox" displaying "Score: X / Y"
3. A button with id="checkBtn" that triggers score submission
4. Call window.gameScoreSubmit(finalScore, maxScore) when game completes
5. No external dependencies - vanilla JavaScript only
6. Responsive design for mobile and desktop
7. Clear instructions and visual feedback

**GAME TYPE**: Drag and Drop Word Matching

**DIFFICULTY LEVEL**: Easy

**TOPIC/SUBJECT**: English - Synonyms

**NUMBER OF QUESTIONS/ROUNDS**: 5 word pairs

**MAXIMUM SCORE**: 5

**ADDITIONAL REQUIREMENTS**:
- Drag words from left column to match with synonyms in right column
- Visual feedback when correct (green) or wrong (red)
- Shuffle words on each game start
- Confetti animation when all correct

Include the score submission code at the end of the check function.
Provide only the raw HTML code.
```

---

## Key Points to Remember

1. **Always specify the score submission requirement** - This is critical for the game to work with the system
2. **Request id="scoreBox" and id="checkBtn"** - These are the standard IDs the system looks for
3. **Ask for complete HTML** - The game should be a full HTML document, not just fragments
4. **No external dependencies** - Keeps games lightweight and ensures they work offline
5. **Specify maximum score** - Important for percentage calculations
6. **Request responsive design** - Games should work on all devices

---

## Testing Checklist

After ChatGPT generates the game, verify:
- [ ] Complete HTML structure (DOCTYPE, head, body)
- [ ] CSS in <style> tags (not external files)
- [ ] JavaScript in <script> tags (not external files)
- [ ] Element with id="scoreBox" exists
- [ ] Button with id="checkBtn" exists
- [ ] Score is displayed in format "Score: X / Y"
- [ ] window.gameScoreSubmit() is called on completion
- [ ] Game works when pasted into the admin interface
- [ ] Score submission works correctly

---

## Troubleshooting

**If the game doesn't load:**
- Check that all CSS is in <style> tags
- Check that all JavaScript is in <script> tags
- Verify no external dependencies are required

**If score doesn't submit:**
- Verify id="checkBtn" exists
- Check that window.gameScoreSubmit() is called
- Ensure score variable is accessible in the check function

**If styling doesn't work:**
- Make sure all CSS is in the <head> section
- Check for CSS conflicts with parent page styles
- Use more specific selectors if needed

---

## Best Practices for Game Creation

1. **Use semantic HTML** - Makes games more accessible
2. **Add ARIA labels** - Improves accessibility
3. **Include game instructions** - Help players understand how to play
4. **Add visual feedback** - Makes games more engaging
5. **Test on mobile** - Ensure touch interactions work
6. **Keep it simple** - Complex games may have compatibility issues
7. **Use modern CSS** - But ensure browser compatibility
8. **Optimize performance** - Avoid heavy animations or computations

---

This template ensures that ChatGPT generates games that will work perfectly with your game management system!

