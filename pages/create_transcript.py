import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import speech_recognition as sr
import streamlit as st
from utils import append_to_experiment

hide_stale_elements = """
<style>
div[data-stale="true"] {
    display: none !important;
}
</style>
"""


def send_stop_signal():
    with Path("stop_signal.txt").open("w") as f:
        print("Sending stop signal")
        f.write("stop")


def start_transcription(model, energy_threshold, record_timeout, phrase_timeout, mic_index):
    try:
        cmd = [
            sys.executable,
            "-m",
            "pages.transcribe",
            "--model",
            model,
            "--energy-threshold",
            str(energy_threshold),
            "--record-timeout",
            str(record_timeout),
            "--phrase-timeout",
            str(phrase_timeout),
            "--mic-index",
            str(mic_index),
        ]
        # Set working directory and inherit environment to ensure proper module loading
        process = subprocess.Popen(cmd, cwd=Path.cwd(), env=os.environ.copy())
        # Store process in session state for monitoring
        st.session_state.transcription_process = process
        return process
    except Exception as e:
        st.error(f"Failed to start transcription: {e}")
        return None


def clear_transcription_file():
    """Clear the contents of the transcription file for data protection"""
    try:
        # Opening in 'w' mode truncates the file
        with Path("temp/transcription_output.txt").open("w") as file:
            pass
        # Also clear any stop signal files
        stop_signal_file = Path("stop_signal.txt")
        if stop_signal_file.exists():
            stop_signal_file.unlink()
    except Exception as e:
        # Silently handle errors to avoid breaking the app
        pass


def cleanup_transcription_data():
    """Comprehensive cleanup of all transcription-related data for data protection"""
    try:
        # Clear transcription file
        clear_transcription_file()
        
        # Clean up any temporary session state data
        keys_to_remove = []
        for key in st.session_state.keys():
            if 'transcription_editor' in key or 'transcribing' in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
            
    except Exception as e:
        # Silently handle errors to avoid breaking the app
        pass


def load_transcription():
    try:
        transcription_file = Path("temp/transcription_output.txt")
        if transcription_file.exists() and transcription_file.stat().st_size > 0:
            with transcription_file.open("r", encoding="utf-8") as file:
                content = file.read().strip()
                return content if content else ""
        return ""
    except Exception as e:
        st.error(f"Error reading transcription file: {e}")
        return ""


def load_transcription_with_formatting(show_relative=False):
    """Load transcription and format it for display with timestamps"""
    try:
        transcription_file = Path("temp/transcription_output.txt")
        if transcription_file.exists() and transcription_file.stat().st_size > 0:
            with transcription_file.open("r", encoding="utf-8") as file:
                content = file.read().strip()
                
                if not content or content == "Model loaded & listening":
                    return "", ""
                
                # Split into timestamped and plain text sections
                if "=== TIMESTAMPED TRANSCRIPTION ===" in content:
                    parts = content.split("=== TIMESTAMPED TRANSCRIPTION ===")
                    if len(parts) > 1:
                        timestamped_section = parts[1].split("=== PLAIN TEXT ===")[0].strip()
                        
                        # Format timestamped content for better display
                        formatted_content = format_timestamped_content(timestamped_section, show_relative)
                        
                        # Get plain text for editing
                        if "=== PLAIN TEXT ===" in content:
                            plain_text = content.split("=== PLAIN TEXT ===")[1].strip()
                        else:
                            plain_text = timestamped_section
                        
                        return formatted_content, plain_text
                
                return content, content
        
        return "", ""
    except Exception as e:
        st.error(f"Error reading transcription file: {e}")
        return "", ""


def format_timestamped_content(timestamped_text, show_relative=False):
    """Format timestamped content for better UI display"""
    if not timestamped_text:
        return ""
    
    lines = timestamped_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line and line.startswith('['):
            # Parse timestamp format: [HH:MM:SS] [0.0s] Text
            try:
                # Find the end of timestamps
                parts = line.split('] ', 2)  # Split on first two '] ' occurrences
                if len(parts) >= 3:
                    real_time = parts[0][1:]  # Remove opening [
                    relative_time = parts[1][1:]  # Remove opening [
                    text = parts[2]
                    
                    # Create styled timestamp line with optional relative time
                    if show_relative:
                        formatted_line = f"""
                        <div style="margin-bottom: 8px;">
                            <span style="color: #0066cc; font-weight: bold; font-size: 12px;">[{real_time}]</span>
                            <span style="color: #666; font-size: 11px; margin-left: 5px;">[{relative_time}]</span>
                            <span style="margin-left: 10px;">{text}</span>
                        </div>
                        """
                    else:
                        formatted_line = f"""
                        <div style="margin-bottom: 8px;">
                            <span style="color: #0066cc; font-weight: bold; font-size: 12px;">[{real_time}]</span>
                            <span style="margin-left: 10px;">{text}</span>
                        </div>
                        """
                    formatted_lines.append(formatted_line)
                else:
                    formatted_lines.append(f"<div style='margin-bottom: 5px;'>{line}</div>")
            except:
                formatted_lines.append(f"<div style='margin-bottom: 5px;'>{line}</div>")
    
    return ''.join(formatted_lines)


def check_model_ready():
    """Check if the model is ready by looking for the 'Model loaded & listening' message"""
    try:
        transcription_file = Path("temp/transcription_output.txt")
        if transcription_file.exists() and transcription_file.stat().st_size > 0:
            with transcription_file.open("r", encoding="utf-8") as file:
                content = file.read()
                return "Model" in content and "loaded & listening" in content
        return False
    except Exception:
        return False


def get_timestamped_text_for_editing(show_relative=False):
    """Get timestamped transcription in a format suitable for editing"""
    try:
        transcription_file = Path("temp/transcription_output.txt")
        if transcription_file.exists() and transcription_file.stat().st_size > 0:
            with transcription_file.open("r", encoding="utf-8") as file:
                content = file.read().strip()
                
                # Extract timestamped section
                if "=== TIMESTAMPED TRANSCRIPTION ===" in content:
                    parts = content.split("=== TIMESTAMPED TRANSCRIPTION ===")
                    if len(parts) > 1:
                        timestamped_section = parts[1].split("=== PLAIN TEXT ===")[0].strip()
                        
                        # If user doesn't want relative timestamps, remove them
                        if not show_relative:
                            formatted_lines = []
                            for line in timestamped_section.split('\n'):
                                line = line.strip()
                                if line and line.startswith('['):
                                    # Parse and reconstruct without relative timestamp
                                    try:
                                        parts = line.split('] ', 2)
                                        if len(parts) >= 3:
                                            real_time = parts[0][1:]  # Remove opening [
                                            text = parts[2]
                                            formatted_lines.append(f"[{real_time}] {text}")
                                        else:
                                            formatted_lines.append(line)
                                    except:
                                        formatted_lines.append(line)
                                elif line:  # Non-empty line that doesn't start with [
                                    formatted_lines.append(line)
                            return '\n'.join(formatted_lines)
                        else:
                            return timestamped_section
                
        return ""
    except Exception as e:
        st.error(f"Error reading timestamped transcription: {e}")
        return ""


def upload_to_experiment(transcript_content, include_timestamps=False):
    """Upload transcript to experiment using append_to_experiment function"""
    try:
        # Check if we have the required session state variables
        if not hasattr(st.session_state, 'api_client'):
            st.error("❌ No API client found. Please ensure you're logged in to eLabFTW.")
            return False
        
        if not hasattr(st.session_state, 'exp_id'):
            st.error("❌ No experiment selected. Please select an experiment first.")
            return False
        
        if not hasattr(st.session_state, 'exp_name'):
            st.error("❌ No experiment name found. Please select an experiment first.")
            return False
        
        # Upload transcript to experiment
        with st.spinner("Uploading transcript to experiment..."):
            # Format the transcript with appropriate header
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if include_timestamps and transcript_content.strip():
                # Check if content already has timestamps
                if '[' in transcript_content and ']' in transcript_content:
                    formatted_transcript = f"""**Transcription with Timestamps - {timestamp_str}**

{transcript_content}

---
*Transcription captured with real-time and relative timestamps*"""
                else:
                    # Fallback to plain text
                    formatted_transcript = f"""**Transcription - {timestamp_str}**

{transcript_content}"""
            else:
                formatted_transcript = f"""**Transcription - {timestamp_str}**

{transcript_content}"""
            
            # Use the append_to_experiment function
            append_to_experiment(st.session_state.api_client, st.session_state.exp_id, formatted_transcript)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error uploading to experiment: {str(e)}")
        return False


def transcription_widget(key_suffix="", on_upload_callback=None, compact_mode=False):
    """
    Reusable transcription widget for voice-to-text transcription
    
    Args:
        key_suffix: Suffix for session state keys to avoid conflicts
        on_upload_callback: Function to call after successful upload (receives transcript_text, include_timestamps)
        compact_mode: If True, shows simplified interface
    """
    import speech_recognition as sr
    
    # Initialize transcription states with suffix
    transcribing_key = f"transcribing{key_suffix}"
    model_loading_key = f"model_loading{key_suffix}"
    model_ready_key = f"model_ready{key_suffix}"
    widget_initialized_key = f"widget_initialized{key_suffix}"
    
    # Auto-cleanup for data protection when widget is first initialized
    if widget_initialized_key not in st.session_state:
        cleanup_transcription_data()
        st.session_state[widget_initialized_key] = True
    
    if transcribing_key not in st.session_state:
        st.session_state[transcribing_key] = False
    if model_loading_key not in st.session_state:
        st.session_state[model_loading_key] = False
    if model_ready_key not in st.session_state:
        st.session_state[model_ready_key] = False
    
    # Display options
    if not compact_mode:
        st.markdown("**🎤 Real-Time Transcription**")
        st.sidebar.markdown("### Display Options")
        show_timestamps = st.sidebar.checkbox("Show timestamps", value=True, help="Display real-time and relative timestamps with transcription", key=f"show_ts{key_suffix}")
        show_relative_timestamps = st.sidebar.checkbox("Show relative timestamps", value=False, help="Show relative time from start of recording (in addition to real time)", key=f"show_rel_ts{key_suffix}")
    else:
        st.markdown("**🎤 Quick Voice Transcription**")
        col_opt1, col_opt2 = st.columns([1, 1])
        with col_opt1:
            show_timestamps = st.checkbox("Show timestamps", value=True, key=f"show_ts{key_suffix}")
        with col_opt2:
            show_relative_timestamps = st.checkbox("Show relative timestamps", value=False, key=f"show_rel_ts{key_suffix}")
    
    # Controls
    col1, col2 = st.columns([1, 2] if compact_mode else [1, 3])
    
    with col1:
        # Model selection
        model = st.selectbox("Choose a model", ["tiny", "base", "small", "medium"], index=2, key=f"trans_model{key_suffix}")
        
        # Microphone selection
        try:
            mics = [(i, name) for i, name in enumerate(sr.Microphone.list_microphone_names())]
            mic_index = st.selectbox("Microphone", options=mics, format_func=lambda x: x[1], key=f"trans_mic{key_suffix}")[0]
        except:
            mic_index = 0
            st.warning("⚠️ Could not detect microphones")
        
        if not compact_mode:
            energy_threshold = st.slider("Energy Threshold", min_value=100, max_value=500, value=300, key=f"energy{key_suffix}")
            record_timeout = st.slider("Record Timeout (s)", min_value=1.0, max_value=10.0, value=3.0, key=f"record{key_suffix}")
            phrase_timeout = st.slider("Phrase Timeout (s)", min_value=5.0, max_value=30.0, value=15.0, key=f"phrase{key_suffix}")
        else:
            energy_threshold = 300
            record_timeout = 3.0
            phrase_timeout = 15.0
    
    with col2:
        # Transcription buttons - same logic as main app
        if not st.session_state[transcribing_key] and not st.session_state[model_loading_key]:
            if st.button("🎤 Start Transcribing", type="primary", key=f"start_trans{key_suffix}"):
                st.session_state[transcribing_key] = True
                st.session_state[model_loading_key] = True
                st.session_state[model_ready_key] = False
                clear_transcription_file()
                start_transcription(model, energy_threshold, record_timeout, phrase_timeout, mic_index)
                st.rerun()
        elif st.session_state[model_loading_key]:
            st.button("⏳ Loading Model...", disabled=True, key=f"loading_trans{key_suffix}")
        else:
            if st.button("⏹️ Stop Transcribing", type="secondary", key=f"stop_trans{key_suffix}"):
                st.session_state[transcribing_key] = False
                st.session_state[model_loading_key] = False
                st.session_state[model_ready_key] = False
                send_stop_signal()
                
                # Same stopping logic as main app
                with st.spinner("Stopping transcription and processing final audio..."):
                    transcription_file = Path("temp/transcription_output.txt")
                    initial_content = load_transcription()
                    
                    max_wait_time = 15
                    check_interval = 0.3
                    wait_time = 0
                    content_stable_time = 0
                    last_content = initial_content
                    
                    while wait_time < max_wait_time:
                        time.sleep(check_interval)
                        wait_time += check_interval
                        
                        current_content = load_transcription()
                        
                        if current_content != last_content:
                            last_content = current_content
                            content_stable_time = 0
                        else:
                            content_stable_time += check_interval
                        
                        process_terminated = False
                        if hasattr(st.session_state, 'transcription_process'):
                            try:
                                poll_result = st.session_state.transcription_process.poll()
                                if poll_result is not None:
                                    process_terminated = True
                            except:
                                process_terminated = True
                        
                        stop_signal_gone = not Path("stop_signal.txt").exists()
                        
                        if ((process_terminated and content_stable_time >= 1.0) or 
                            (stop_signal_gone and content_stable_time >= 2.0) or 
                            (content_stable_time >= 5.0)):
                            break
                    
                    time.sleep(0.5)
                
                final_content = load_transcription()
                if final_content and final_content != initial_content:
                    st.success("⏹️ Transcription stopped! Final content saved.")
                elif final_content:
                    st.success("⏹️ Transcription stopped!")
                else:
                    st.success("⏹️ Transcription stopped!")
                
                if hasattr(st.session_state, 'transcription_process'):
                    del st.session_state.transcription_process
                
                st.rerun()
    
    # Status display
    if st.session_state[transcribing_key]:
        if st.session_state[model_loading_key]:
            with st.spinner("Loading Whisper model..."):
                st.warning("🔄 Loading Whisper model... This may take a few seconds.")
                if not compact_mode:
                    st.caption("⏱️ Estimated loading time: 5-30 seconds depending on model size")
        elif st.session_state[model_ready_key]:
            st.success("✅ Model ready - Transcription is active")
        else:
            st.info("🎤 Transcription starting...")
    
    # Real-time transcription display - same as main app
    if st.session_state[transcribing_key]:
        if st.session_state[model_ready_key]:
            st.info("🎤 Transcription is running... Speak into your microphone.")
        elif st.session_state[model_loading_key]:
            st.warning("⏳ Loading Whisper model... Please wait, this may take up to 30 seconds.")
        else:
            st.info("🎤 Transcription starting...")
        
        # Control section
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🔄 Refresh Now", key=f"refresh{key_suffix}"):
                pass
        
        with col2:
            auto_refresh = st.checkbox("🔄 Auto-refresh (3s)", value=True, help="Automatically refresh content every 3 seconds", key=f"auto_refresh{key_suffix}")
        
        # Create placeholders for dynamic content
        content_placeholder = st.empty()
        
        # Auto-refresh loop - same as main app
        if auto_refresh:
            for i in range(100):
                if not st.session_state[model_ready_key] and check_model_ready():
                    st.session_state[model_ready_key] = True
                    st.session_state[model_loading_key] = False
                    st.rerun()
                
                if show_timestamps:
                    transcription_content, _ = load_transcription_with_formatting(show_relative_timestamps)
                else:
                    transcription_content = load_transcription()
                
                with content_placeholder.container():
                    if show_timestamps:
                        formatted_content, plain_content = load_transcription_with_formatting(show_relative_timestamps)
                        if formatted_content:
                            st.markdown("**📝 Live Transcription with Timestamps:**")
                            st.markdown(f"""
                            <div style="background-color: #2e2e2e; padding: 15px; border-radius: 5px; border: 1px solid #555; max-height: 400px; overflow-y: auto; font-family: 'Segoe UI', sans-serif;">
                                {formatted_content}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if show_relative_timestamps:
                                st.caption("🕐 Blue timestamps show real time | Gray timestamps show relative time from start")
                            else:
                                st.caption("🕐 Blue timestamps show real time")
                        else:
                            if st.session_state[model_ready_key]:
                                st.info("Waiting for speech... 🎯\n\nMake sure to speak clearly and check your microphone is working")
                    else:
                        transcription_content = load_transcription()
                        if transcription_content and "=== PLAIN TEXT ===" in transcription_content:
                            plain_text = transcription_content.split("=== PLAIN TEXT ===")[1].strip()
                            if plain_text:
                                st.markdown("**📝 Live Transcription:**")
                                st.markdown(f"""
                                <div style="background-color: #2e2e2e; padding: 15px; border-radius: 5px; border: 1px solid #555; max-height: 400px; overflow-y: auto; font-family: monospace;">
                                    <pre style="white-space: pre-wrap; margin: 0; font-size: 14px; color: #ffffff; background-color: transparent;">{plain_text}</pre>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                if st.session_state[model_ready_key]:
                                    st.info("Waiting for speech... 🎯")
                        else:
                            if st.session_state[model_ready_key]:
                                st.info("Waiting for speech... 🎯")

                time.sleep(3)
                
                if not st.session_state[transcribing_key]:
                    break
        else:
            # Manual refresh mode
            if not st.session_state[model_ready_key] and check_model_ready():
                st.session_state[model_ready_key] = True
                st.session_state[model_loading_key] = False
                st.rerun()
            
            if show_timestamps:
                transcription_content, _ = load_transcription_with_formatting(show_relative_timestamps)
            else:
                transcription_content = load_transcription()
            
            with content_placeholder.container():
                if show_timestamps:
                    formatted_content, plain_content = load_transcription_with_formatting(show_relative_timestamps)
                    if formatted_content:
                        st.markdown("**📝 Live Transcription with Timestamps:**")
                        st.markdown(f"""
                        <div style="background-color: #2e2e2e; padding: 15px; border-radius: 5px; border: 1px solid #555; max-height: 400px; overflow-y: auto; font-family: 'Segoe UI', sans-serif;">
                            {formatted_content}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if show_relative_timestamps:
                            st.caption("🕐 Blue timestamps show real time | Gray timestamps show relative time from start")
                        else:
                            st.caption("🕐 Blue timestamps show real time")
                    else:
                        if st.session_state[model_ready_key]:
                            st.info("Waiting for speech... 🎯\n\nMake sure to speak clearly and check your microphone is working")
                else:
                    transcription_content = load_transcription()
                    if transcription_content and "=== PLAIN TEXT ===" in transcription_content:
                        plain_text = transcription_content.split("=== PLAIN TEXT ===")[1].strip()
                        if plain_text:
                            st.markdown("**📝 Live Transcription:**")
                            st.markdown(f"""
                            <div style="background-color: #2e2e2e; padding: 15px; border-radius: 5px; border: 1px solid #555; max-height: 400px; overflow-y: auto; font-family: monospace;">
                                <pre style="white-space: pre-wrap; margin: 0; font-size: 14px; color: #ffffff; background-color: transparent;">{plain_text}</pre>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            if st.session_state[model_ready_key]:
                                st.info("Waiting for speech... 🎯")
                    else:
                        if st.session_state[model_ready_key]:
                            st.info("Waiting for speech... 🎯")

    # Display final transcription results (when not recording) - same as main app
    if not st.session_state[transcribing_key]:
        transcription_content = load_transcription()
        if transcription_content:
            st.markdown("**📄 Previous Transcription:**")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                include_timestamps = st.checkbox("Include timestamps in upload", value=True, help="Include timing information with the transcription", key=f"include_ts_upload{key_suffix}")
                
                formatted_content, plain_content = load_transcription_with_formatting(show_relative_timestamps)
                
                if include_timestamps and formatted_content:
                    display_content = get_timestamped_text_for_editing(show_relative_timestamps)
                    edited_content = st.text_area(
                        "Edit Transcription (with timestamps)",
                        value=display_content,
                        height=300,
                        help="Edit the transcription with timestamps before uploading. Format: [HH:MM:SS] [Xs] Text" if show_relative_timestamps else "Edit the transcription with timestamps before uploading. Format: [HH:MM:SS] Text",
                        key=f"transcription_editor{key_suffix}"
                    )
                else:
                    edited_content = st.text_area(
                        "Edit Transcription (plain text)",
                        value=plain_content,
                        height=300,
                        help="Edit the plain text version of the transcription before uploading",
                        key=f"transcription_editor{key_suffix}"
                    )
            
            with col2:
                st.markdown("**Actions:**")
                
                # Upload section
                st.markdown("**Upload to eLabFTW:**")
                
                confirmation_key = f"upload_confirmation_pending{key_suffix}"
                if confirmation_key not in st.session_state:
                    st.session_state[confirmation_key] = False
                
                if hasattr(st.session_state, 'exp_name') and hasattr(st.session_state, 'exp_id'):
                    st.info(f"📊 Selected: **{st.session_state.exp_name}**")
                    
                    if st.session_state[confirmation_key]:
                        st.warning("⚠️ **Confirm Upload**")
                        
                        col_confirm1, col_confirm2 = st.columns(2)
                        
                        with col_confirm1:
                            if st.button("✅ Yes", type="primary", key=f"confirm_upload{key_suffix}"):
                                success = upload_to_experiment(edited_content, include_timestamps)
                                if success:
                                    st.success("✅ Uploaded!")
                                    
                                    if on_upload_callback:
                                        on_upload_callback(edited_content, include_timestamps)
                                    
                                    clear_transcription_file()
                                    st.info("🗑️ Data cleared.")
                                
                                st.session_state[confirmation_key] = False
                                st.rerun()
                        
                        with col_confirm2:
                            if st.button("❌ Cancel", type="secondary", key=f"cancel_upload{key_suffix}"):
                                st.session_state[confirmation_key] = False
                                st.rerun()
                    else:
                        if st.button("🧪 Upload", type="primary", key=f"upload_to_exp{key_suffix}"):
                            st.session_state[confirmation_key] = True
                            st.rerun()
                else:
                    st.warning("⚠️ No experiment selected.")
                
                # Clear button
                if st.button("🗑️ Clear", key=f"clear_trans{key_suffix}"):
                    clear_transcription_file()
                    st.rerun()
