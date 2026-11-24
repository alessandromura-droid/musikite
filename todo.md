# MusiKitE – to do

What is still to do. `CLAUDE.md` describes the software as it is now: a feature moves
there when it is done. Updated 2026-11-24.

## Fingerings (incremental; 4th valve, F trigger, double horn done 2026-11-24)

- Alternative fingerings (more than one per note, e.g. trumpet 3 for 12, trombone
  alternate positions), shown as an option.
- Compensating 4th valve (euphonium, tubas): today the combinations are not corrected.
- Second trigger of the bass trombone (Gb / D), real trigger positions (longer than the Bb
  ones: today the T number is only the order).
- Double horn: the switch point to the Bb side as a setting (today written G#4).

## Rework of recorded material (owner, 2026-11-24)

- `rework.py` (adapt, split, double, resample, quantize: port of MATLAB exercise.m) exists
  as Python modules: ADD THEM TO THE EDITOR (piano roll / Make a variant / a recording of the
  Free player: buttons or a menu), and decide how quantize (seconds -> quarters) relates to
  the piano roll's Quantize.

## Play-along graded / improvisation (done 2026-11-24, open points)

- Play-along: tempo changes of the MIDI are not followed in a graded take (one constant
  tempo); a graded take always starts from the first bar of the bars to play.
- Play-along: results kept in the diary only, not on the exercise (it stays "n/a").
- Headphones: the check is by the NAME of the output device (`realtime.output_is_speakers`);
  unknown names (an external loudspeaker on an interface) are not detected.
- Improvisation: grading = Chord arpeggios' rules; rhythm, phrasing and style not judged.

## Later: ear training and dictation (owner, 2026-11-24: "not clear how to implement")

- Progressions by ear (I-IV-V-I, ii-V-I…).
- Rhythmic dictation.
- Melodic dictation: a fragment of 4-8 notes, played back on the MIDI keyboard or written
  in the piano roll / on the staff; fragments from the owner's MIDI files or the duets.
- Two-voice dictation (the lower voice of a duet, or the intervals between the voices).
- Played intervals: a note is given, the user plays the interval asked.

## To review with the owner (later)

- Chord arpeggios: low piano voicing of the chords heard.
- Trumpet-specific rules, case by case (one voice, treble clef, difficulty of the high
  register).

## StaffView limits (later)

- One staff per part: a part on two staves (piano) is not matched.
- Pickup bars are not detected (also accompany.py and Play over MIDI bar numbers).

## Exercise library (later)

- Translation: the ease of the passages per instrument (trombone: slide positions far apart
  in fast notes; valve combinations), not only range and note length.
- Removing a melody from the user library (Add exists, Remove not yet).
- Crossings and generated melodies (today MAX_CROSSINGS = 0, N_GENERATED = 0).
- Build the library file: `python3 scripts/build_library.py <folder of the ~100 MIDI files>`
  (owner); then the folder exercises/trumpet is no longer used by the app.

## Generate (done 2026-11-24, open points)

- Brass trio / quartet: fixed ensembles; other ensembles (mixed brass chosen by the user,
  woodwinds) later. Trombone and horn lines are simple (roots / chord tones), no motifs.
- Melodies and etudes: the model learns from the library; with an empty library nothing
  can be made.

## Other

- `canon_trumpets.py` as a texture / mode of the duet generator.
- Cause of the "objects lost" report (2026-11-08) not confirmed.
- Screenshots of the manual (`docs/images/`).
- Android port (tablets only).
- Menus: family submenus exist in Practice / Generate; the right-click menu is still flat.
