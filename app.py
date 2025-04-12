import streamlit as st
from datetime import datetime, timezone # Import timezone
import uuid
from supabase import create_client, Client, PostgrestAPIError # Import PostgrestAPIError

# --- Page Configuration ---
st.set_page_config(
    page_title="Craft Knowledge Forum",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Supabase Initialization ---
# Cache the Supabase client connection resource
@st.cache_resource
def init_supabase_client():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found in secrets.toml. Please add [supabase] section with url and key.")
        st.stop()
    except Exception as e:
        st.error(f"Failed to initialize Supabase client: {e}")
        st.stop()

supabase: Client = init_supabase_client()

# --- Data Loading Function ---
def load_forum_data():
    """Loads topics and their posts from Supabase."""
    topics_dict = {}
    try:
        # Fetch topics sorted by creation date (newest first)
        response_topics = supabase.table('topics').select('*').order('created_at', desc=True).execute()
        if not hasattr(response_topics, 'data'):
             st.error("Failed to fetch topics or unexpected response format.")
             return {}

        topics_data = response_topics.data

        # Fetch all posts sorted by creation date (oldest first within a topic)
        response_posts = supabase.table('posts').select('*').order('created_at', desc=False).execute()
        if not hasattr(response_posts, 'data'):
             st.error("Failed to fetch posts or unexpected response format.")
             # Return topics even if posts fail? Or empty? Let's return empty for safety.
             return {}

        posts_data = response_posts.data

        # Organize posts by topic_id for efficient lookup
        posts_by_topic = {}
        for post in posts_data:
            topic_id = post.get('topic_id')
            if topic_id:
                if topic_id not in posts_by_topic:
                    posts_by_topic[topic_id] = []
                 # Convert timestamp string from Supabase (UTC) to datetime object
                post['created_at'] = datetime.fromisoformat(post['created_at'])
                posts_by_topic[topic_id].append(post)

        # Build the final nested dictionary
        for topic in topics_data:
             topic_id = topic['id']
             # Convert timestamp string from Supabase (UTC) to datetime object
             topic['created_at'] = datetime.fromisoformat(topic['created_at'])
             # Assign posts, default to empty list if no posts found for this topic
             topic['posts'] = posts_by_topic.get(topic_id, [])
             # Use 'created_at' for 'timestamp' key for compatibility with old display code
             topic['timestamp'] = topic['created_at']
             topics_dict[topic_id] = topic

    except PostgrestAPIError as e:
        st.error(f"Database error loading data: {e.message}")
    except Exception as e:
        st.error(f"An unexpected error occurred loading data: {e}")

    return topics_dict

# --- Data Saving Functions ---
def save_topic(topic_id, title, author):
    """Saves a new topic metadata to Supabase."""
    try:
        # created_at will be set by DB default
        topic_data = {'id': topic_id, 'title': title, 'author': author}
        response = supabase.table('topics').insert(topic_data).execute()
        # Basic check if insertion seemingly succeeded (more robust checks might be needed)
        return len(response.data) > 0
    except PostgrestAPIError as e:
        st.error(f"Database error saving topic: {e.message}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred saving topic: {e}")
        return False

def save_post(post_id, topic_id, author, content):
    """Saves a new post (OP or reply) to Supabase."""
    try:
        # created_at will be set by DB default
        post_data = {'id': post_id, 'topic_id': topic_id, 'author': author, 'content': content}
        response = supabase.table('posts').insert(post_data).execute()
        return len(response.data) > 0
    except PostgrestAPIError as e:
        st.error(f"Database error saving post: {e.message}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred saving post: {e}")
        return False


# --- Session State Initialization (UI state only) ---
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'list_topics'
if 'selected_topic_id' not in st.session_state:
    st.session_state.selected_topic_id = None
if 'username' not in st.session_state:
    st.session_state.username = ""

# --- Utility Functions ---
def format_timestamp(ts):
    """Formats datetime object into a readable string."""
    if isinstance(ts, str): # Handle potential string timestamps if conversion failed
         return ts
    # Format as local time potentially, or keep UTC? Let's keep consistent:
    # Example: 2025-04-12 01:55 AM (UTC)
    return ts.strftime("%Y-%m-%d %I:%M %p (UTC)")


# --- UI Components ---

# --- Sidebar ---
with st.sidebar:
    st.title("🛠️ Craft Forum")
    st.divider()

    st.subheader("Your Details")
    username_input = st.text_input("Enter your username", value=st.session_state.username, key="username_input_key")
    if username_input:
        st.session_state.username = username_input

    st.divider()
    st.subheader("Actions")
    if st.button("💬 View All Topics", use_container_width=True):
        st.session_state.current_view = 'list_topics'
        st.session_state.selected_topic_id = None
        st.rerun()

    create_topic_disabled = not bool(st.session_state.username)
    create_topic_help = "Enter a username to create topics." if create_topic_disabled else None
    if st.button("➕ Create New Topic", use_container_width=True, type="primary", disabled=create_topic_disabled, help=create_topic_help):
        st.session_state.current_view = 'create_topic'
        st.session_state.selected_topic_id = None
        st.rerun()

    st.divider()
    st.caption("Part of the Cross-Generation Knowledge Transfer Platform")


# --- Main Content Area ---

# --- Load Data ---
# Load fresh data on each run. Caching could be added here later if needed.
topics_data = load_forum_data()

# --- View: List All Topics ---
if st.session_state.current_view == 'list_topics':
    st.title("Forum Topics")
    st.markdown("Browse questions and discussions on various techniques.")
    st.divider()

    if not topics_data:
        st.info("No topics yet, or failed to load topics. Be the first to create one!")
    else:
        # Sort topics by timestamp (already sorted by query, but double-check if needed)
        # We use the dictionary directly now
        for topic_id, topic in topics_data.items():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.subheader(topic.get('title', 'No Title'))
                    st.caption(f"Started by: **{topic.get('author', 'Unknown')}** on {format_timestamp(topic.get('timestamp', ''))}") # Use .get for safety
                with col2:
                     reply_count = max(0, len(topic.get('posts', [])) - 1) # OP doesn't count as reply
                     st.metric(label="Replies", value=reply_count)
                with col3:
                     if st.button("View Thread", key=f"view_{topic_id}", use_container_width=True):
                        st.session_state.current_view = 'view_thread'
                        st.session_state.selected_topic_id = topic_id
                        st.rerun()

# --- View: Display a Single Thread ---
elif st.session_state.current_view == 'view_thread' and st.session_state.selected_topic_id:
    topic_id = st.session_state.selected_topic_id
    if topic_id not in topics_data:
        st.error("Topic not found or failed to load!")
        # Option: Attempt to reload data once? Or just go back to list.
        st.session_state.current_view = 'list_topics'
        st.session_state.selected_topic_id = None
        # Consider adding a button to retry loading or go back
        if st.button("Back to Topics List"):
            st.rerun()
    else:
        topic = topics_data[topic_id]
        st.title(f"🧵 {topic.get('title', 'No Title')}")

        # --- Display Original Post (OP) ---
        op_post = topic.get('posts', [])[0] if topic.get('posts') else None
        if op_post:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{op_post.get('author', 'Unknown')}** (OP)")
            with col2:
                st.markdown(f"<p style='text-align: right; color: grey; font-size: smaller;'>{format_timestamp(op_post.get('created_at', ''))}</p>", unsafe_allow_html=True)
            st.markdown(op_post.get('content', '*No content*'))
            st.divider()
        else:
            st.warning("Original post not found for this topic.")
            st.divider()


        # --- Display Replies ---
        replies = topic.get('posts', [])[1:] # All posts except the first one
        if replies:
            st.subheader(f"Replies ({len(replies)})")
            for i, reply in enumerate(replies):
                if i > 0: # Add divider before 2nd, 3rd reply etc.
                     st.divider()
                with st.container():
                    col1_reply, col2_reply = st.columns([3, 1])
                    with col1_reply:
                        st.markdown(f"**{reply.get('author', 'Unknown')}**")
                    with col2_reply:
                        st.markdown(f"<p style='text-align: right; color: grey; font-size: smaller;'>{format_timestamp(reply.get('created_at', ''))}</p>", unsafe_allow_html=True)
                    st.markdown(reply.get('content', '*No content*'))
            st.divider()

        # --- Reply Form ---
        st.subheader("💬 Add Your Reply")
        if st.session_state.username:
            with st.form("reply_form", clear_on_submit=True):
                reply_content = st.text_area("Your message:", height=150, placeholder="Share your insights or ask for clarification...")
                submitted = st.form_submit_button("Post Reply")
                if submitted:
                    if not reply_content.strip():
                        st.warning("Reply cannot be empty.")
                    else:
                        new_post_id = f"post_{uuid.uuid4().hex[:8]}"
                        # Save the reply to the database
                        if save_post(new_post_id, topic_id, st.session_state.username, reply_content):
                            st.success("Reply posted successfully!")
                            # No need to manually update state, rerun will reload from DB
                            st.rerun()
                        # Error message is handled within save_post
        else:
            st.warning("Please enter your username in the sidebar to reply.")


# --- View: Create New Topic ---
elif st.session_state.current_view == 'create_topic':
    st.title("➕ Start a New Discussion")
    st.markdown("Ask a question or share a technique.")
    st.divider()

    if not st.session_state.username:
         st.error("Error: Username is required to create a topic. Please enter it in the sidebar.")
    else:
        with st.form("new_topic_form", clear_on_submit=True):
            topic_title = st.text_input("Topic Title / Question:", placeholder="e.g., How to achieve a perfect dovetail joint?")
            topic_content = st.text_area("Your first post (provide details):", height=200, placeholder="Describe the technique, problem, or question in detail...")
            submitted = st.form_submit_button("Create Topic")

            if submitted:
                if not topic_title.strip():
                    st.warning("Topic title cannot be empty.")
                elif not topic_content.strip():
                    st.warning("The first post cannot be empty.")
                else:
                    new_topic_id = f"topic_{uuid.uuid4().hex[:8]}"
                    first_post_id = f"post_{uuid.uuid4().hex[:8]}"

                    # 1. Save the topic metadata
                    topic_saved = save_topic(new_topic_id, topic_title, st.session_state.username)

                    # 2. Save the first post only if topic was saved
                    post_saved = False
                    if topic_saved:
                        post_saved = save_post(first_post_id, new_topic_id, st.session_state.username, topic_content)
                    else:
                         st.error("Failed to save topic metadata. Post was not saved.")

                    # 3. If both saved, switch view
                    if topic_saved and post_saved:
                        st.success("Topic created successfully!")
                        st.session_state.current_view = 'view_thread'
                        st.session_state.selected_topic_id = new_topic_id
                        st.rerun()
                    elif topic_saved and not post_saved:
                         st.error("Topic metadata was saved, but the initial post failed to save. Please try adding the post as a reply.")
                         # Optionally: delete the topic metadata here if desired, or leave it as an empty topic
                         st.session_state.current_view = 'list_topics' # Go back to list
                         st.rerun()