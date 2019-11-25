# Artificial-Music-Synthesis
This repository contains the iPython Notebook of the implementation of Artificial Music Generation using Recurrent Neural Network.

## Important Points about the Project: 
- A Deep RNN model is used to develop the model.
- A series of LSTM(Long-Short Term Memory) and GRU(Gated Recurrent Unit) cells are used as the basic units.
- The model is similar to a Language Predictive model.
- The frequency pattern of the musical notes is analyzed.
- Musical notes & tones in fixed intervals of time are represented in the form of One-hot encoding.
- The model is trained on several epochs using the generated one-hot encoding.
- The trained model is finally used to predict the time-sequence frequency pattern of musical notes.
- These generated encodings are finally Post-processed to get the melodious musical sound.
- The generated Music is a combination of sounds produced from various musical instruments.

## Frameworks and Libraries Used: 
- Model is developed on Keras Framework.
- For Pre-processing and Post-processing of Musical data, IPython library is used.

## Note : The Music Files that are synthesised by the network are also uploaded.
