import os
import logging
import numpy as np
import torch
import librosa
import whisper
from typing import Dict , Any , List , Optional , Tuple
from transformers import pipeline
from pydub import AudioSegment

logger=logging.getLogger(__name__)

class AudioAgent:
    """
    Agent responsible for processing and analyzing audio inputs 
    such as cough sounds , breathing patterns , voice analysis, etc .
    Using OpenAI's Whisper Model for Transcription and custom PyTorch models
    for health-related audio analysis. 
    """

    def __init__(self,config: Dict[str,Any]):
        """
        Initialize the audio agent with configuration

        Args:
            config: Configuration dictionary with audio processing parameters 
        """
        self.config=config
        self.device=torch.device("cuda" if torch.cuda.is_available() and config.get("use_gpu",True) else "cpu")
        self.sample_rate=config.get("sample_rate",16000)
        self.models={}

        whisper_model_size=config.get("whisper_model_size","base")
        self.whisper_model=whisper.load_model(whisper_model_size,device=self.device)

        self._load_models()

        logger.info(f"AudioAgent initialized pn {self.device} with Whisper {whisper_model_size}")

    
    def _load_models(self):
        """load the required audio models based on configuration"""
        model_configs=self.config.get("models",{})

        for model_name, model_config in model_configs.items():
            try:
                if model_name == "cough_classifier":
                    self.models[model_name]=self._load_cough_classifier(model_config)

                elif model_name == "breathing_analyzer":
                    self.models[model_name]=self._load_breathing_analyzer(model_config)

                elif model_name == "voice_analyzer":
                    self.models[model_name]==self._load_voice_ananlyzer(model_config)

                elif model_name == "emotion_detector":
                    self.models[model_name]== pipeline(
                        "audio-classification",
                         model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
                    )

                logger.info(f"Successfully loaded audio model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load audio model {model_name}: {str(e)}") 


    def _load_cough_classifier(self,config):
        """load cough sound classifier model using PyTorch"""

        model_path= config.get("model_path","models/audio_models/cough_classifier.pt")

        class CoughClassifier(torch.nn.Module):
            def __init__(self):
                super(CoughClassifier, self).__init__()
                self.conv1 = torch.nn.Conv1d(1, 64, kernel_size=10, stride=5)
                self.pool = torch.nn.MaxPool1d(2)
                self.conv2 = torch.nn.Conv1d(64, 128, kernel_size=10, stride=5)
                self.flatten = torch.nn.Flatten()
                self.fc1 = torch.nn.Linear(128 * 99, 128)  
                self.fc2 = torch.nn.Linear(128, 64)
                self.fc3 = torch.nn.Linear(64, 4) 
                self.relu = torch.nn.ReLU()

            def forward(self, x):
                x = self.pool(self.relu(self.conv1(x)))
                x = self.pool(self.relu(self.conv2(x)))
                x = self.flatten(x)
                x = self.relu(self.fc1(x))
                x = self.relu(self.fc2(x))
                x = self.fc3(x)
                return x
        model = CoughClassifier().to(self.device)
        

        if os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=self.device))
            model.eval()
        else:
            logger.warning(f"Cough classifier model not found at {model_path}. Using untrained model.")
        
        return model

    def _load_breathing_analyzer(self,config):
        """Load breathing pattern analyzer model"""

        class BreathingAnalyzer(torch.nn.Module):
            def __init__(self):
                super(BreathingAnalyzer,self).__init__()
                self.conv1 = torch.nn.Conv1d(1, 64, kernel_size=10, stride=5)
                self.pool = torch.nn.MaxPool1d(2)
                self.conv2 = torch.nn.Conv1d(64, 128, kernel_size=10, stride=5)
                self.flatten = torch.nn.Flatten()
                self.fc1 = torch.nn.Linear(128 * 99, 128)
                self.fc2 = torch.nn.Linear(128, 64)
                self.fc3 = torch.nn.Linear(64, 5)
                self.relu = torch.nn.ReLU()
            def forward(self, x):
                x = self.pool(self.relu(self.conv1(x)))
                x = self.pool(self.relu(self.conv2(x)))
                x = self.flatten(x)
                x = self.relu(self.fc1(x))
                x = self.relu(self.fc2(x))
                x = self.fc3(x)
                return x
        model = BreathingAnalyzer().to(self.device)
        model_path = config.get("model_path", "models/audio_models/breathing_analyzer.pt")
        
        if os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=self.device))
            model.eval()
        else:
            logger.warning(f"Breathing analyzer model not found at {model_path}. Using untrained model.")
            
        return model
    
    def _load_voice_analyzer(self, config):
        """Load voice characteristics analyzer model"""
        model_path = config.get("model_path", "models/audio_models/voice_analyzer.pt")
        
        # Placeholder for a real model implementation
        class VoiceAnalyzer(torch.nn.Module):
            def __init__(self):
                super(VoiceAnalyzer, self).__init__()
                self.conv1 = torch.nn.Conv1d(1, 64, kernel_size=10, stride=5)
                self.pool = torch.nn.MaxPool1d(2)
                self.conv2 = torch.nn.Conv1d(64, 128, kernel_size=10, stride=5)
                self.lstm = torch.nn.LSTM(128, 64, batch_first=True, bidirectional=True)
                self.fc = torch.nn.Linear(128, 3)  # 3 outputs: tremor, hoarseness, clarity
                
            def forward(self, x):
                x = self.pool(torch.nn.functional.relu(self.conv1(x)))
                x = self.pool(torch.nn.functional.relu(self.conv2(x)))
                x = x.permute(0, 2, 1)  # Reshape for LSTM
                x, _ = self.lstm(x)
                x = x[:, -1, :]  # Take the last output
                x = self.fc(x)
                return x
                
        model = VoiceAnalyzer().to(self.device)
        
        if os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=self.device))
            model.eval()
        else:
            logger.warning(f"Voice analyzer model not found at {model_path}. Using untrained model.")
            
        return model


    def preprocess_audio(self, audio_path:str)->np.ndarray:
        """
        Preprocess audio file for analysis
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Preprocessed audio as numpy array
        """

        try :
            if not audio_path.endswith('.wav'):
                audio = AudioSegment.from_file(audio_path)
                temp_path= audio_path.rsplit('.',1)[0]+'.wav'
                audio.export(temp_path,format='wav')
                audio_path=temp_path

            audio, sr = librosa.load(audio_path, sr=self.sample_rate)

            if self.config.get("normalize",True):
                audio = librosa.util.normalize(audio)
            
            if self.config.get("remove_silence",False):
                non_silent_intervals=librosa.effects.split(
                    audio,
                    top_db=self.config.get("silence_thresold",30)
                )
                audio=np.concatenate([audio[start:end] for start,end in non_silent_intervals])

            return audio
        except Exception as e:
            logger.error(f"Error preprocessing audio file {audio_path}:{str(e)}")
            raise


    def extract_features(self,audio:np.ndarray)->Dict[str, Any]:
        """
        Extract features from preprocessed audio
        
        Args:
            audio: Preprocessed audio array
            
        Returns:
            Dictionary of extracted features
        """

        features={}

        if self.config.get("extract_mfcc",True):
            mfccs=librosa.feature.mfcc(
                y=audio,
                sr=self.sample_rate,
                n_mfcc=self.config.get("n_mfcc",13)
            )
            features["mfcc"]=mfccs.mean(axis=1)

        if self.config.get("external_spectral_centroid",True):
            spectral_centroid=librosa.feature.spectral_centroid(
                y=audio,
                sr=self.sample_rate
            )
            features["spectral_centroid"]=spectral_centroid.mean()

        if self.config.get("extract_chroma",True):
            bandwidth=librosa.feature.chroma_stft(y=audio,sr=self.sample_rate)
            features["bandwidth"]=bandwidth.mean()

        if self.config.get("extract_tempo",True):
            onset_env=librosa.onset.onset_strength(y=audio, sr=self.sample_rate)
            tempo=librosa.beat.tempo(onset_envelope=onset_env, sr=self.sample_rate)
            features["tempo"]=tempo[0]

        return features

    def transcribe_audio(self, audio: np.ndarray) -> str:
        """
        Transcribe speech in audio using Whisper
        
        Args:
            audio: Audio array
            
        Returns:
            Transcribed text
        """
        try:
            # Convert to float32 if needed
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
                
            # Use Whisper to transcribe
            result = self.whisper_model.transcribe(audio)
            return result["text"]
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return ""
    
    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze audio file and return comprehensive results
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dictionary with analysis results
        """
        results = {}
        
        try:

            audio = self.preprocess_audio(audio_path)
            

            features = self.extract_features(audio)
            results["features"] = features
            

            if self.config.get("transcribe", True):
                transcript = self.transcribe_audio(audio)
                results["transcript"] = transcript
            

            for model_name, model in self.models.items():
                if model_name == "emotion_detector":

                    emotion_result = model(audio_path)
                    results[model_name] = emotion_result
                else:

                    with torch.no_grad():
                        model_input = torch.tensor(audio).float().unsqueeze(0).unsqueeze(0)
                        if len(model_input) > 10000: 
                            model_input = model_input[:, :, :10000]
                        

                        output = model(model_input.to(self.device))
                        if model_name == "cough_classifier":
                            classes = ["normal", "covid", "pneumonia", "bronchitis"]
                            probs = torch.nn.functional.softmax(output, dim=1)[0]
                            class_idx = torch.argmax(probs).item()
                            results[model_name] = {
                                "prediction": classes[class_idx],
                                "confidence": probs[class_idx].item(),
                                "probabilities": {cls: prob.item() for cls, prob in zip(classes, probs)}
                            }
                        elif model_name == "breathing_analyzer":
                            classes = ["normal", "wheezy", "crackle", "stridor", "rhonchi"]
                            probs = torch.nn.functional.softmax(output, dim=1)[0]
                            class_idx = torch.argmax(probs).item()
                            results[model_name] = {
                                "prediction": classes[class_idx],
                                "confidence": probs[class_idx].item(),
                                "probabilities": {cls: prob.item() for cls, prob in zip(classes, probs)}
                            }
                        elif model_name == "voice_analyzer":
                            output = output[0].cpu().numpy()
                            results[model_name] = {
                                "tremor": float(output[0]),
                                "hoarseness": float(output[1]),
                                "clarity": float(output[2])
                            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing audio: {str(e)}")
            results["error"] = str(e)
            return results