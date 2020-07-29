from __future__ import print_function
from server import app
from flask import render_template, flash, jsonify, request, redirect
from threading import Thread
from server.tasks import process_video
# from server.liveTranslate import live_transcribe
from flask_cors import CORS, cross_origin
import os, uuid
import pyaudio
from watson_developer_cloud import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from watson_developer_cloud.websocket import RecognizeCallback, AudioSource
from dotenv import load_dotenv
import json
# from threading import Thread
import platform


cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mpeg', 'mov', 'm4v'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def hello_world():
    return app.send_static_file('index.html')

@app.route("/language_models", methods=['GET'])
@cross_origin()
def language_models():
    models = app.config['LANGUAGE_TRANSLATOR'].list_models().get_result()
    languages = app.config['LANGUAGE_TRANSLATOR'].list_identifiable_languages().get_result()
    return jsonify({"models": models["models"], "languages": languages["languages"]})

@app.route("/upload_video", methods=['POST'])
@cross_origin()
def upload_video():
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"error": "No file part. Please ensure the video is uploaded as multipart form data with the key as 'file'."}), 400
    file = request.files['file']
   
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        file_id = str(uuid.uuid1())
        mqtt_topic = 'cfc-covid-19-video-transcriber-starter/'+ file_id
        new_filename = file_id + '.'+ file.filename.split('.')[1]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(file_path)

        # extract translation fields if specified
        source = None
        target = None
        form_fields = request.form.to_dict(flat=False)
        if 'source' in form_fields and 'target' in form_fields:
            source = form_fields['source'][0]
            target = form_fields['target'][0]

        # start pipeline as a new thread
        thread = Thread(target=process_video, args=(file_path,new_filename,mqtt_topic,source,target,))
        thread.daemon = True
        thread.start()

        # return mqtt namespace for listening for video updates
        return jsonify({"msg": "file uploaded", "mqtt_topic": mqtt_topic})
    else:
        return jsonify({"error": "File must be one of: "+json.dumps(ALLOWED_EXTENSIONS)}), 400


@app.route("/LiveTrans", methods=['GET'])
@cross_origin()
def live_translate():
    print('hey im here')
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
    audioTrans = {}
    with open("server\\routes\\spchToTxtLive.json", 'w') as f:
        json.dump(audioTrans, f)
    ###############################################
    #### Prepare Speech to Text Service ########
    ###############################################
    # initialize speech to text service
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!Give Keys here!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1
    # speech_to_text = SpeechToTextV1(
    #    url="URL HERE", 
    #    iam_apikey="APIKEY HERE")
    
    # define callback for the speech to text service
    class MyRecognizeCallback(RecognizeCallback):
        def __init__(self):
            RecognizeCallback.__init__(self)
            self.transcript = None
        def on_transcription(self, transcript):
            print('transcript: {}'.format(transcript))
            print(transcript)
            audioTrans = transcript
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
            audioTrans = '{0}final: {1}'.format(
                '' if data['results'][0]['final'] else 'not ',
                self.transcript)
            json.dump(audioTrans, f)
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
    
       

@app.errorhandler(404)
@app.route("/error404")
def page_not_found(error):
    return app.send_static_file('404.html')

@app.errorhandler(500)
@app.route("/error500")
def requests_error(error):
    return app.send_static_file('500.html')
