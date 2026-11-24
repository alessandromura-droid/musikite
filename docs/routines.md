# Routines

[← Manual](README.md)

A routine ↻ is an ordered list of exercises: your practice plan for the day. Every exercise
of a routine goes to the [practice diary](diary.md) as usual.

![A routine](images/routine.png)

## Making a routine

- Select exercises in Objects (in the order you want) and choose **Generate > Make a
  routine** (or right-click). A group counts as its exercises.
- Or open an existing routine and **Add…** / drag exercises into it.

**One routine per instrument**: a routine for the trumpet, another for the piano. The
title proposed is "Routine *instrument*" (the instrument chosen beside the user).

The routine holds **copies**: the exercises in Objects are not changed, and the results of
the routine's items are their own.

### New each time

Exercises made by the app (drills, quizzes, random Read & play / Listen & repeat pieces)
can be **new each time**: once a day (only if not yet done that day) the item is made new
with the same settings — a new scale, new questions, a new random piece. Tick it in the
*New each time* column. A daily routine then changes every day by itself.

## The routine tab

Double-click the routine. The list shows for each exercise:

| Column | Meaning |
|---|---|
| **Today** | ✓ done today |
| **Grade** | today's best grade ("n/a" for ungraded exercises such as Play over MIDI) |
| **Exercise** | number and title |
| **New each time** | see above |

Buttons:

| Button | Meaning |
|---|---|
| **Start** | Starts the **selected** exercise. When the routine opens, the **first** exercise is selected, so Start begins from the start. |
| **Add…** | Inserts after the selected exercise: the exercises selected in Objects, exercise files (.mke, .mkr, .json), or a **new exercise** (long tones, scales, lip slurs, rhythm, intervals, interval reading, chord qualities, flash cards, *Read & play (random)*, *Listen & repeat (random)*) made with your last settings and marked *new each time*. |
| **Up / Down** | Move the selected exercise. |
| **Remove** | Remove it from the routine. |
| **Auto-advance** | After an attempt on the current exercise, the next exercise **to do** opens by itself after a pause (10 s by default: [Settings > Exercises > Routine: next exercise after](settings.md#exercises)). It does not interrupt an exercise you have started again in the meantime. |

**Drag and drop**: drag exercises from the Objects panel (Exercises list) or exercise files
from the Finder onto the list — they are inserted where you drop them. Drag the items of the
list to reorder them. Holding a drag over the routine's tab brings it to the front.

## Doing a routine

Each exercise opens in **its own tab** and starts at once. The tab is named after the
**routine** and the position, not after the exercise (e.g. "↻ Routine trumpet – 3/7"; a
group of exercises: "▦ <group> – 3/5"), so you always see that you are inside a routine.
In the bar of that tab two extra
buttons appear:

| Button | Meaning |
|---|---|
| **◀** | The exercise before, in the routine |
| **▶** | The exercise after |

They work only while the exercise is **stopped** (they are disabled during it). The tab of
the previous exercise closes when the next one opens.

When everything has been done today, the routine says so and shows the **mean grade** of
the day.

## Files

A routine is saved as `.mkr` (Save as…), and is part of the workspace. *File > Open…* reads
it back.
