# Voice input — manual test checklist

The `useSpeech` unit tests cover the state machine against a fake recognition
engine. They cannot cover the browser's actual speech engine, microphone
permissions, or how well it hears airport codes. Run this list by hand before
each release, in **Chrome, Safari, and Firefox**.

| # | Steps | Expected |
|---|---|---|
| 1 | Load the app in Chrome, click the mic | Permission prompt appears (first time only); button turns red and pulses |
| 2 | Say "is Boston congested" | Words stream into the input box as you speak |
| 3 | Stop talking | Button returns to idle; text stays in the box; **nothing is sent** |
| 4 | Press Send | Normal answer with a congestion chart |
| 5 | Click the mic, then click it again mid-sentence | Listening stops immediately; partial text remains, editable |
| 6 | Say "how busy is P W M" | Check what lands in the box — codes are the weak spot; you can fix it before sending |
| 7 | Deny microphone permission (or block it in site settings), click the mic | Red hint: "Microphone blocked — check your browser settings."; typing still works |
| 8 | Load in Safari, click the mic | Same behavior as Chrome |
| 9 | Load in **Firefox** | Mic button is **absent**; the composer and typing work normally |
| 10 | Click mic, then send a typed question while listening | No crash; the mic stops cleanly |
| 11 | Enable "reduce motion" in the OS, start dictation | Button turns red but does not pulse |

## Known limitations (by design)

- Firefox has no Web Speech API. The button is hidden rather than broken.
- Chrome sends audio to Google's servers for recognition; Safari uses Apple's.
  No audio ever reaches *our* server, but the browser's engine is not offline.
- Airport codes are frequently mis-transcribed. This is exactly why dictation
  never auto-sends.
