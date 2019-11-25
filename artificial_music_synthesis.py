# -*- coding: utf-8 -*-
"""Artificial Music Synthesis.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/12rq8gTBj6wKIolDo8Hyh3kzo61nA8t3h
"""

# Commented out IPython magic to ensure Python compatibility.
import numpy as np
import os
from google.colab import drive
from IPython import *
from keras.models import *
from keras.initializers import *
from keras.utils import *
from keras.layers import *
from keras.optimizers import *
from music21 import *
from itertools import zip_longest
import random
# %tensorflow_version 1.x

display.Audio('30s_trained_model.mp3')

def __parse_midi(data_fn):
    # Parse the MIDI data for separate melody and accompaniment parts.
    midi_data = converter.parse(data_fn)
    # Get melody part, compress into single voice.
    melody_stream = midi_data[5]     # For Metheny piece, Melody is Part #5.
    melody1, melody2 = melody_stream.getElementsByClass(stream.Voice)
    for j in melody2:
        melody1.insert(j.offset, j)
    melody_voice = melody1

    for i in melody_voice:
        if i.quarterLength == 0.0:
            i.quarterLength = 0.25

    # Change key signature to adhere to comp_stream (1 sharp, mode = major).
    # Also add Electric Guitar. 
    melody_voice.insert(0, instrument.ElectricGuitar())
    melody_voice.insert(0, key.KeySignature(sharps=1))

    # The accompaniment parts. Take only the best subset of parts from
    # the original data. Maybe add more parts, hand-add valid instruments.
    # Should add least add a string part (for sparse solos).
    # Verified are good parts: 0, 1, 6, 7 '''
    partIndices = [0, 1, 6, 7]
    comp_stream = stream.Voice()
    comp_stream.append([j.flat for i, j in enumerate(midi_data) 
        if i in partIndices])

    # Full stream containing both the melody and the accompaniment. 
    # All parts are flattened. 
    full_stream = stream.Voice()
    for i in range(len(comp_stream)):
        full_stream.append(comp_stream[i])
    full_stream.append(melody_voice)

    # Extract solo stream, assuming you know the positions ..ByOffset(i, j).
    # Note that for different instruments (with stream.flat), you NEED to use
    # stream.Part(), not stream.Voice().
    # Accompanied solo is in range [478, 548)
    solo_stream = stream.Voice()
    for part in full_stream:
        curr_part = stream.Part()
        curr_part.append(part.getElementsByClass(instrument.Instrument))
        curr_part.append(part.getElementsByClass(tempo.MetronomeMark))
        curr_part.append(part.getElementsByClass(key.KeySignature))
        curr_part.append(part.getElementsByClass(meter.TimeSignature))
        curr_part.append(part.getElementsByOffset(476, 548, 
                                                  includeEndBoundary=True))
        cp = curr_part.flat
        solo_stream.insert(cp)

    # Group by measure so you can classify. 
    # Note that measure 0 is for the time signature, metronome, etc. which have
    # an offset of 0.0.
    melody_stream = solo_stream[-1]
    measures = OrderedDict()
    offsetTuples = [(int(n.offset / 4), n) for n in melody_stream]
    measureNum = 0 # for now, don't use real m. nums (119, 120)
    for key_x, group in groupby(offsetTuples, lambda x: x[0]):
        measures[measureNum] = [n[1] for n in group]
        measureNum += 1

    # Get the stream of chords.
    # offsetTuples_chords: group chords by measure number.
    chordStream = solo_stream[0]
    chordStream.removeByClass(note.Rest)
    chordStream.removeByClass(note.Note)
    offsetTuples_chords = [(int(n.offset / 4), n) for n in chordStream]

    # Generate the chord structure. Use just track 1 (piano) since it is
    # the only instrument that has chords. 
    # Group into 4s, just like before. 
    chords = OrderedDict()
    measureNum = 0
    for key_x, group in groupby(offsetTuples_chords, lambda x: x[0]):
        chords[measureNum] = [n[1] for n in group]
        measureNum += 1

    # Fix for the below problem.
    #   1) Find out why len(measures) != len(chords).
    #   ANSWER: resolves at end but melody ends 1/16 before last measure so doesn't
    #           actually show up, while the accompaniment's beat 1 right after does.
    #           Actually on second thought: melody/comp start on Ab, and resolve to
    #           the same key (Ab) so could actually just cut out last measure to loop.
    #           Decided: just cut out the last measure. 
    del chords[len(chords) - 1]
    assert len(chords) == len(measures)

    return measures, chords

def __get_abstract_grammars(measures, chords):
    # extract grammars
    abstract_grammars = []
    for ix in range(1, len(measures)):
        m = stream.Voice()
        for i in measures[ix]:
            m.insert(i.offset, i)
        c = stream.Voice()
        for j in chords[ix]:
            c.insert(j.offset, j)
        parsed = parse_melody(m, c)
        abstract_grammars.append(parsed)

    return abstract_grammars

def get_musical_data(data_fn):
    
    measures, chords = __parse_midi(data_fn)
    abstract_grammars = __get_abstract_grammars(measures, chords)

    return chords, abstract_grammars

def get_corpus_data(abstract_grammars):
    corpus = [x for sublist in abstract_grammars for x in sublist.split(' ')]
    values = set(corpus)
    val_indices = dict((v, i) for i, v in enumerate(values))
    indices_val = dict((i, v) for i, v in enumerate(values))

    return corpus, values, val_indices, indices_val

def data_processing(corpus, values_indices, m = 60, Tx = 30):
    # cut the corpus into semi-redundant sequences of Tx values
    Tx = Tx 
    N_values = len(set(corpus))
    np.random.seed(0)
    X = np.zeros((m, Tx, N_values), dtype=np.bool)
    Y = np.zeros((m, Tx, N_values), dtype=np.bool)
    for i in range(m):
#         for t in range(1, Tx):
        random_idx = np.random.choice(len(corpus) - Tx)
        corp_data = corpus[random_idx:(random_idx + Tx)]
        for j in range(Tx):
            idx = values_indices[corp_data[j]]
            if j != 0:
                X[i, j, idx] = 1
                Y[i, j-1, idx] = 1
    
    Y = np.swapaxes(Y,0,1)
    Y = Y.tolist()
    return np.asarray(X), np.asarray(Y), N_values

def Load_Data():
    chords, abstract_grammars = get_musical_data('original_metheny.mid')
    corpus, notes, notes_indices, indices_notes = get_corpus_data(abstract_grammars)
    notes = len(set(corpus))
    X_train, Y_train, notes = data_processing(corpus, notes_indices, 60, 30)   
    return (X_train, Y_train, notes, indices_notes)

reshapor = Reshape((1,78))
LSTM_Cell = LSTM(64,return_state = True)
dense = Dense(78,activation='softmax')

X_train, Y_train, notes, indices_notes = Load_Data()

print('shape of X:', X_train.shape)
print('number of training examples:', X_train.shape[0])
print('Tx (length of sequence):', X_train.shape[1])
print('total # of unique values:', notes)
print('Shape of Y:', Y_train.shape)

def one_hot(x):
    x = K.argmax(x)
    x = tf.one_hot(x, 78) 
    x = RepeatVector(1)(x)
    return x

reshapor = Reshape((1,78))
LSTM_cell = LSTM(64,return_state=True)
Densor = Dense(78,activation="softmax")

def Propagation(input_shape,tx):

  X_input = Input(shape = input_shape)
  X = X_input
  a0 = Input(shape=(64,),name="a0")
  c0 = Input(shape=(64,),name="c0")
  a = a0
  c = c0

  outputs = []
  for t in range(tx):
    x = Lambda(lambda x: X[:,t,:])(X)
    x = reshapor(x)
    a,_,c = LSTM_cell(x,initial_state=[a,c])
    output = Densor(a)
    outputs.append(output)
  
  model = Model([X_input,a0,c0],outputs)
  return model

def Caller_Function():

  X_train, Y_train, notes, indices_notes = Load_Data()
  num_epochs = 1000
  mini_batch_size = 10
  shape = X_train.shape
  input_shape = (shape[1],shape[2])
  tx = shape[1]
  m = shape[0]
  a0 = np.zeros((m, 64))
  c0 = np.zeros((m, 64))

  model = Propagation(input_shape,tx)
  opt = Adam(lr=0.01, beta_1=0.9, beta_2=0.999, decay=0.01)
  model.compile(loss='categorical_crossentropy',optimizer=opt,metrics=['accuracy'])
  model.fit([X_train,a0,c0],list(Y_train),epochs=num_epochs)
  #model.summary()

Caller_Function()

def Music_Generation_Helper(notes):

  X_input = Input((1,notes))
  a0 = Input((64,),name="a0")
  c0 = Input((64,),name="c0")
  a = a0
  c = c0
  X = X_input 

  outputs = []
  for t in range(20):

    a,_,c = LSTM_Cell(X,initial_state = [a,c])
    output = Densor(a)
    outputs.append(output)
    X = Lambda(one_hot)(output)

  model = Model([X_input,a0,c0],outputs)

  return model

def predict_and_sample(inference_model):

  x = np.zeros((1,1,78))
  a0 = np.zeros((1,64))
  c0 = np.zeros((1,64))

  output = inference_model.predict([x,a0,c0])
  indices = np.argmax(output,2)
  result = to_categorical(indices)

  return result, indices

def __roundDown(num, mult):
    return (float(num) - (float(num) % mult))

def __roundUp(num, mult):
    return __roundDown(num, mult) + mult

def __roundUpDown(num, mult, upDown):
    if upDown < 0:
        return __roundDown(num, mult)
    else:
        return __roundUp(num, mult)

def __is_scale_tone(chord, note):
    # Method: generate all scales that have the chord notes th check if note is
    # in names

    # Derive major or minor scales (minor if 'other') based on the quality
    # of the chord.
    scaleType = scale.DorianScale() # i.e. minor pentatonic
    if chord.quality == 'major':
        scaleType = scale.MajorScale()
    # Can change later to deriveAll() for flexibility. If so then use list
    # comprehension of form [x for a in b for x in a].
    scales = scaleType.derive(chord) # use deriveAll() later for flexibility
    allPitches = list(set([pitch for pitch in scales.getPitches()]))
    allNoteNames = [i.name for i in allPitches] # octaves don't matter

    # Get note name. Return true if in the list of note names.
    noteName = note.name
    return (noteName in allNoteNames)

def __is_approach_tone(chord, note):
    # Method: see if note is +/- 1 a chord tone.

    for chordPitch in chord.pitches:
        stepUp = chordPitch.transpose(1)
        stepDown = chordPitch.transpose(-1)
        if (note.name == stepDown.name or 
            note.name == stepDown.getEnharmonic().name or
            note.name == stepUp.name or
            note.name == stepUp.getEnharmonic().name):
                return True
    return False

def __is_chord_tone(lastChord, note):
    return (note.name in (p.name for p in lastChord.pitches))

def __generate_chord_tone(lastChord):
    lastChordNoteNames = [p.nameWithOctave for p in lastChord.pitches]
    return note.Note(random.choice(lastChordNoteNames))

def __generate_scale_tone(lastChord):
    # Derive major or minor scales (minor if 'other') based on the quality
    # of the lastChord.
    scaleType = scale.WeightedHexatonicBlues() # minor pentatonic
    if lastChord.quality == 'major':
        scaleType = scale.MajorScale()
   
    scales = scaleType.derive(lastChord) # use deriveAll() later for flexibility
    allPitches = list(set([pitch for pitch in scales.getPitches()]))
    allNoteNames = [i.name for i in allPitches] # octaves don't matter

    # Return a note (no octave here) in a scale that matches the lastChord.
    sNoteName = random.choice(allNoteNames)
    lastChordSort = lastChord.sortAscending()
    sNoteOctave = random.choice([i.octave for i in lastChordSort.pitches])
    sNote = note.Note(("%s%s" % (sNoteName, sNoteOctave)))
    return sNote

def __generate_approach_tone(lastChord):
    sNote = __generate_scale_tone(lastChord)
    aNote = sNote.transpose(random.choice([1, -1]))
    return aNote

def __generate_arbitrary_tone(lastChord):
    return __generate_scale_tone(lastChord) # fix later, make random note.

def parse_melody(fullMeasureNotes, fullMeasureChords):
    # Remove extraneous elements.x
    measure = copy.deepcopy(fullMeasureNotes)
    chords = copy.deepcopy(fullMeasureChords)
    measure.removeByNotOfClass([note.Note, note.Rest])
    chords.removeByNotOfClass([chord.Chord])

    # Information for the start of the measure.
    # 1) measureStartTime: the offset for measure's start, e.g. 476.0.
    # 2) measureStartOffset: how long from the measure start to the first element.
    measureStartTime = measure[0].offset - (measure[0].offset % 4)
    measureStartOffset  = measure[0].offset - measureStartTime

    # Iterate over the notes and rests in measure, finding the grammar for each
    # note in the measure and adding an abstract grammatical string for it. 

    fullGrammar = ""
    prevNote = None # Store previous note. Need for interval.
    numNonRests = 0 # Number of non-rest elements. Need for updating prevNote.
    for ix, nr in enumerate(measure):
        # Get the last chord. If no last chord, then (assuming chords is of length
        # >0) shift first chord in chords to the beginning of the measure.
        try: 
            lastChord = [n for n in chords if n.offset <= nr.offset][-1]
        except IndexError:
            chords[0].offset = measureStartTime
            lastChord = [n for n in chords if n.offset <= nr.offset][-1]

        # FIRST, get type of note, e.g. R for Rest, C for Chord, etc.
        # Dealing with solo notes here. If unexpected chord: still call 'C'.
        elementType = ' '
        # R: First, check if it's a rest. Clearly a rest --> only one possibility.
        if isinstance(nr, note.Rest):
            elementType = 'R'
        # C: Next, check to see if note pitch is in the last chord.
        elif nr.name in lastChord.pitchNames or isinstance(nr, chord.Chord):
            elementType = 'C'
        # L: (Complement tone) Skip this for now.
        # S: Check if it's a scale tone.
        elif __is_scale_tone(lastChord, nr):
            elementType = 'S'
        # A: Check if it's an approach tone, i.e. +-1 halfstep chord tone.
        elif __is_approach_tone(lastChord, nr):
            elementType = 'A'
        # X: Otherwise, it's an arbitrary tone. Generate random note.
        else:
            elementType = 'X'

        # SECOND, get the length for each element. e.g. 8th note = R8, but
        # to simplify things you'll use the direct num, e.g. R,0.125
        if (ix == (len(measure)-1)):
            # formula for a in "a - b": start of measure (e.g. 476) + 4
            diff = measureStartTime + 4.0 - nr.offset
        else:
            diff = measure[ix + 1].offset - nr.offset

        # Combine into the note info.
        noteInfo = "%s,%.3f" % (elementType, nr.quarterLength) # back to diff

        # THIRD, get the deltas (max range up, max range down) based on where
        # the previous note was, +- minor 3. Skip rests (don't affect deltas).
        intervalInfo = ""
        if isinstance(nr, note.Note):
            numNonRests += 1
            if numNonRests == 1:
                prevNote = nr
            else:
                noteDist = interval.Interval(noteStart=prevNote, noteEnd=nr)
                noteDistUpper = interval.add([noteDist, "m3"])
                noteDistLower = interval.subtract([noteDist, "m3"])
                intervalInfo = ",<%s,%s>" % (noteDistUpper.directedName, 
                    noteDistLower.directedName)
                # print "Upper, lower: %s, %s" % (noteDistUpper,
                #     noteDistLower)
                # print "Upper, lower dnames: %s, %s" % (
                #     noteDistUpper.directedName,
                #     noteDistLower.directedName)
                # print "The interval: %s" % (intervalInfo)
                prevNote = nr

        # Return. Do lazy evaluation for real-time performance.
        grammarTerm = noteInfo + intervalInfo 
        fullGrammar += (grammarTerm + " ")

    return fullGrammar.rstrip()

def __grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

def prune_grammar(curr_grammar):
    pruned_grammar = curr_grammar.split(' ')

    for ix, gram in enumerate(pruned_grammar):
        terms = gram.split(',')
        terms[1] = str(__roundUpDown(float(terms[1]), 0.250, 
            random.choice([-1, 1])))
        pruned_grammar[ix] = ','.join(terms)
    pruned_grammar = ' '.join(pruned_grammar)

    return pruned_grammar

def prune_notes(curr_notes):
    for n1, n2 in __grouper(curr_notes, n=2):
        if n2 == None: # corner case: odd-length list
            continue
        if isinstance(n1, note.Note) and isinstance(n2, note.Note):
            if n1.nameWithOctave == n2.nameWithOctave:
                curr_notes.remove(n2)

    return curr_notes

def clean_up_notes(curr_notes):
    removeIxs = []
    for ix, m in enumerate(curr_notes):
        # QA1: ensure nothing is of 0 quarter note len, if so changes its len
        if (m.quarterLength == 0.0):
            m.quarterLength = 0.250
        # QA2: ensure no two melody notes have same offset, i.e. form a chord.
        # Sorted, so same offset would be consecutive notes.
        if (ix < (len(curr_notes) - 1)):
            if (m.offset == curr_notes[ix + 1].offset and
                isinstance(curr_notes[ix + 1], note.Note)):
                removeIxs.append((ix + 1))
    curr_notes = [i for ix, i in enumerate(curr_notes) if ix not in removeIxs]

    return curr_notes

def unparse_grammar(m1_grammar, m1_chords):
    m1_elements = stream.Voice()
    currOffset = 0.0 # for recalculate last chord.
    prevElement = None
    for ix, grammarElement in enumerate(m1_grammar.split(' ')):
        terms = grammarElement.split(',')
        currOffset += float(terms[1]) # works just fine

        # Case 1: it's a rest. Just append
        if terms[0] == 'R':
            rNote = note.Rest(quarterLength = float(terms[1]))
            m1_elements.insert(currOffset, rNote)
            continue

        # Get the last chord first so you can find chord note, scale note, etc.
        try: 
            lastChord = [n for n in m1_chords if n.offset <= currOffset][-1]
        except IndexError:
            m1_chords[0].offset = 0.0
            lastChord = [n for n in m1_chords if n.offset <= currOffset][-1]

        # Case: no < > (should just be the first note) so generate from range
        # of lowest chord note to highest chord note (if not a chord note, else
        # just generate one of the actual chord notes). 

        # Case #1: if no < > to indicate next note range. Usually this lack of < >
        # is for the first note (no precedent), or for rests.
        if (len(terms) == 2): # Case 1: if no < >.
            insertNote = note.Note() # default is C

            # Case C: chord note.
            if terms[0] == 'C':
                insertNote = __generate_chord_tone(lastChord)

            # Case S: scale note.
            elif terms[0] == 'S':
                insertNote = __generate_scale_tone(lastChord)

            # Case A: approach note.
            # Handle both A and X notes here for now.
            else:
                insertNote = __generate_approach_tone(lastChord)

            # Update the stream of generated notes
            insertNote.quarterLength = float(terms[1])
            if insertNote.octave < 4:
                insertNote.octave = 4
            m1_elements.insert(currOffset, insertNote)
            prevElement = insertNote

        # Case #2: if < > for the increment. Usually for notes after the first one.
        else:
            # Get lower, upper intervals and notes.
            interval1 = interval.Interval(terms[2].replace("<",''))
            interval2 = interval.Interval(terms[3].replace(">",''))
            if interval1.cents > interval2.cents:
                upperInterval, lowerInterval = interval1, interval2
            else:
                upperInterval, lowerInterval = interval2, interval1
            lowPitch = interval.transposePitch(prevElement.pitch, lowerInterval)
            highPitch = interval.transposePitch(prevElement.pitch, upperInterval)
            numNotes = int(highPitch.ps - lowPitch.ps + 1) # for range(s, e)

            # Case C: chord note, must be within increment (terms[2]).
            # First, transpose note with lowerInterval to get note that is
            # the lower bound. Then iterate over, and find valid notes. Then
            # choose randomly from those.
            
            if terms[0] == 'C':
                relevantChordTones = []
                for i in range(0, numNotes):
                    currNote = note.Note(lowPitch.transpose(i).simplifyEnharmonic())
                    if __is_chord_tone(lastChord, currNote):
                        relevantChordTones.append(currNote)
                if len(relevantChordTones) > 1:
                    insertNote = random.choice([i for i in relevantChordTones
                        if i.nameWithOctave != prevElement.nameWithOctave])
                elif len(relevantChordTones) == 1:
                    insertNote = relevantChordTones[0]
                else: # if no choices, set to prev element +-1 whole step
                    insertNote = prevElement.transpose(random.choice([-2,2]))
                if insertNote.octave < 3:
                    insertNote.octave = 3
                insertNote.quarterLength = float(terms[1])
                m1_elements.insert(currOffset, insertNote)

            # Case S: scale note, must be within increment.
            elif terms[0] == 'S':
                relevantScaleTones = []
                for i in range(0, numNotes):
                    currNote = note.Note(lowPitch.transpose(i).simplifyEnharmonic())
                    if __is_scale_tone(lastChord, currNote):
                        relevantScaleTones.append(currNote)
                if len(relevantScaleTones) > 1:
                    insertNote = random.choice([i for i in relevantScaleTones
                        if i.nameWithOctave != prevElement.nameWithOctave])
                elif len(relevantScaleTones) == 1:
                    insertNote = relevantScaleTones[0]
                else: # if no choices, set to prev element +-1 whole step
                    insertNote = prevElement.transpose(random.choice([-2,2]))
                if insertNote.octave < 3:
                    insertNote.octave = 3
                insertNote.quarterLength = float(terms[1])
                m1_elements.insert(currOffset, insertNote)

            # Case A: approach tone, must be within increment.
            # For now: handle both A and X cases.
            else:
                relevantApproachTones = []
                for i in range(0, numNotes):
                    currNote = note.Note(lowPitch.transpose(i).simplifyEnharmonic())
                    if __is_approach_tone(lastChord, currNote):
                        relevantApproachTones.append(currNote)
                if len(relevantApproachTones) > 1:
                    insertNote = random.choice([i for i in relevantApproachTones
                        if i.nameWithOctave != prevElement.nameWithOctave])
                elif len(relevantApproachTones) == 1:
                    insertNote = relevantApproachTones[0]
                else: # if no choices, set to prev element +-1 whole step
                    insertNote = prevElement.transpose(random.choice([-2,2]))
                if insertNote.octave < 3:
                    insertNote.octave = 3
                insertNote.quarterLength = float(terms[1])
                m1_elements.insert(currOffset, insertNote)

            # update the previous element.
            prevElement = insertNote

    return m1_elements

chords, abstract_grammars = get_musical_data('original_metheny.mid')
corpus, tones, tones_indices, indices_tones = get_corpus_data(abstract_grammars)

def post_processing(inference_model, corpus = corpus, abstract_grammars = abstract_grammars , tones = tones, tones_indices = tones_indices, indices_tones = indices_tones, T_y = 10, max_tries = 1000, diversity = 0.5):
    
    # set up audio stream
    out_stream = stream.Stream()
    
    # Initialize chord variables
    curr_offset = 0.0                                     # variable used to write sounds to the Stream.
    num_chords = int(len(chords) / 3)                     # number of different set of chords
    
    print("Predicting new values for different set of chords.")
    # Loop over all 18 set of chords. At each iteration generate a sequence of tones
    # and use the current chords to convert it into actual sounds 
    for i in range(1, num_chords):
        
        # Retrieve current chord from stream
        curr_chords = stream.Voice()
        
        # Loop over the chords of the current set of chords
        for j in chords[i]:
            # Add chord to the current chords with the adequate offset, no need to understand this
            curr_chords.insert((j.offset % 4), j)
        
        # Generate a sequence of tones using the model
        _, indices = predict_and_sample(inference_model)
        indices = list(indices.squeeze())
        pred = [indices_tones[p] for p in indices]
        
        predicted_tones = 'C,0.25 '
        for k in range(len(pred) - 1):
            predicted_tones += pred[k] + ' ' 
        
        predicted_tones +=  pred[-1]
                
        #### POST PROCESSING OF THE PREDICTED TONES ####
        # We will consider "A" and "X" as "C" tones. It is a common choice.
        predicted_tones = predicted_tones.replace(' A',' C').replace(' X',' C')

        # Pruning #1: smoothing measure
        predicted_tones = prune_grammar(predicted_tones)
        
        # Use predicted tones and current chords to generate sounds
        sounds = unparse_grammar(predicted_tones, curr_chords)

        # Pruning #2: removing repeated and too close together sounds
        sounds = prune_notes(sounds)

        # Quality assurance: clean up sounds
        sounds = clean_up_notes(sounds)

        # Print number of tones/notes in sounds
        print('Generated %s sounds using the predicted values for the set of chords ("%s") and after pruning' % (len([k for k in sounds if isinstance(k, note.Note)]), i))
        
        # Insert sounds into the output stream
        for m in sounds:
            out_stream.insert(curr_offset + m.offset, m)
        for mc in curr_chords:
            out_stream.insert(curr_offset + mc.offset, mc)

        curr_offset += 4.0
        
    # Initialize tempo of the output stream with 130 bit per minute
    out_stream.insert(0.0, tempo.MetronomeMark(number=130))

    # Save audio stream to fine
    mf = midi.translate.streamToMidiFile(out_stream)
    mf.open("new_music.midi", 'wb')
    mf.write()
    print("Your generated music is saved in new_music.midi")
    mf.close()
    
    return out_stream

def Generate_Music():

  inference_model = Music_Generation_Helper(notes = 78)
  music = post_processing(inference_model)

Generate_Music()

