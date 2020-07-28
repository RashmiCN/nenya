from __future__ import print_function
import pyaudio
from watson_developer_cloud import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from watson_developer_cloud.websocket import RecognizeCallback, AudioSource
from dotenv import load_dotenv
from threading import Thread
import os, platform
try:
    from Queue import Queue, Full
except ImportError:
    from queue import Queue, Full
###############################################
#### Initalize queue to store the recordings ##
###############################################
CHUNK = 1024
# Note: It will discard if the websocket client can't consumme fast enough
# So, increase the max size as per your choice
BUF_MAX_SIZE = CHUNK * 10
# Buffer to store audio
q = Queue(maxsize=int(round(BUF_MAX_SIZE / CHUNK)))
# Create an instance of AudioSource
audio_source = AudioSource(q, True, True)
###############################################
#### Prepare Speech to Text Service ########
###############################################
# initialize speech to text service
speech_to_text = SpeechToTextV1(
    url="https://api.eu-gb.speech-to-text.watson.cloud.ibm.com/instances/87521fcc-f094-44d9-9953-1a91d68215f3", 
    iam_apikey="zujIlMW63qNznLI7Y7zgnT8Bt5sbebqyMJx0wMHVnAY1")
# SpeechToTextV1(
#     username='YOUR SERVICE USERNAME',
#     password='YOUR SERVICE PASSWORD',
#     url='url')
# load_dotenv()
# authenticator = IAMAuthenticator(os.getenv("STT_API_KEY")) 
# service = SpeechToTextV1(authenticator=authenticator) 
# service.set_service_url(os.getenv("STT_URL"))
# define callback for the speech to text service
class MyRecognizeCallback(RecognizeCallback):
    def __init__(self):
        RecognizeCallback.__init__(self)
        self.transcript = None
    def on_transcription(self, transcript):
        print('transcript: {}'.format(transcript))
        print(transcript)
    def on_connected(self):
        print('Connection was successful')
    def on_error(self, error):
        print('Error received: {}'.format(error))
    def on_inactivity_timeout(self, error):
        print('Inactivity timeout: {}'.format(error))
    def on_listening(self):
        print('Service is listening')
    def on_hypothesis(self, hypothesis):
        print(hypothesis)
    def on_data(self, data):
        self.transcript = data['results'][0]['alternatives'][0]['transcript']
        print('{0}final: {1}'.format(
            '' if data['results'][0]['final'] else 'not ',
            self.transcript
        ))
        # print(data)
    def on_close(self):
        print("Connection closed")
# this function will initiate the recognize service and pass in the AudioSource
def recognize_using_weboscket(*args):
    mycallback = MyRecognizeCallback()
    speech_to_text.recognize_using_websocket(audio=audio_source,
                                             content_type='audio/l16; rate=44100',
                                             recognize_callback=mycallback,
                                             interim_results= True)
    print(mycallback.transcript)
###############################################
#### Prepare the for recording using Pyaudio ##
###############################################
# Variables for recording the speech
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
# define callback for pyaudio to store the recording in queue
def pyaudio_callback(in_data, frame_count, time_info, status):
    try:
        q.put(in_data)
    except Full:
        pass # discard
    return (None, pyaudio.paContinue)
# instantiate pyaudio
audio = pyaudio.PyAudio()
# open stream using callback
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
    stream_callback=pyaudio_callback,
    start=False
)
#########################################################################
#### Start the recording and start service to recognize the stream ######
#########################################################################
print("Enter CTRL+C to end recording...")
stream.start_stream()
try:
    recognize_thread = Thread(target=recognize_using_weboscket, args=())
    recognize_thread.start()
    while True:
        pass
except KeyboardInterrupt:
    # stop recording
    audio_source.completed_recording()
    stream.stop_stream()
    stream.close()
audio.terminate()