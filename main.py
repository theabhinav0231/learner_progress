import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json # Needed for handling chat data if saving to CSV (though not fully implemented here)

# --- Configuration ---
UPLOAD_DIR = "uploaded_work_samples" # Directory to save uploaded files
SUBMISSIONS_FILE = "submissions.csv" # File to store submission records

# --- Helper Functions ---

def initialize_app():
    """Initializes the application state and necessary directories/files."""
    if not os.path.exists(UPLOAD_DIR):
        try:
            os.makedirs(UPLOAD_DIR)
        except OSError as e:
            st.error(f"Error creating upload directory: {e}")
            st.stop()

    if 'submissions_df' not in st.session_state:
        try:
            st.session_state.submissions_df = pd.read_csv(SUBMISSIONS_FILE)
            # Convert Timestamp column to datetime
            if 'Timestamp' in st.session_state.submissions_df.columns:
                st.session_state.submissions_df['Timestamp'] = pd.to_datetime(st.session_state.submissions_df['Timestamp'])
            
            # Ensure 'Chat' column exists and contains lists (handle potential loading issues)
            if 'Chat' not in st.session_state.submissions_df.columns:
                 st.session_state.submissions_df['Chat'] = [[] for _ in range(len(st.session_state.submissions_df))]
            else:
                 # Attempt to safely convert string representation back to list if needed
                 # This is fragile; proper serialization (like JSON) is better for file storage.
                 st.session_state.submissions_df['Chat'] = st.session_state.submissions_df['Chat'].apply(
                     lambda x: json.loads(x) if isinstance(x, str) and x.startswith('[') else x if isinstance(x, list) else []
                 )

        except FileNotFoundError:
            st.session_state.submissions_df = pd.DataFrame(columns=[
                "Timestamp", "Learner Name", "Module/Task", "Filename", "File Path", "Status", "Chat"
            ])
        except (pd.errors.EmptyDataError, KeyError, json.JSONDecodeError) as e:
             st.warning(f"Issue loading submissions or chat history ({e}), initializing fresh state.")
             st.session_state.submissions_df = pd.DataFrame(columns=[
                "Timestamp", "Learner Name", "Module/Task", "Filename", "File Path", "Status", "Chat"
            ])
        except Exception as e:
            st.error(f"Error loading submissions file: {e}")
            st.session_state.submissions_df = pd.DataFrame(columns=[
                "Timestamp", "Learner Name", "Module/Task", "Filename", "File Path", "Status", "Chat"
            ])

        # Ensure Chat column always contains lists after loading or initialization
        st.session_state.submissions_df['Chat'] = st.session_state.submissions_df['Chat'].apply(lambda x: x if isinstance(x, list) else [])


def save_submission_record(df):
    """Saves the submission DataFrame (excluding chat for CSV simplicity) to CSV."""
    try:
        # Create a copy excluding the 'Chat' column before saving to CSV
        df_to_save = df.drop(columns=['Chat'], errors='ignore')
        df_to_save.to_csv(SUBMISSIONS_FILE, index=False)
    except Exception as e:
        st.error(f"Error saving submission record to CSV: {e}")

def add_submission_to_state(timestamp, learner_name, module_task, filename, file_path, status="Submitted"):
    """Adds a new submission to the session state DataFrame."""
    new_submission = pd.DataFrame([{
        "Timestamp": timestamp,
        "Learner Name": learner_name,
        "Module/Task": module_task,
        "Filename": filename,
        "File Path": file_path,
        "Status": status,
        "Chat": [] # Initialize chat history as an empty list
    }])
    st.session_state.submissions_df = pd.concat(
        [st.session_state.submissions_df, new_submission],
        ignore_index=True
    )
    # Save the updated records (without chat) to CSV
    save_submission_record(st.session_state.submissions_df)


def add_chat_message(submission_index, author, message):
    """Adds a chat message to a specific submission in the session state."""
    if submission_index is not None and submission_index in st.session_state.submissions_df.index:
        message_entry = {
            "author": author,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # Append message to the list in the DataFrame cell
        st.session_state.submissions_df.loc[submission_index, 'Chat'].append(message_entry)
        # This change is only in session state, not saved to CSV by default.
    else:
        st.error("Could not add chat message: Invalid submission index.")


# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("🎓 Work Sample Submission Portal")
st.markdown("Upload your work samples here for progress verification.")

initialize_app()

# --- Submission Form ---
st.header("Submit Your Work")
with st.form("submission_form", clear_on_submit=True):
    learner_name = st.text_input("Enter Your Name:")
    available_modules = [
        "Module 1: Basic Wood Carving Techniques", "Module 2: Introduction to Pottery Wheel",
        "Task 3.1: Soldering Practice", "Project Alpha: Weaving Pattern Design",
        "Cultural Practice: Traditional Knot Tying - Step 1", "Other"
    ]
    selected_module_option = st.selectbox("Select the Module/Task:", available_modules)
    custom_module = ""
    if selected_module_option == "Other":
        custom_module = st.text_input("Please specify the Module/Task:")

    uploaded_file = st.file_uploader(
        "Upload your work sample (Image, Video, PDF, etc.):",
        type=None
    )
    submitted = st.form_submit_button("Submit Work Sample")

    if submitted:
        final_module = custom_module if selected_module_option == "Other" else selected_module_option
        if not learner_name:
            st.warning("Please enter your name.")
        elif not final_module:
            st.warning("Please select or specify the module/task.")
        elif uploaded_file is None:
            st.warning("Please upload a file.")
        else:
            try:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_learner_name = "".join(c if c.isalnum() else "_" for c in learner_name)
                safe_module_name = "".join(c if c.isalnum() else "_" for c in final_module[:20])
                original_filename = uploaded_file.name
                file_extension = os.path.splitext(original_filename)[1]
                unique_filename = f"{timestamp_str}_{safe_learner_name}_{safe_module_name}{file_extension}"
                save_path = os.path.join(UPLOAD_DIR, unique_filename)

                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                submission_time = datetime.now()
                add_submission_to_state(
                    timestamp=submission_time, learner_name=learner_name, module_task=final_module,
                    filename=original_filename, file_path=save_path, status="Submitted"
                )

                st.success(f"✅ Success! Your work '{original_filename}' for '{final_module}' has been submitted.")
                st.balloons()
                # No explicit rerun needed here due to form submission behavior

            except Exception as e:
                st.error(f"❌ An error occurred during submission: {e}")

# --- Display Submitted Work & Chat ---
st.divider()
st.header("📋 Submission History & Feedback")
st.markdown("_(Select a submission to view details, download the file, and add comments.)_")

if not st.session_state.submissions_df.empty:
    # Select submission
    st.subheader("Select Submission")
    
    # Modified format_func to handle both datetime and string timestamps
    def format_submission(x):
        row = st.session_state.submissions_df.loc[x]
        timestamp = row['Timestamp']
        
        # Format timestamp based on its type
        if isinstance(timestamp, pd.Timestamp) or isinstance(timestamp, datetime):
            formatted_time = timestamp.strftime('%Y-%m-%d %H:%M')
        else:
            # If it's still a string despite conversion attempts, just use it as is
            formatted_time = timestamp
            
        return f"[{formatted_time}] {row['Learner Name']} - {row['Module/Task']} ({row['Status']})"
    
    selected_submission_index = st.selectbox(
        "Select a submission:",
        st.session_state.submissions_df.index,
        format_func=format_submission,
        index=None, # Default to no selection
        placeholder="Choose a submission to view...",
        key="submission_selector" # Add key for stability
    )

    if selected_submission_index is not None:
        selected_row = st.session_state.submissions_df.loc[selected_submission_index]
        file_path_to_download = selected_row['File Path']
        original_filename = selected_row['Filename']

        # Display details and download in columns
        col1, col2 = st.columns([2,1]) # Give more space to details/preview

        with col1:
            st.subheader("Submission Details & Preview")
            st.write(f"**Learner:** {selected_row['Learner Name']}")
            st.write(f"**Module/Task:** {selected_row['Module/Task']}")
            
            # Display timestamp based on its type
            timestamp = selected_row['Timestamp']
            if isinstance(timestamp, pd.Timestamp) or isinstance(timestamp, datetime):
                st.write(f"**Submitted:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.write(f"**Submitted:** {timestamp}")
                
            st.write(f"**Status:** {selected_row['Status']}")
            st.write(f"**Original Filename:** {original_filename}")

            # Preview/Download button
            try:
                with open(file_path_to_download, "rb") as fp:
                    st.download_button(
                        label=f"Download '{original_filename}'",
                        data=fp,
                        file_name=original_filename,
                        mime=None
                    )
                # Optional: Display image/video previews
                file_ext = os.path.splitext(original_filename)[1].lower()
                if file_ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    st.image(file_path_to_download, caption=f"Preview: {original_filename}", use_column_width=True)
                elif file_ext in ['.mp4', '.mov', '.avi', '.webm']:
                    st.video(file_path_to_download)
                # Add more preview types if needed

            except FileNotFoundError:
                st.error(f"Error: File not found at path '{file_path_to_download}'. It might have been moved or deleted.")
            except Exception as e:
                st.error(f"An error occurred while preparing the download/preview: {e}")

        with col2:
            st.subheader("💬 Mentor Feedback / Chat")

            # Display existing chat messages
            chat_history = selected_row['Chat']
            if isinstance(chat_history, list) and chat_history:
                 # Use a container with height for scrollability
                 with st.container(height=300):
                    for msg in chat_history:
                        st.markdown(f"**{msg.get('author', 'Unknown')}** ({msg.get('timestamp', '')}):\n{msg.get('message', '')}")
                        st.divider()
            else:
                st.info("No comments yet for this submission.")

            # Chat input form
            # Use a unique key based on the index to avoid state issues when switching selections
            with st.form(key=f"chat_form_{selected_submission_index}", clear_on_submit=True):
                comment_author = st.text_input("Your Name (Mentor):", value="Mentor", key=f"author_{selected_submission_index}") # Placeholder name
                comment_text = st.text_area("Add a comment:", key=f"comment_{selected_submission_index}")
                submit_comment = st.form_submit_button("Send Comment")

                if submit_comment and comment_text:
                    add_chat_message(selected_submission_index, comment_author, comment_text)
                    # Rerun to display the new message immediately
                    st.rerun()
                elif submit_comment and not comment_text:
                    st.warning("Please enter a comment before sending.")

    else:
         st.info("Select a submission from the list above to see details and comments.")

else:
    st.info("No submissions recorded yet.")

# --- Footer ---
st.markdown("---")
st.caption("Cross-Generation Knowledge Transfer Platform")