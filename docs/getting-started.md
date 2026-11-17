# Getting started

[← Manual](README.md)

![The main window](images/main-window.png)

## The main window

The window has three panels and a log:

| Part | What it is |
|---|---|
| **Objects** (left) | Everything you have open: two lists, **Material** (MIDI, scores, PDFs, recordings) above and **Exercises** below. The divider between them can be moved. |
| **Tabs** (centre) | Score views, exercises, routines, the practice diary… Each tab has its own buttons on top, under the tab name: changing tab changes the buttons. |
| **Tools** (right) | The options of the Generate / Convert tool chosen, with a **Run** button. It closes by itself when it is no longer needed (e.g. when an exercise opens) and reappears with the next tool. *View > Tools* shows or hides it. |
| **Log** (bottom) | What the app is doing, and why something did not start. **Hidden at start**: *View > Log* shows it. Everything is also written to `~/.musikite/log.txt`. |

With two or more tabs open, a last tab **Close all** closes them all (the objects stay).

The window never grows by itself: long scores scroll inside their tab.

### Menus

| Menu | Contents |
|---|---|
| **File** | Open… (MIDI, PDF, MusicXML, exercises .mke, routines .mkr, workspaces; several files at once), Save object as…, New / Open / Save workspace, Print… (Cmd+P) |
| **Edit** | Rename, Remove the selected objects |
| **View** | View / Play the selected object, Stop sound (Esc), show / hide panels |
| **Generate** | Make new material: [duets, canons, exercises to do, routines](generate.md) |
| **Convert** | Turn one object into another: [PDF → MIDI, fingerings, MIDI → score / PDF, merge, transpose](convert.md) |
| **Practice** | Start an exercise at once ([Read & play](read-and-play.md), [drills](drills.md), [ear training](ear-training.md), [Play over MIDI](play-over-midi.md), [Free player](free-player.md)) |
| **Analyse** | [Practice diary](diary.md) |
| **Settings** | [Settings…](settings.md) (Cmd+,) |
| **Help** | **Manual** (F1): this manual in a tab, with Back / Forward / Contents; About |

Right-clicking an object shows the same tools, limited to those that accept it.

## Users

The user is chosen in the toolbar at the top (**+** creates a new one). Every user is like
a separate installation: own [settings](settings.md), own results, own practice diary, own
workspace. A teacher can create one user per pupil. The window title shows
"MusiKitE – *user*".

Changing user saves the workspace of the previous one and loads the new user's last
workspace.

## Objects

Every object has a colour and a symbol:

| Symbol | Object | Colour |
|---|---|---|
| ♪ | MIDI | blue |
| ♫ | Score (notation) | teal |
| ▤ | PDF | red |
| ≈ | Recording (notes with intonation) | blue-grey |
| ♩ | Exercise to read / repeat (a phrase) | orange (Listen & repeat: green) |
| ▦ | Group of exercises (expand it with the arrow) | dark orange / purple |
| ◆ | Exercise made by the app (drill, quiz) | purple |
| ♬ | Play over MIDI | dark green |
| ↻ | Routine | dark blue |

Exercises show **today's best grade** of the current user (nothing if not done today).
Exercises **to do** (not done today) are in **bold on a grey background**; at 04:00 every
exercise becomes "to do" again.

More in [Objects and files](objects.md).

### Buttons of the Objects panel

| Button | What it does |
|---|---|
| **View** | Shows the object in a tab (a score, the pages of a PDF, an exercise). |
| **Play** | **Listens** to the object: its staff appears with the red cursor moving and the sound. It becomes **Stop** while playing. |
| **Save** | Saves to the file the object came from (the first time: Save as…). With several objects selected, all of them. |
| **Save as…** | Chooses where and in which format. With several objects selected: one folder for all. |

**Double-click** an exercise (or right-click > **Do it**) to practise it.

## Play and Start: listening versus practising

This difference runs through the whole app:

- **Play** = **listen**. Only in the Objects panel. You hear the music and see the cursor.
- **Start** = **practise**. Only inside exercises. You get one count-in bar and the
  metronome click; the cursor moves; **the music is not played** — you play it, and the app
  listens. (Listen & repeat first plays the phrase you must repeat: that is the question.)

Inside an exercise tab the buttons are typically **Start** (then Pause / Resume),
**Stop**, **Repeat** / **Again**, **Keep**, **Zoom +** / **Zoom −**, **Click**.

### The Click button

In every exercise with a staff (Read & play, Listen & repeat, the [drills](drills.md),
[Play over MIDI](play-over-midi.md)) and in the [Free player](free-player.md) the last
button of the bar is **Click**. It is two
things in one:

- a **visual metronome**: while a take runs it shows **Click 1**, **Click 2**, … (the beat
  of the bar, also in the count-in bar) and its colour changes at every click: the
  **first beat of the bar red**, then yellow, green, blue, and yellow again. In 3/4 it goes
  red–yellow–green; 6/8 is counted in eighths, as its clicks; when the time signature
  changes (scales with rhythm *varied*) the count follows it.
- the **switch of the audio click**: press it to switch the click **off** (the text is
  struck through; the colours and the count go on), press again to switch it on. It works
  also **during a take**. In Play over MIDI and in the Free player the **count-in bar is
  always heard**; "off" silences the clicks after it. Its first state comes from
  [Settings > Exercises > *Click*](settings.md#exercises); the drills and Play over MIDI
  remember it.

With the click off from the start, Read & play aligns the recording on the delay of the
audio device instead of the first click (as with headphones).

## The staff

- **Zoom + / Zoom −** in every score and exercise tab; the zoom is kept for the next
  exercise.
- **Click on a bar** (when nothing is playing) to move the cursor there and see the bar
  number.
- The cursor moves either **with the notes** or **bar line to bar line**: see
  [Settings > Exercises > Cursor](settings.md#exercises).
- Transposing instruments are always shown **as written** (a trumpet in B♭ part is
  written a tone above the sound).

## Workspaces

A workspace is everything in the Objects panel, saved in one file. The current workspace
is saved automatically when you quit or change user, and reopened at the next start.
*File > New workspace / Open workspace… / Save workspace as…* manage them by hand.

## Where to go next

- Practise at once: [Practice > Read & play](read-and-play.md) or any [drill](drills.md).
- Turn your band parts (PDF) into exercises: [Convert > PDF → MIDI](convert.md#pdf--midi),
  then [Generate > Exercises to do](generate.md#exercises-to-do).
- Build a daily plan: [Routines](routines.md).
