# Free player, recording and piano roll

[← Manual](README.md)

## Free player

*Practice > Free player (MIDI keyboard)* plays your MIDI keyboard with the soundfont.

| Control | Meaning |
|---|---|
| **Input** | Where the notes come from: a MIDI keyboard connected or the **computer keyboard** (default: Settings > Audio > MIDI input). Changing it connects the new one. |
| **Instrument** | A General MIDI instrument, or *From keyboard* (the keyboard's own channel and program changes; channel 10 = drums). |
| **All notes off** | Stops every sounding note. |
| **Reconnect** | Opens the keyboard again (after unplugging it). |

Sustain pedal, pitch bend and controllers are passed on. The keyboard is connected only
while the Free player tab is in front; the latency of the audio buffer is shown in the bar.

Time spent **really playing** counts as study time in the [practice diary](diary.md).

## Computer keyboard

Without a MIDI keyboard (or with *Settings > Audio > MIDI input* = **Computer keyboard**)
the letters of the computer play the notes, here and wherever the app accepts a MIDI
keyboard (Read & play, Listen & repeat, scales, chord arpeggios, rhythm reading, Test MIDI):

| Keys | Notes |
|---|---|
| `a w s e d f t g y h u j k o l p ò` (`;` on other layouts) | C C♯ D D♯ E F F♯ G G♯ A A♯ B C C♯ D D♯ E — an octave and a half, from C4 |
| `z` / `x` | octave down / up (shown at the bottom of the window) |
| `c` / `v` | softer / louder (velocity, 100 at the start) |

- The keys play only while the keyboard is in use (this tab in front, a take of an exercise,
  Test MIDI) and **not while a text or number field has the cursor** (bpm, names…): click on
  an empty part of the window first.
- A key held down plays one note (auto-repeat ignored); leaving the app releases every key.
- Laptop keyboards cannot always send three or four keys at once: chords may lose a note.
- The timing is a little less precise than a MIDI keyboard (the keys pass through the
  window, not through the MIDI driver): fine for the exercises, slightly looser when
  recording.

## Recording

The Free player records **takes**, each one a **part** with its own instrument:

1. Set **bpm** and **time signature**. A take always starts with one count-in bar of
   clicks; the **Click** button of the bar shows the beat of the bar in colour while you
   record and switches the clicks after the count-in off / on, also during the take (see
   [The Click button](getting-started.md#the-click-button)).
2. **Rec**: play; **Stop** ends the take.
3. The take appears in the **piano roll**, and **Quantize…** opens on it (Cancel keeps it
   as played).
4. The next take plays back the parts already recorded while you play (overdub).
5. **Save** makes a MIDI object "Recording *date time*" in Objects. **Clear** starts again.

Nothing is drawn during the take (drawing would disturb the timing); a bar / beat counter
runs instead. Tempo and time signature are those of the first take. If your recordings
come out late, set *Recording offset* in [Settings > Audio](settings.md#audio).

## Piano roll

The piano roll edits a recording or any MIDI (button **Piano roll** in the tab of a MIDI;
**Staff** goes back). Time runs left to right with the bar numbers; pitch bottom to top with
a keyboard on the left (click a key to hear it). One colour per track; the other tracks are
faded; louder notes are darker; selected notes are orange. Click a bar number: the next
Play begins at that bar after one count-in bar; double-click it: it plays from there at once
(see [Playing from a bar](objects.md#playing-from-a-bar)).

![Piano roll](images/piano-roll.png)

### Tools

| Tool | Use |
|---|---|
| **Hand** | Click = select (Shift adds), drag = move on the grid (Alt = free), drag the right edge = length, drag on empty space = rectangle selection, double-click on empty space = new note, on a note = delete. |
| **Pencil** | Click = a note one grid step long, drag = longer. |
| **Eraser** | Click or drag over notes. |
| **Grid** | Off, 1/4 … 1/32, triplets. |
| **Track** | The track you edit. |
| **Velocity** | Of new notes; changes the selected ones. |
| **Undo / Redo / Delete / Quantize… / Zoom** | |

### Keys and mouse

| Key | Action |
|---|---|
| Delete / Backspace | Delete the selection |
| Cmd+Z / Cmd+Shift+Z | Undo / Redo |
| Ctrl+A | Select all |
| ↑ ↓ | Semitone (Shift: octave) |
| ← → | One grid step |
| Ctrl+Q | Quantize… |
| Esc | Clear the selection |
| Wheel | Pitch; Shift + wheel: time; Cmd + wheel: zoom time; Alt + wheel: zoom pitch |

Notes you move or draw are heard with the instrument of the track.

### Quantize

| Option | Meaning |
|---|---|
| **Grid** | 1/4, 1/8, 1/8T, 1/8+1/8T, 1/16, 1/16T, 1/16+1/16T, 1/32 (T = triplet; "+" = the nearest point of either grid). |
| **Strength** | 0–100 %: below 100 % part of the played timing is kept. |
| **Note ends too** | Also the lengths (otherwise only the starts move). |
| **Scope** | Selected notes, the track, all tracks. |

The result is shown at once while you change the options; **OK** keeps it (Undo takes it
back), **Cancel** restores. Tip: on a mixed grid (1/8+1/8T) a light swing can come out half
triplets and half straight eighths; use a single grid or a strength below 100 %.

After quantising, *Convert > MIDI → Score* gives clean notation.
