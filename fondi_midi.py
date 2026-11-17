#!/usr/bin/env python3

import sys
from pathlib import Path
import pretty_midi


def main():
    if len(sys.argv) < 3:
        print("Uso: fondi_midi.py input1.mid input2.mid ... output.mid")
        sys.exit(1)

    *input_files, output_file = sys.argv[1:]

    risultato = pretty_midi.PrettyMIDI()

    for file in input_files:
        print(f"Analizzo: {file}")
        midi = pretty_midi.PrettyMIDI(file)
        risultato.instruments.extend(midi.instruments)

    risultato.write(output_file)
    print(f"Creato: {output_file}")


if __name__ == "__main__":
    main()