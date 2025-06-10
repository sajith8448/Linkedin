import streamlit as st
import google.generativeai as genai
import re
from PIL import Image
import joblib
import os
import io
import streamlit.components.v1 as components
import urllib.parse
import time

# Hardcode the API key (replace with your actual key)
GOOGLE_API_KEY = "AIzaSyBxZJci98VkGnL6vFPIBXnCVpz6OAgy37I"
try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"Failed to configure Gemini API: {str(e)}")
    st.stop()

# Configure Streamlit page settings
st.set_page_config(
    page_title="LinkedIn Post Generator",
    page_icon=":sparkles:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Gemini model
try:
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    st.error(f"Failed to initialize Gemini model: {str(e)}")
    st.stop()

# Function to generate LinkedIn post using Gemini API with text and optional image
def generate_linkedin_post(bullet_points, tone, char_limit, include_hashtags, custom_hashtags, emoji_level, image=None):
    prompt = f"""
    Create a LinkedIn post based on the following bullet-point ideas{' and the provided image' if image else ''}. The post should be {tone} in tone, within {char_limit} characters, and {'include relevant hashtags' if include_hashtags else 'exclude hashtags'}. {'Use these custom hashtags: ' + ', '.join(custom_hashtags) if custom_hashtags else ''}. Use emojis {emoji_level}.
    Bullet points:
    {bullet_points}
    {'Describe the image and incorporate it into the post context.' if image else ''}
    
    Format the post with clear paragraphs, professional or casual language as specified, and ensure it is engaging and polished for LinkedIn.
    """
    try:
        if image:
            # Send both text and image to Gemini
            response = model.generate_content([prompt, image])
        else:
            response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating post: {str(e)}"

# Function to count characters and validate
def count_characters(text):
    return len(text)

# Function to clean and format hashtags
def format_hashtags(hashtags):
    return [f"#{re.sub(r'\s+', '', tag.strip())}" for tag in hashtags if tag.strip()]

# Initialize session state for chat history, post drafts, and images
if 'post_drafts' not in st.session_state:
    st.session_state.post_drafts = []
if 'selected_draft' not in st.session_state:
    st.session_state.selected_draft = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'draft_images' not in st.session_state:
    st.session_state.draft_images = {}  # Maps draft text to image paths

# Sidebar for app settings and history
with st.sidebar:
    st.title("LinkedIn Post Generator")
    
    # Image upload for logo
    st.markdown("### Upload Logo (PNG, max 5MB)")
    uploaded_logo = st.file_uploader("Choose a PNG image for logo", type=["png"], key="logo_uploader")
    if uploaded_logo is not None:
        # Validate file size (max 5MB)
        if uploaded_logo.size > 5 * 1024 * 1024:
            st.error("Logo size exceeds 5MB limit. Please upload a smaller file.")
        else:
            try:
                # Process and display uploaded image
                logo_image = Image.open(uploaded_logo)
                st.image(logo_image, width=100)
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
                # Fallback placeholder
                st.image("https://via.placeholder.com/100", width=100, caption="Placeholder Logo")
    else:
        # Fallback placeholder if no image is uploaded
        st.image("https://via.placeholder.com/100", width=100, caption="Placeholder Logo")
    
    st.markdown("### Settings")
    tone = st.selectbox("Select Tone", ["Professional", "Casual", "Inspirational", "Conversational"])
    char_limit = st.slider("Character Limit", 200, 3000, 1300)
    include_hashtags = st.checkbox("Include Hashtags", value=True)
    custom_hashtags = st.text_input("Custom Hashtags (comma-separated)", "")
    emoji_level = st.selectbox("Emoji Usage", ["None", "Minimal", "Moderate", "High"])
    theme = st.selectbox("UI Theme", ["Light", "Dark", "Colorful"])
    
    # Draft history
    st.markdown("### Draft History")
    draft_options = ["New Post"] + [f"Draft {i+1}: {draft[:30]}..." for i, draft in enumerate(st.session_state.post_drafts)]
    selected_draft = st.selectbox("Select Draft", draft_options)
    if selected_draft != "New Post":
        try:
            draft_index = draft_options.index(selected_draft) - 1
            if 0 <= draft_index < len(st.session_state.post_drafts):
                st.session_state.selected_draft = st.session_state.post_drafts[draft_index]
            else:
                st.warning("Selected draft is no longer available. Please choose another.")
                st.session_state.selected_draft = None
        except ValueError:
            st.warning("Invalid draft selection. Please choose another.")
            st.session_state.selected_draft = None

# Apply custom CSS for colorful UI
if theme == "Colorful":
    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .stButton>button {
        background-color: #0077b5;
        color: white;
        border-radius: 10px;
    }
    .stTextInput>div>input {
        border: 2px solid #0077b5;
        border-radius: 10px;
    }
    .stSelectbox>div>div {
        border: 2px solid #0077b5;
        border-radius: 10px;
    }
    .stFileUploader>div>div {
        border: 2px solid #0077b5;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Main app layout
st.title("✨ LinkedIn Post Generator ✨")
st.markdown("Transform your ideas into polished LinkedIn posts with ease!")

# Tabs for different functionalities
tab1, tab2, tab3, tab4 = st.tabs(["Create Post", "Edit Post", "Preview & Export", "AI Assistant"])

with tab1:
    st.header("Create Your Post")
    bullet_points = st.text_area("Enter Your Bullet-Point Ideas", placeholder="e.g.\n- Launched a new product\n- Team achieved 20% growth\n- Excited about industry trends", height=200)
    # Image upload for post
    st.markdown("### Upload Image for Post (PNG, max 5MB)")
    post_image = st.file_uploader("Choose a PNG image for the post", type=["png"], key="post_image_uploader")
    if st.button("Generate Post"):
        if bullet_points:
            custom_hashtags_list = format_hashtags(custom_hashtags.split(",")) if custom_hashtags else []
            image_content = None
            image_path = None
            if post_image is not None:
                if post_image.size > 5 * 1024 * 1024:
                    st.error("Post image size exceeds 5MB limit. Please upload a smaller file.")
                else:
                    try:
                        # Process and save image
                        image_content = Image.open(post_image)
                        # Generate unique filename for image
                        image_filename = f"data/post_image_{int(time.time() * 1000)}.png"
                        os.makedirs("data", exist_ok=True)
                        image_content.save(image_filename)
                        image_path = image_filename
                    except Exception as e:
                        st.error(f"Error processing post image: {str(e)}")
                        image_content = None
            # Generate post with or without image
            post = generate_linkedin_post(bullet_points, tone, char_limit, include_hashtags, custom_hashtags_list, emoji_level, image_content)
            if not post.startswith("Error"):
                st.session_state.post_drafts.append(post)
                st.session_state.selected_draft = post
                if image_path:
                    st.session_state.draft_images[post] = image_path
                st.success("Post generated successfully!")
            else:
                st.error(post)
        else:
            st.error("Please enter bullet-point ideas.")

with tab2:
    st.header("Edit Your Post")
    if st.session_state.selected_draft:
        edited_post = st.text_area("Edit Post", value=st.session_state.selected_draft, height=300)
        if st.button("Save Edited Post"):
            try:
                draft_index = st.session_state.post_drafts.index(st.session_state.selected_draft)
                # Update draft and preserve associated image
                old_post = st.session_state.post_drafts[draft_index]
                st.session_state.post_drafts[draft_index] = edited_post
                st.session_state.selected_draft = edited_post
                if old_post in st.session_state.draft_images:
                    st.session_state.draft_images[edited_post] = st.session_state.draft_images.pop(old_post)
                st.success("Post updated successfully!")
            except ValueError:
                st.error("Draft not found. Please generate a new post.")
    else:
        st.info("Generate a post first to edit.")

with tab3:
    st.header("Preview & Export")
    if st.session_state.selected_draft:
        char_count = count_characters(st.session_state.selected_draft)
        st.markdown(f"**Character Count**: {char_count}/{char_limit}")
        st.markdown("### Preview")
        # Display post text
        st.markdown(st.session_state.selected_draft, unsafe_allow_html=True)
        # Display associated image if available
        if st.session_state.selected_draft in st.session_state.draft_images:
            try:
                st.image(st.session_state.draft_images[st.session_state.selected_draft], caption="Post Image Preview")
            except Exception as e:
                st.warning(f"Error displaying post image: {str(e)}")
        if char_count > char_limit:
            st.warning("Post exceeds character limit!")
        
        # Export options
        st.markdown("### Export Options")
        st.info("To share on LinkedIn, copy the post text and manually upload the image (if any) in LinkedIn's post composer.")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Copy to Clipboard"):
                components.html(
                    f"""
                    <textarea id="post" style="position: absolute; left: -9999px;">{st.session_state.selected_draft}</textarea>
                    <script>
                        function copyToClipboard() {{
                            var copyText = document.getElementById("post");
                            copyText.select();
                            navigator.clipboard.writeText(copyText.value)
                                .then(() => alert("Copied to clipboard!"))
                                .catch(err => alert("Failed to copy: " + err));
                        }}
                        copyToClipboard();
                    </script>
                    """,
                    height=0
                )
                st.success("Post copied to clipboard!")
        with col2:
            st.download_button("Download as Text", st.session_state.selected_draft, file_name="linkedin_post.txt")
            # Download image if available
            if st.session_state.selected_draft in st.session_state.draft_images:
                image_path = st.session_state.draft_images[st.session_state.selected_draft]
                with open(image_path, "rb") as file:
                    st.download_button("Download Post Image", file, file_name=os.path.basename(image_path))
        with col3:
            if st.button("Share to LinkedIn"):
                encoded_post = urllib.parse.quote(st.session_state.selected_draft)
                linkedin_share_url = f"https://www.linkedin.com/feed/?shareActive=true&text={encoded_post}"
                st.markdown(f'<a href="{linkedin_share_url}" target="_blank">Share on LinkedIn (Text Only)</a>', unsafe_allow_html=True)
    else:
        st.info("No post available to preview.")

with tab4:
    st.header("AI Assistant")
    user_query = st.text_input("Ask the AI for help (e.g., suggest hashtags, improve post)")
    if st.button("Ask AI"):
        if user_query:
            try:
                response = model.generate_content(f"Provide suggestions for: {user_query}")
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"AI Assistant error: {str(e)}")
        else:
            st.error("Please enter a query.")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Save drafts to file
try:
    joblib.dump(st.session_state.post_drafts, "data/post_drafts.pkl")
    joblib.dump(st.session_state.draft_images, "data/draft_images.pkl")
except:
    os.makedirs("data", exist_ok=True)
    joblib.dump(st.session_state.post_drafts, "data/post_drafts.pkl")
    joblib.dump(st.session_state.draft_images, "data/draft_images.pkl")