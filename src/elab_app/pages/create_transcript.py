import os
import subprocess
import sys
import tempfile
import time
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
from utils import append_to_experiment
from auth import ELAB_HOST
from components.hashtag_textarea import hashtag_textarea

_TEMP_DIR = Path(tempfile.gettempdir()) / "elab_app"
_TEMP_DIR.mkdir(exist_ok=True)

_BASE_URL = ELAB_HOST.replace('/api/v2', '')

hide_stale_elements = """
<style>
div[data-stale="true"] {
    display: none !important;
}
</style>
"""


def send_stop_signal():
    with (_TEMP_DIR / "stop_signal.txt").open("w") as f:
        print("Sending stop signal")
        f.write("stop")


def save_default_microphone(mic_tuple, key_suffix=""):
    """Save default microphone setting to local file"""
    try:
        # Load existing settings or create new
        settings_file = _TEMP_DIR / "default_microphone.json"
        settings = {}
        
        if settings_file.exists():
            try:
                with settings_file.open("r", encoding="utf-8") as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, Exception):
                settings = {}
        
        # Save microphone setting with key_suffix for different contexts
        settings[f"default_mic{key_suffix}"] = {
            "mic_id": mic_tuple[0],
            "mic_name": mic_tuple[1],
            "saved_at": datetime.now().isoformat()
        }
        
        # Write settings back to file
        with settings_file.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            
        return True
    except Exception:
        # Silently handle errors to avoid breaking the app
        return False


def load_default_microphone(key_suffix=""):
    """Load default microphone setting from local file"""
    try:
        settings_file = _TEMP_DIR / "default_microphone.json"
        if not settings_file.exists():
            return None
            
        with settings_file.open("r", encoding="utf-8") as f:
            settings = json.load(f)
            
        setting_key = f"default_mic{key_suffix}"
        if setting_key in settings:
            mic_data = settings[setting_key]
            return (mic_data["mic_id"], mic_data["mic_name"])
            
        return None
    except Exception:
        return None


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
        with (_TEMP_DIR / "transcription_output.txt").open("w"):
            pass
        # Also clear any stop signal files
        stop_signal_file = _TEMP_DIR / "stop_signal.txt"
        if stop_signal_file.exists():
            stop_signal_file.unlink()
    except Exception:
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
            if isinstance(key, str) and ('transcription_editor' in key or 'transcribing' in key):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
            
    except Exception:
        # Silently handle errors to avoid breaking the app
        pass


def load_transcription():
    try:
        transcription_file = _TEMP_DIR / "transcription_output.txt"
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
        transcription_file = _TEMP_DIR / "transcription_output.txt"
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
                        formatted_line = f"""<div style="margin-bottom: 8px;">
                            <span style="color: #0066cc; font-weight: bold; font-size: 12px;">[{real_time}]</span>
                            <span style="color: #666; font-size: 11px; margin-left: 5px;">[{relative_time}]</span>
                            <span style="margin-left: 10px; color: #ffffff;">{text}</span>
                        </div>"""
                    else:
                        formatted_line = f"""<div style="margin-bottom: 8px;">
                            <span style="color: #0066cc; font-weight: bold; font-size: 12px;">[{real_time}]</span>
                            <span style="margin-left: 10px; color: #ffffff;">{text}</span>
                        </div>"""
                    formatted_lines.append(formatted_line)
                else:
                    formatted_lines.append(f"<div style='margin-bottom: 5px; color: #ffffff;'>{line}</div>")
            except Exception:
                formatted_lines.append(f"<div style='margin-bottom: 5px; color: #ffffff;'>{line}</div>")
    
    # Return properly wrapped content without extra closing tags
    return ''.join(formatted_lines)


def check_model_ready():
    """Check if the model is ready by looking for the 'Model loaded & listening' message"""
    try:
        transcription_file = _TEMP_DIR / "transcription_output.txt"
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
        transcription_file = _TEMP_DIR / "transcription_output.txt"
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
                                    except Exception:
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
    """Upload transcript to experiment or item using append_to_experiment function"""
    try:
        # Check if we have the required session state variables
        if not hasattr(st.session_state, 'api_client'):
            st.error("❌ No API client found. Please ensure you're logged in to eLabFTW.")
            return False

        if not hasattr(st.session_state, 'exp_id'):
            st.error("❌ No entry selected. Please select an experiment or resource first.")
            return False

        if not hasattr(st.session_state, 'exp_name'):
            st.error("❌ No entry name found. Please select an experiment or resource first.")
            return False

        entity_type = st.session_state.get('entity_type', 'experiments')
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'

        # Upload transcript to entry
        with st.spinner("Uploading transcript to %s..." % entry_label):
            if include_timestamps and transcript_content.strip():
                # Parse timestamped transcription and upload each block separately
                if '[' in transcript_content and ']' in transcript_content:
                    lines = transcript_content.strip().split('\n')
                    any_ok = False
                    for line in lines:
                        line = line.strip()
                        if not line or not line.startswith('['):
                            continue

                        # Parse timestamp format: [HH:MM:SS] Text or [HH:MM:SS] [Xs] Text
                        try:
                            # Find first closing bracket
                            first_bracket_end = line.index(']')
                            time_str = line[1:first_bracket_end]  # Extract HH:MM:SS

                            # Extract text (skip relative time if present)
                            remaining = line[first_bracket_end + 1:].strip()
                            if remaining.startswith('['):
                                # Has relative timestamp, skip it
                                second_bracket_end = remaining.index(']')
                                text = remaining[second_bracket_end + 1:].strip()
                            else:
                                text = remaining

                            if not text:
                                continue

                            # Convert [HH:MM:SS] to full datetime format: YYYY-MM-DD HH:MM:SS.
                            today = datetime.now().date()
                            time_parts = time_str.split(':')
                            if len(time_parts) == 3:
                                hours, minutes, seconds = map(int, time_parts)
                                full_datetime = datetime.combine(today, datetime.min.time().replace(hour=hours, minute=minutes, second=seconds))
                                formatted_timestamp = full_datetime.strftime('%Y-%m-%dT%H:%M:%S')

                                # Upload with custom timestamp
                                if append_to_experiment(st.session_state.api_client, st.session_state.exp_id, text, custom_timestamp=formatted_timestamp, entity_type=entity_type, initials=st.session_state.get('initials', '')):
                                    any_ok = True

                        except (ValueError, IndexError):
                            # If parsing fails, skip this line
                            continue
                    return any_ok
                else:
                    # No timestamps found, upload as plain text with current timestamp
                    return append_to_experiment(st.session_state.api_client, st.session_state.exp_id, transcript_content, entity_type=entity_type, initials=st.session_state.get('initials', ''))
            else:
                # Upload plain text with current timestamp (default behavior)
                return append_to_experiment(st.session_state.api_client, st.session_state.exp_id, transcript_content, entity_type=entity_type, initials=st.session_state.get('initials', ''))

    except Exception as e:
        st.error(f"❌ Error uploading to experiment: {str(e)}")
        return False


def transcription_widget(key_suffix="", on_upload_callback=None, compact_mode=False):
    """
    Reusable transcription widget for voice-to-text transcription.

    Args:
        key_suffix: Suffix for session state keys to avoid conflicts.
        on_upload_callback: Called after successful upload (receives text, use_timestamps).
        compact_mode: If True, shows simplified interface.
    """
    _TEMP_DIR.mkdir(exist_ok=True)

    try:
        import speech_recognition as sr
    except ImportError:
        st.info(
            "🎤 Voice transcription is not available on this installation.\n\n"
            "To enable it, reinstall with the transcription extra:\n\n"
            "```\nuv tool install \"elab-app[transcription]\"\n```"
        )
        return

    # ── Session state keys ────────────────────────────────────────────────────
    transcribing_key      = f"transcribing{key_suffix}"
    model_loading_key     = f"model_loading{key_suffix}"
    model_ready_key       = f"model_ready{key_suffix}"
    widget_initialized_key = f"widget_initialized{key_suffix}"
    use_timestamps_key    = f"use_timestamps{key_suffix}"
    ed_reset_key          = f"transcript_editor_reset{key_suffix}"

    if widget_initialized_key not in st.session_state:
        cleanup_transcription_data()
        st.session_state[widget_initialized_key] = True

    for key, default in [
        (transcribing_key,  False),
        (model_loading_key, False),
        (model_ready_key,   False),
        (use_timestamps_key, False),
        (ed_reset_key,      0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if not compact_mode:
        st.markdown("**🎤 Real-Time Transcription**")
    else:
        st.markdown("**🎤 Quick Voice Transcription**")

    # ── Setup controls ────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2] if compact_mode else [1, 3])

    with col1:
        model = st.selectbox(
            "Choose a model", ["tiny", "base", "small", "medium"],
            index=2, key=f"trans_model{key_suffix}",
        )

        try:
            all_mics = sr.Microphone.list_microphone_names()
            filtered_mics = []
            seen_names = set()
            for i, name in enumerate(all_mics):
                name_lower = name.lower()
                if any(kw in name_lower for kw in [
                    'speaker', 'output', 'playback', 'hdmi', 'display',
                    'lautsprecher', 'ausgabe', 'wiedergabe', 'anzeige', 'kopfhörer',
                ]):
                    continue
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    filtered_mics.append((i, name))
            if not filtered_mics:
                filtered_mics = [(i, name) for i, name in enumerate(all_mics)]

            default_mic_key = f"default_microphone{key_suffix}"
            default_index = 0
            file_default = load_default_microphone(key_suffix)
            if file_default:
                st.session_state[default_mic_key] = file_default
                saved_default = file_default
            else:
                saved_default = st.session_state.get(default_mic_key)
            if saved_default:
                for idx, (mic_id, mic_name) in enumerate(filtered_mics):
                    if mic_name == saved_default[1]:
                        default_index = idx
                        break

            selected_mic = st.selectbox(
                "Microphone", options=filtered_mics, index=default_index,
                format_func=lambda x: x[1], key=f"trans_mic{key_suffix}",
            )
            mic_index = selected_mic[0]

            if st.button("📌 Set as Default", key=f"set_default_mic{key_suffix}",
                         help="Set this microphone as default"):
                st.session_state[default_mic_key] = selected_mic
                if save_default_microphone(selected_mic, key_suffix):
                    st.success("✅ Default set and saved!")
                else:
                    st.success("✅ Default set for this session!")
                st.rerun()

            if default_mic_key in st.session_state:
                dm = st.session_state[default_mic_key]
                label = "📌 Default (saved)" if file_default and file_default == dm else "📌 Default"
                st.caption(f"{label}: {dm[1]}")

        except Exception:
            mic_index = 0
            st.warning("⚠️ Could not detect microphones - using default")

        if not compact_mode:
            energy_threshold = st.slider("Energy Threshold", 100, 500, 150, key=f"energy{key_suffix}")
            record_timeout   = st.slider("Record Timeout (s)", 10.0, 120.0, 60.0, key=f"record{key_suffix}",
                                         help="Maximum duration before processing")
            phrase_timeout   = st.slider("Phrase Timeout (s)", 3.0, 30.0, 7.0, key=f"phrase{key_suffix}",
                                         help="Pause duration that triggers processing")
        else:
            energy_threshold, record_timeout, phrase_timeout = 150, 60.0, 7.0

    with col2:
        # Timestamps checkbox — only shown while not recording
        if not st.session_state[transcribing_key]:
            st.session_state[use_timestamps_key] = st.checkbox(
                "Add timestamps",
                value=st.session_state[use_timestamps_key],
                help="Automatically break up the transcript by segment, each with a real-time timestamp",
                key=f"use_ts_checkbox{key_suffix}",
            )

        # Start / Stop button
        if not st.session_state[transcribing_key] and not st.session_state[model_loading_key]:
            if st.button("🎤 Start Transcribing", type="primary", key=f"start_trans{key_suffix}"):
                st.session_state[transcribing_key]  = True
                st.session_state[model_loading_key] = True
                st.session_state[model_ready_key]   = False
                clear_transcription_file()
                # Reset editor so it picks up the fresh recording on next stop
                st.session_state[ed_reset_key] = st.session_state[ed_reset_key] + 1
                start_transcription(model, energy_threshold, record_timeout, phrase_timeout, mic_index)
                st.rerun()
        elif st.session_state[model_loading_key]:
            st.button("⏳ Loading Model...", disabled=True, key=f"loading_trans{key_suffix}")
        else:
            if st.button("⏹️ Stop Transcribing", type="secondary", key=f"stop_trans{key_suffix}"):
                st.session_state[transcribing_key]  = False
                st.session_state[model_loading_key] = False
                st.session_state[model_ready_key]   = False
                send_stop_signal()

                with st.spinner("Stopping transcription and processing final audio..."):
                    initial_content = load_transcription()
                    max_wait_time, check_interval = 15, 0.3
                    wait_time = content_stable_time = 0
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
                                if st.session_state.transcription_process.poll() is not None:
                                    process_terminated = True
                            except Exception:
                                process_terminated = True
                        stop_signal_gone = not (_TEMP_DIR / "stop_signal.txt").exists()
                        if ((process_terminated and content_stable_time >= 1.0) or
                                (stop_signal_gone and content_stable_time >= 2.0) or
                                (content_stable_time >= 5.0)):
                            break
                    time.sleep(0.5)

                if hasattr(st.session_state, 'transcription_process'):
                    del st.session_state.transcription_process

                # Increment reset_key so the editor remounts with the new content
                st.session_state[ed_reset_key] = st.session_state[ed_reset_key] + 1
                st.rerun()

    # ── Status display ────────────────────────────────────────────────────────
    if st.session_state[transcribing_key]:
        if st.session_state[model_loading_key]:
            st.warning("🔄 Loading Whisper model... This may take a few seconds.")
            if not compact_mode:
                st.caption("⏱️ Estimated loading time: 5-30 seconds depending on model size")
        elif st.session_state[model_ready_key]:
            st.success("✅ Model ready - Transcription is active")
        else:
            st.info("🎤 Transcription starting...")

    # ── Live display while recording ──────────────────────────────────────────
    if st.session_state[transcribing_key]:
        use_ts = st.session_state[use_timestamps_key]
        col_r1, col_r2 = st.columns([1, 2])
        with col_r1:
            if st.button("🔄 Refresh Now", key=f"refresh{key_suffix}"):
                pass
        with col_r2:
            auto_refresh = st.checkbox("🔄 Auto-refresh (3s)", value=True, key=f"auto_refresh{key_suffix}")

        content_placeholder = st.empty()

        def _show_live():
            if use_ts:
                formatted_content, _ = load_transcription_with_formatting(False)
                if formatted_content:
                    st.markdown("**📝 Live Transcription with Timestamps:**")
                    st.markdown(
                        f'<div style="background-color:#2e2e2e;padding:15px;border-radius:5px;'
                        f'border:1px solid #555;max-height:400px;overflow-y:auto;'
                        f'font-family:\'Segoe UI\',sans-serif;">{formatted_content}</div>',
                        unsafe_allow_html=True,
                    )
                elif st.session_state[model_ready_key]:
                    st.info("Waiting for speech... 🎯\n\nSpeak clearly and check your microphone.")
            else:
                raw = load_transcription()
                plain = raw.split("=== PLAIN TEXT ===")[1].strip() if "=== PLAIN TEXT ===" in raw else ""
                if plain:
                    st.markdown("**📝 Live Transcription:**")
                    st.markdown(
                        f'<div style="background-color:#2e2e2e;padding:15px;border-radius:5px;'
                        f'border:1px solid #555;max-height:400px;overflow-y:auto;font-family:monospace;">'
                        f'<pre style="white-space:pre-wrap;margin:0;font-size:14px;color:#fff;'
                        f'background-color:transparent;">{plain}</pre></div>',
                        unsafe_allow_html=True,
                    )
                elif st.session_state[model_ready_key]:
                    st.info("Waiting for speech... 🎯")

        if auto_refresh:
            for _ in range(100):
                if not st.session_state[model_ready_key] and check_model_ready():
                    st.session_state[model_ready_key]   = True
                    st.session_state[model_loading_key] = False
                    st.rerun()
                with content_placeholder.container():
                    _show_live()
                time.sleep(3)
                if not st.session_state[transcribing_key]:
                    break
        else:
            if not st.session_state[model_ready_key] and check_model_ready():
                st.session_state[model_ready_key]   = True
                st.session_state[model_loading_key] = False
                st.rerun()
            with content_placeholder.container():
                _show_live()

    # ── Editing area (after recording) ────────────────────────────────────────
    if not st.session_state[transcribing_key]:
        raw = load_transcription()
        if raw:
            st.markdown("**📄 Transcription — edit, then Ctrl+Enter to upload:**")

            use_ts = st.session_state[use_timestamps_key]
            _, plain_content = load_transcription_with_formatting(False)
            initial_value = get_timestamped_text_for_editing(False) if use_ts else plain_content

            editor_result = hashtag_textarea(
                items=st.session_state.get('all_items', []),
                base_url=_BASE_URL,
                value=initial_value,
                placeholder="Edit transcription… (type # to link a resource, Ctrl+Enter to upload)",
                reset_key=st.session_state[ed_reset_key],
                key=f"hashtag_transcript{key_suffix}",
            )

            if editor_result and editor_result.get('submitted'):
                text_to_upload = editor_result['text']
                success = upload_to_experiment(text_to_upload, include_timestamps=use_ts)
                if success:
                    st.success("✅ Uploaded!")
                    if on_upload_callback:
                        on_upload_callback(text_to_upload, use_ts)
                    clear_transcription_file()
                    st.session_state[ed_reset_key] = st.session_state[ed_reset_key] + 1
                    st.rerun()
