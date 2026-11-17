import random
from music21 import stream, note, meter, key, instrument

# Dizionario degli accordi (in Do Maggiore) e note ideali per il registro della tromba
CHORD_DATA = {
    'C': {
        't1': ['C5', 'E5', 'G4', 'E4'], # Note accordo Do maggiore per voce acuta
        't2': ['G4', 'E4', 'C4', 'G3'], # Note accordo Do maggiore per voce grave
        'scala': ['C', 'D', 'E', 'F', 'G', 'A', 'B']
    },
    'F': {
        't1': ['F4', 'A4', 'C5', 'F5'],
        't2': ['A3', 'C4', 'F4', 'A4'],
        'scala': ['F', 'G', 'A', 'B', 'C', 'D', 'E']
    },
    'G': {
        't1': ['G4', 'B4', 'D5', 'G5'],
        't2': ['B3', 'D4', 'G4', 'B4'],
        'scala': ['G', 'A', 'B', 'C', 'D', 'E', 'F']
    },
    'Am': {
        't1': ['A4', 'C5', 'E5', 'A4'],
        't2': ['C4', 'E4', 'A3', 'C4'],
        'scala': ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    }
}

# Progressione classica in 8 battute (Domanda alla battuta 4, Risposta conclusiva alla battuta 8)
PROGRESSIONE_BASE = ['C', 'F', 'G', 'G', 'C', 'F', 'G', 'C']

def ottieni_terza_sotto(nota_str):
    """Calcola la terza diatonica inferiore per armonizzare all'italiana/classica."""
    nomi = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
    nome = nota_str[0]
    ottava = int(nota_str[1])
    idx = nomi.index(nome)
    
    # Due gradi sotto nella scala
    nuovo_idx = (idx - 2) % 7
    nuova_ottava = ottava if idx >= 2 else ottava - 1
    return f"{nomi[nuovo_idx]}{nuova_ottava}"

def genera_battuta(accordo, tipo_battuta, complessita):
    """
    Genera 4 quarti di musica coerente con l'accordo del momento.
    tipo_battuta: 'normale', 'semicadenza' (battuta 4), 'cadenza_finale' (battuta 8/16)
    """
    note_t1 = []
    note_t2 = []

    # Cadenza finale: accordo tenuto di risoluzione su Do
    if tipo_battuta == 'cadenza_finale':
        note_t1.append(note.Note('C5', quarterLength=4.0))
        note_t2.append(note.Note('C4', quarterLength=4.0))
        return note_t1, note_t2

    # Semicadenza (pausa / respiro sul Sol alla fine della prima frase)
    if tipo_battuta == 'semicadenza':
        note_t1.append(note.Note('D5', quarterLength=2.0))
        note_t1.append(note.Note('B4', quarterLength=2.0))
        note_t2.append(note.Note('B4', quarterLength=2.0))
        note_t2.append(note.Note('G4', quarterLength=2.0))
        return note_t1, note_t2

    # Generazione in base alla complessità
    chord_tones = CHORD_DATA[accordo]['t1']

    if complessita == 1:
        # Livello 1: Omoritmico, valori larghi (minime e semiminime), puro canto a due voci
        pattern = random.choice(['2_minime', '4_semiminime', 'minima_2semi'])
        
        if pattern == '2_minime':
            n1 = random.choice(chord_tones)
            n2 = random.choice([n for n in chord_tones if n != n1])
            for n in [n1, n2]:
                note_t1.append(note.Note(n, quarterLength=2.0))
                note_t2.append(note.Note(ottieni_terza_sotto(n), quarterLength=2.0))
                
        elif pattern == '4_semiminime':
            n_start = random.choice(chord_tones)
            for _ in range(4):
                note_t1.append(note.Note(n_start, quarterLength=1.0))
                note_t2.append(note.Note(ottieni_terza_sotto(n_start), quarterLength=1.0))
                n_start = random.choice(chord_tones)
                
        else:
            n1 = random.choice(chord_tones)
            note_t1.append(note.Note(n1, quarterLength=2.0))
            note_t2.append(note.Note(ottieni_terza_sotto(n1), quarterLength=2.0))
            for _ in range(2):
                nx = random.choice(chord_tones)
                note_t1.append(note.Note(nx, quarterLength=1.0))
                note_t2.append(note.Note(ottieni_terza_sotto(nx), quarterLength=1.0))

    elif complessita == 2:
        # Livello 2: Melodia con arpeggi e crome di passaggio
        for _ in range(2):  # 2 metà da 2 quarti ciascuna
            n_base = random.choice(chord_tones)
            # Tromba 1 fa crome (disegno melodico), Tromba 2 tiene la nota dell'accordo
            note_t1.append(note.Note(n_base, quarterLength=0.5))
            note_t1.append(note.Note(ottieni_terza_sotto(n_base), quarterLength=0.5))
            note_t1.append(note.Note(n_base, quarterLength=1.0))
            
            note_t2.append(note.Note(ottieni_terza_sotto(n_base), quarterLength=2.0))

    else:
        # Livello 3: Contrappunto a domanda/risposta e ritmi sincopati/puntati
        for _ in range(2):
            n1 = random.choice(chord_tones)
            n2 = random.choice([n for n in chord_tones if n != n1])
            # T1 ritmo puntato, T2 risponde
            note_t1.append(note.Note(n1, quarterLength=1.5))
            note_t1.append(note.Note(n2, quarterLength=0.5))
            
            note_t2.append(note.Note(ottieni_terza_sotto(n1), quarterLength=1.0))
            note_t2.append(note.Note(ottieni_terza_sotto(n2), quarterLength=1.0))

    return note_t1, note_t2

def genera_duetto_musicale(complessita=1, ripetizioni_giro=2, nome_file="duetto_melodico.mid"):
    score = stream.Score()

    t1 = stream.Part(id='Tromba 1')
    t1.insert(0, instrument.Trumpet())
    t1.insert(0, meter.TimeSignature('4/4'))
    t1.insert(0, key.Key('C'))

    t2 = stream.Part(id='Tromba 2')
    t2.insert(0, instrument.Trumpet())
    t2.insert(0, meter.TimeSignature('4/4'))
    t2.insert(0, key.Key('C'))

    # Crea la sequenza di battute (8 battute * ripetizioni)
    progressione = PROGRESSIONE_BASE * ripetizioni_giro
    totale_battute = len(progressione)

    for i, accordo in enumerate(progressione):
        num_battuta = i + 1
        misura_t1 = stream.Measure(number=num_battuta)
        misura_t2 = stream.Measure(number=num_battuta)

        # Riconoscimento delle cadenze formali (battute 4, 8, 12, 16...)
        if num_battuta == totale_battute:
            tipo = 'cadenza_finale'
        elif num_battuta % 4 == 0:
            tipo = 'semicadenza'
        else:
            tipo = 'normale'

        n_t1, n_t2 = genera_battuta(accordo, tipo, complessita)

        for n in n_t1:
            misura_t1.append(n)
        for n in n_t2:
            misura_t2.append(n)

        t1.append(misura_t1)
        t2.append(misura_t2)

    score.insert(0, t1)
    score.insert(0, t2)

    score.write('midi', fp=nome_file)
    print(f"\n[OK] Duetto armonico generato: '{nome_file}' ({totale_battute} battute, Livello {complessita})")

if __name__ == "__main__":
    print("--- GENERATORE DUETTI ARMONICI PER TROMBA ---")
    liv = int(input("Complessità (1 = Melodico/Cantabile, 2 = Crome/Arpeggi, 3 = Mosso/Contrappuntistico): ").strip() or "1")
    giri = int(input("Quanti giri da 8 battute vuoi generare? (default 2 = 16 battute): ").strip() or "2")
    file_out = input("Nome file (default 'duetto_melodico.mid'): ").strip() or "duetto_melodico.mid"

    genera_duetto_musicale(complessita=liv, ripetizioni_giro=giri, nome_file=file_out)