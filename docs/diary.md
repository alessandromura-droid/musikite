# Practice diary

[← Manual](README.md)

*Analyse > Practice diary* shows your practice day by day, for the current user.

![Practice diary](images/diary.png)

## The rules

- **The day runs from 04:00 to 04:00**: a session across midnight is one day.
- An exercise can be repeated during the day: its **grade of the day is the best attempt**.
  Every attempt is still kept (see *Candles*), and its time always counts.
- At the end of the day the day is **frozen**: grades, means and minutes are never
  recomputed, so a future change of the grading rules does not rewrite your past.
- **Study time counts only exercises**:
  - Read & play, Listen & repeat, drills: twice the length of every take (you also read
    and prepare);
  - blocks of questions: the time spent answering, at most 15 s per question;
  - Free player: twice the time you really played (each note keeps it "active" for 1 s);
  - listening with Play, or the app left open: nothing.

## Charts

| Chart | What it shows |
|---|---|
| **Calendar** | One cell per day, weeks in columns (Monday on top), the last 53 weeks. *Colour*: time studied, mean grade, or the mean grade of one exercise type. Today is outlined. The current and the longest **streak** (days in a row) are in the bar. |
| **Candles** | Like a stock chart, per day: *open* = first attempt, *close* = last, *high* = best, *low* = worst; green if the day closed higher than it opened. The dot is the mean grade of the day; a dashed line marks 6 (*fair*). |
| **Trend** | Mean grade of every day, the min–max band and the 7-day moving mean. |
| **Weekly time** | Minutes per week, stacked by exercise type. |

**Instrument**: all instruments, or one of yours (every attempt records the instrument
chosen beside the user; attempts made before this existed are shown only with *All
instruments*). **Exercise**: all types, or one (Candles, Trend). **Click a day** to see its summary on the
right: exercises done, grades, attempts, minutes. Tooltips give the values. **Refresh**
re-reads the data, **Today** jumps to today.

## Where it is stored

`~/.musikite/users/<user>/diary.json`.
