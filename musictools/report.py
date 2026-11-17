"""
ScoreReport: a score that shows what was expected and what was played (no Qt).

Two staves: the exercise, every note coloured (green right, red wrong), and
below it the notes actually played (transcribed from the microphone or taken
from the MIDI keyboard). Used at the end of every take of Read & play and
Listen & repeat; stored as plain data (to_dict) in the exercise detail.

    r = ScoreReport(phrase, played, correct_rows, title='...', info={...})
    score, colors = r.to_score()      # Score with 2 parts; {table row: colour}
"""
RIGHT, WRONG, PLAYED = "#2e7d32", "#d32f2f", "#1565c0"


class ScoreReport:
    def __init__(self, phrase, played, correct_rows, title="", info=None):
        """phrase: phrase.Phrase or its dict; played: [[start_q, dur_q, concert pitch]];
        correct_rows: {row of the exercise table: True/False}."""
        from .phrase import Phrase
        self.phrase = phrase if isinstance(phrase, Phrase) else Phrase.from_dict(phrase)
        self.played = [[float(s), float(d), int(p)] for s, d, p in played]
        self.correct_rows = {int(k): bool(v) for k, v in dict(correct_rows).items()}
        self.title = title or self.phrase.title
        self.info = dict(info or {})

    def __repr__(self):
        ok = sum(self.correct_rows.values())
        return f"ScoreReport('{self.title}', {ok}/{len(self.correct_rows)} right, " \
               f"{len(self.played)} notes played)"

    def to_dict(self):
        return dict(phrase=self.phrase.to_dict(), played=self.played,
                    correct_rows={str(k): v for k, v in self.correct_rows.items()},
                    title=self.title, info=self.info)

    @classmethod
    def from_dict(cls, d):
        return cls(d["phrase"], d["played"], d["correct_rows"], d.get("title", ""), d.get("info"))

    def to_midi(self):
        """Midi with two tracks: 'Exercise' and 'Played' (concert pitch)."""
        import pretty_midi
        m = self.phrase.to_midi()
        m.pm.instruments[0].name = "Exercise"
        spq = 60.0 / self.phrase.bpm
        ins = pretty_midi.Instrument(program=self.phrase.program, name="Played")
        L = self.phrase.length_q
        grid = 0.25                                        # sixteenths: no odd tuplets
        notes = []
        for s, d, p in sorted(self.played):
            s = round(s / grid) * grid
            d = max(grid, round(d / grid) * grid)
            if s >= L:
                continue
            if notes and notes[-1][0] + notes[-1][1] > s:   # one voice: cut the previous note
                notes[-1][1] = s - notes[-1][0]
                if notes[-1][1] <= 0:
                    notes.pop()
            notes.append([s, min(d, L - s), p])
        for s, d, p in notes:
            ins.notes.append(pretty_midi.Note(70, p, s * spq, (s + d) * spq))
        if ins.notes:                                      # nothing played: no second staff
            m.pm.instruments.append(ins)
        return m

    def to_score(self):
        """(Score, {row: colour}): exercise notes green/red, played notes blue."""
        from .score import Score
        s = Score.from_midi(self.to_midi(), title=self.title)
        colors = {}
        rows = 0
        for ip in range(len(s.m21.parts)):
            t = s.table(part=ip)
            for k, r in enumerate(t.itertuples()):
                if r.pitch is None or str(r.pitch) == "<NA>":
                    continue
                if ip == 0:
                    ok = self.correct_rows.get(k)
                    if ok is None:                         # tied continuation: as the note before
                        prev = [v for kk, v in self.correct_rows.items() if kk < k]
                        ok = prev[-1] if prev else True
                    colors[rows + k] = RIGHT if ok else WRONG
                else:
                    colors[rows + k] = PLAYED
            rows += len(t)
        return s, colors
