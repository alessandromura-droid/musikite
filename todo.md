# MusiKitE – to do

What is still to do. `CLAUDE.md` describes the software as it is now: a feature moves
there when it is done. Updated 2026-11-25.

## Fingerings (incremental; 4th valve, F trigger, double horn done 2026-11-24)

- Alternative fingerings (more than one per note, e.g. trumpet 3 for 12, trombone
  alternate positions), shown as an option.
- Compensating 4th valve (euphonium, tubas): today the combinations are not corrected.
- Second trigger of the bass trombone (Gb / D), real trigger positions (longer than the Bb
  ones: today the T number is only the order).
- Double horn: the switch point to the Bb side as a setting (today written G#4).

## Rework of recorded material (owner, 2026-11-24; editor done 2026-11-25)

- The editor tools (Bars…, Double…, Resample…, Quantize from playing) are NOT in the piano
  roll of the Free player (its recorder keeps its own tempo / metre): to decide.

## Editing a PDF (owner, 2026-11-25: to do, in this order of cost)

A PDF has no notes, only drawings and text at a position. An edited PDF is a NEW object:
the original is never touched (as the fingerings).
- LOW COST
  * Page operations: rotate, delete, reorder, merge several PDFs, crop margins
    (PyMuPDF; only the interface). Useful for band parts.
  * Title of the PDFs made by the app (from Midi / Score): engrave again with the new title
    (the title is already a parameter).
  * Text added on any PDF (title, "Trumpet 2", a note) as the fingerings: text on a white
    box (works on Android too).
- MEDIUM COST
  * Preview of the fingerings before saving: the existing options (size, gap, colour, no
    repetitions) seen at once on the page, saved only at the end (scoreread run on a
    temporary file at every change; scoreread not changed in depth).
  * Change a text already in an external PDF: redaction of the old text + new text. Trap:
    embedded fonts are subsets (only the characters used), the new text comes out in
    another font: it works, but it shows.
- MEDIUM-HIGH COST
  * Move / delete a single fingering (also corrects wrong readings): scoreread must return
    the list of the fingerings (page, position, text) instead of writing the PDF directly;
    a page view to drag / delete them; then the PDF written. Changes scoreread (only on the
    owner's request); the output with --midi must stay identical. Touch drag on Android.
- TRAP: added text may disturb scoreread when that PDF is read back to MIDI (with the
  fingerings on a white box it does not happen today): to check for free text.

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
- DUPLICATION (owner, 2026-11-24): "Read & play – generate random" (a piece of one voice of
  a new duet) and "Melodies and etudes" make similar exercises, confusing for the user.
  Both kept for now; when one works better the other is dropped, or they are merged into
  ONE generation engine (melodies.py already offers the duet voice as an engine).
- Melody / duet engines (melodygen.py, duetcp.py, 2026-11-24): tune the weights by
  listening; pickups, modulation, longer forms (ABA with a contrasting middle) not done.

## Other

- `canon_trumpets.py` as a texture / mode of the duet generator.
- Cause of the "objects lost" report (2026-11-08) not confirmed.
- Screenshots of the manual (`docs/images/`).
- Android port (tablets only).
- Menus: the family submenus were removed (2026-11-24: tools greyed by instrument); the
  right-click menu is flat.
