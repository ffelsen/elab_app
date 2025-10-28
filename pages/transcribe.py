"""
Whispered Secrets.

Usage:
    python -m demo.transcribe
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue
from time import sleep

import numpy as np
import speech_recognition as sr
import torch
import typer
import whisper


def check_for_stop_signal():
    return os.path.exists("stop_signal.txt")


def main(
    model: str = typer.Option(
        "medium",
        help="Model to use",
        prompt="Choose a model from ['tiny', 'base', 'small', 'medium']",
    ),
    energy_threshold: int = typer.Option(150, help="Energy level for mic to detect."),
    record_timeout: float = typer.Option(60.0, help="How real time the recording is in seconds."),
    phrase_timeout: float = typer.Option(
        7.0,
        help=(
            "How much empty space between recordings before we consider"
            "it a new line in the transcription."
        ),
    ),
    mic_index: int = typer.Option(0, help="Microphone device to use."),
):
    """main function"""

    # Configure microphone
    if mic_index is None:
        print("Available microphone devices are: ")
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f'{index}: Microphone with name "{name}" found')
        mic_index = int(input("Please enter the index of the microphone you want to use: "))
    source = sr.Microphone(sample_rate=16000, device_index=mic_index)

    # Load / Download model
    audio_model = whisper.load_model(model)

    # We use SpeechRecognizer to record our audio because it has a nice feature where it can detect
    # when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = energy_threshold

    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to
    # a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False

    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    transcription = [""]
    transcription_data = []  # Store segments with timestamps

    # The last time a recording was retrieved from the queue.
    phrase_time = None
    session_start_time = datetime.now()

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio: sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.

        audio: An AudioData containing the recorded bytes.
        """
        data_queue.put(audio.get_raw_data())

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    stop_listening = recorder.listen_in_background(
        source,
        record_callback,
        phrase_time_limit=record_timeout,
    )

    message = (
        f"✅ Model {model} loaded & listening (energy_threshold={energy_threshold}, "
        f"record_timeout={record_timeout}, phrase_timeout={phrase_timeout})...\n"
    )
    print(message)
    write_transcription_with_timestamps(transcription_data, initial_message=message)

    try:
        while True:
            if check_for_stop_signal():
                print("Stop signal received. Processing remaining audio...")
                
                # Stop the background listener first but allow current recording to finish
                stop_listening(wait_for_stop=True)
                
                # Give a moment for any final audio to be queued
                sleep(0.5)
                
                # Process any remaining audio in the queue before stopping
                final_audio_chunks = []
                processed_chunks = 0
                
                while not data_queue.empty():
                    final_audio_chunks.append(data_queue.get())
                    processed_chunks += 1
                
                print(f"Processing {processed_chunks} remaining audio chunks...")
                
                if final_audio_chunks:
                    # Combine final audio data
                    audio_data = b"".join(final_audio_chunks)
                    
                    # Convert to numpy array
                    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # Only process if we have meaningful audio data
                    if len(audio_np) > 1600:  # At least 0.1 seconds of audio at 16kHz
                        # Transcribe final audio with timestamps
                        result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                        
                        if result and 'segments' in result and result['segments']:
                            current_time = datetime.now()
                            
                            for segment in result['segments']:
                                text = segment['text'].strip()
                                if text:  # Only add if there's actual text
                                    print(f"Final transcription: '{text}'")
                                    
                                    # Calculate timestamps
                                    segment_duration = segment['end'] - segment['start']
                                    speech_time = current_time - timedelta(seconds=segment_duration/2)
                                    relative_seconds = (speech_time - session_start_time).total_seconds() + segment['start']
                                    
                                    segment_data = {
                                        'text': text,
                                        'start': segment['start'],
                                        'end': segment['end'],
                                        'real_time': speech_time.strftime('%H:%M:%S'),
                                        'relative_time': f"{relative_seconds:.1f}s"
                                    }
                                    
                                    transcription_data.append(segment_data)
                                    
                                    # Also add to plain transcription for compatibility
                                    if transcription and transcription[-1]:
                                        cleaned = transcription[-1].strip()
                                        for suffix in ["...", ".", "?"]:
                                            cleaned = cleaned.removesuffix(suffix)
                                        cleaned_text = (cleaned + " " + text).strip()
                                        transcription[-1] = cleaned_text
                                    else:
                                        transcription.append(text)
                            
                            # Write final transcription to file
                            write_transcription_with_timestamps(transcription_data)
                            print("Final transcription saved.")
                
                print("Exiting...")
                break

            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                now = datetime.now()

                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Combine audio data from queue
                audio_data = b"".join(list(data_queue.queue))
                data_queue.queue.clear()

                # Convert in-ram buffer to something the model can use directly without needing a
                # temp file. Convert data from 16 bit wide integers to floating point with a width
                # of 32 bits. Clamp the audio stream frequency to a PCM wavelength compatible
                # default of 32768hz max.
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                # Read the transcription - get full text only (no individual segment timestamps)
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available(), language='en', task='transcribe')
                
                if result:
                    current_time = datetime.now()
                    
                    # Get the full text from this block
                    full_text = result["text"].strip()
                    
                    if full_text:
                        # Calculate timestamp for this block (start of speech in this block)
                        audio_duration = len(audio_np) / 16000
                        block_start_time = current_time - timedelta(seconds=audio_duration)
                        relative_seconds = (block_start_time - session_start_time).total_seconds()
                        
                        # Create single block entry with one timestamp
                        block_data = {
                            'text': full_text,
                            'real_time': block_start_time.strftime('%H:%M:%S'),
                            'relative_time': f"{relative_seconds:.1f}s"
                        }
                        
                        transcription_data.append(block_data)
                        transcription.append(full_text)
                        
                        print(f"[{block_start_time.strftime('%H:%M:%S')}] {full_text}")

                # Write updated transcription with timestamps
                write_transcription_with_timestamps(transcription_data)
            else:
                # Infinite loops are bad for processors, must sleep.
                sleep(0.1)
    except KeyboardInterrupt:
        pass

    finally:
        # Stop the background listener
        try:
            stop_listening(wait_for_stop=False)
        except:
            pass
        
        if os.path.exists("stop_signal.txt"):
            os.remove("stop_signal.txt")  # Clean up the signal file on exit


def write_transcription_with_timestamps(transcription_data, initial_message="Model loaded & listening\n"):
    """Write transcription data with timestamps to file"""
    try:
        with Path("temp/transcription_output.txt").open("w", encoding="utf-8") as file:
            file.write(initial_message)
            
            if transcription_data:
                file.write("\n=== TIMESTAMPED TRANSCRIPTION ===\n\n")
                
                for segment in transcription_data:
                    # Format: [Real Time] [Relative Time] Text
                    file.write(f"[{segment['real_time']}] [{segment['relative_time']}] {segment['text']}\n")
                
                file.write(f"\n=== PLAIN TEXT ===\n\n")
                # Also provide a clean version without timestamps
                for segment in transcription_data:
                    file.write(f"{segment['text']} ")
                    
    except Exception as e:
        print(f"Error writing transcription: {e}")


if __name__ == "__main__":
    typer.run(main)
