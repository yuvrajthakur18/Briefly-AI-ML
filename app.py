import os
import validators
import streamlit as st
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import YoutubeLoader
from dotenv import load_dotenv
from langchain.docstore.document import Document
import requests
from bs4 import BeautifulSoup
from transformers import T5ForConditionalGeneration, T5Tokenizer, MarianMTModel, MarianTokenizer
import fitz  # PyMuPDF
import re
from langdetect import detect
import easyocr
import numpy as np
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# Set up Streamlit app configuration
st.set_page_config(page_title="Multilingual Summarizer", page_icon="📄", layout="wide")

# Load Summarization LLM with Groq
groq_api_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="Gemma-7b-It", groq_api_key=groq_api_key)

@st.cache_resource
def load_model():
    model_directory = "t5-base"  # Using T5 for multilingual support
    model = T5ForConditionalGeneration.from_pretrained(model_directory)
    tokenizer = T5Tokenizer.from_pretrained(model_directory)
    return model, tokenizer

model, tokenizer = load_model()

@st.cache_resource
def load_translation_models():
    # Load translation models
    translation_model = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-mul-en")
    translation_tokenizer = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-mul-en")
    return translation_model, translation_tokenizer

translation_model, translation_tokenizer = load_translation_models()

def translate_text(text, src_lang):
    # Translate text to English
    src_lang = src_lang.lower()
    if src_lang == "zh-cn":
        src_lang = "zh"
    translation_input = translation_tokenizer.prepare_seq2seq_batch([text], src_lang=src_lang, tgt_lang="en", return_tensors="pt")
    translated_ids = translation_model.generate(**translation_input)
    translated_text = translation_tokenizer.decode(translated_ids[0], skip_special_tokens=True)
    return translated_text

def preprocess_text(text):
    # Remove special characters and extra whitespace
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = cleaned_text.strip()
    return cleaned_text

def summarize_text_t5(text, prompts):
    cleaned_text = preprocess_text(text)
    combined_text = f"summarize: {cleaned_text}"
    if prompts:
        combined_text += " " + " ".join(prompts)
    
    tokenized_text = tokenizer.encode(combined_text, return_tensors="pt", max_length=512, truncation=True, padding=True)
    
    summary_ids = model.generate(tokenized_text, max_length=150, num_beams=4, early_stopping=True)
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    
    return summary

def read_pdf(file):
    pdf_document = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        text += page.get_text()
    return text

def read_txt(file):
    return file.read().decode("utf-8")

def read_image(file, lang):
    image = Image.open(file)
    image_np = np.array(image)  # Convert PIL Image to numpy array
    
    # Language groups
    latin_languages = ['en', 'fr', 'de', 'es', 'it', 'pt']
    cyrillic_languages = ['ru', 'rs_cyrillic', 'be', 'bg', 'uk', 'mn', 'en']
    ja_ko_zh_languages = ['ja', 'ko', 'zh-cn', 'zh-tw', 'en']
    
    if lang in ['ja', 'ko', 'zh-cn', 'zh-tw']:
        reader = easyocr.Reader(ja_ko_zh_languages)
    elif lang in cyrillic_languages:
        reader = easyocr.Reader(cyrillic_languages)
    else:
        reader = easyocr.Reader(latin_languages)
    
    result = reader.readtext(image_np, detail=0)
    
    text = ' '.join(result)
    return text

def detect_language(text):
    lang = detect(text)
    return lang

def fetch_url_data(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            text_content = soup.get_text(separator='\n')  # Extract text content
            return text_content.strip()  # Remove leading/trailing whitespace
        else:
            return "Failed to retrieve content from the URL."
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"

# Title with a container
st.markdown(
    """
    <style>
    .title-container {
        position: relative;
        background-image: url("https://imgs.search.brave.com/LMbtcRP9xh_GYr28J_aW054OB4mUYjDtd8Gu6vlneYM/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9pbWcu/ZnJlZXBpay5jb20v/ZnJlZS1waG90by9h/YnN0cmFjdC1iYWNr/Z3JvdW5kLXdpdGgt/cmVkLWxpbmVzXzEz/NjEtMzUzMS5qcGc_/c2l6ZT02MjYmZXh0/PWpwZw");
        background-size: cover;
        padding: 50px;
        border-radius: 15px;
        text-align: center;
        overflow: hidden;
        transition: transform 0.5s ease;
    }
    
    .title-container h1, .title-container h2 {
        color: white;
        font-family: 'Quicksand', sans-serif;
        position: relative;
        z-index: 2;
        transition: transform 0.3s ease, text-shadow 0.3s ease;
    }

    .title-container h1 {
        font-size: 3em;
    }

    .title-container h2 {
        font-size: 1.5em;
    }

    .title-container:hover h1, .title-container:hover h2 {
        transform: scale(1.1) perspective(500px) rotateX(5deg);
        text-shadow: 3px 3px 5px rgba(0, 0, 0, 0.3);
    }

    .title-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background-color: rgba(255, 255, 255, 0.2);
        z-index: 1;
        transition: left 0.5s ease-in-out;
    }

    .title-container:hover::before {
        left: 100%;
    }
    </style>
    <div class="title-container">
        <h1>📄 Summarize</h1>
        <h2>Summarize Text From YouTube, Website, or Uploaded Files</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar input method selection
st.sidebar.write("### Select Input Method")
input_type = st.sidebar.radio("Choose input method:", ("YouTube", "Website", "Direct Text Input", "Upload File (PDF, TXT, Image)"))

# Initialize session state for transcript, website content, and summary
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "website_content" not in st.session_state:
    st.session_state.website_content = ""
if "summary" not in st.session_state:
    st.session_state.summary = ""

# Handle YouTube input and processing
if input_type == "YouTube":
    youtube_url = st.text_input("Enter a YouTube URL", "")
    
    if st.button("Show YouTube Transcript"):
        if youtube_url and validators.url(youtube_url):
            try:
                with st.spinner("Fetching YouTube transcript..."):
                    loader = YoutubeLoader.from_youtube_url(youtube_url, add_video_info=True)
                    docs = loader.load()
                    if docs:
                        transcript_text = docs[0].page_content if hasattr(docs[0], 'page_content') else str(docs[0])
                        st.session_state.transcript = transcript_text
                        st.text_area("YouTube Transcript", value=st.session_state.transcript, height=300)
                    else:
                        st.error("No content found.")
            except Exception as e:
                st.error(f"An error occurred while fetching the YouTube transcript: {e}")
        else:
            st.error("Please enter a valid YouTube URL.")
    
    if st.button("Summarize YouTube Transcript"):
        if st.session_state.transcript:
            try:
                with st.spinner("Summarizing content..."):
                    docs = [Document(page_content=st.session_state.transcript)]
                    prompt_template = PromptTemplate(template="Summarize this content in 300 words:\n{text}", input_variables=["text"])
                    chain = load_summarize_chain(llm, chain_type="stuff", prompt=prompt_template)
                    summary = chain.run(docs)
                    st.session_state.summary = summary
                    st.success(summary)
            except Exception as e:
                st.error(f"An error occurred while summarizing: {e}")
        else:
            st.error("Transcript is not available. Please fetch the transcript first.")

# Handle Website input and processing
elif input_type == "Website":
    url = st.text_input("Enter a Website URL", "")
    
    if url:
        input_text = fetch_url_data(url)
        if input_text:
            st.session_state.website_content = input_text
            st.text_area("Content from the URL", input_text, height=200)

    if st.button("Summarize Website Content"):
        if st.session_state.website_content:
            try:
                with st.spinner("Summarizing content..."):
                    doc = Document(page_content=st.session_state.website_content)
                    prompt_template = PromptTemplate(template="Summarize this content in 300 words:\n{text}", input_variables=["text"])
                    chain = load_summarize_chain(llm, chain_type="stuff", prompt=prompt_template)
                    summary = chain.run([doc])
                    st.session_state.summary = summary
                    st.success(summary)
            except Exception as e:
                st.error(f"An error occurred while summarizing: {e}")
        else:
            st.error("Website content is not available. Please enter a valid URL and fetch the content first.")

# Handle Direct Text Input and File Upload
elif input_type in ("Direct Text Input", "Upload File (PDF, TXT, Image)"):
    if input_type == "Direct Text Input":
        # Text input
        user_input = st.text_area("Enter your text here:", height=200)

        if user_input:
            file_text = user_input
        else:
            file_text = None

    else:
        # File upload
        uploaded_file = st.file_uploader("Choose a file (PDF, TXT, Image)", type=["pdf", "txt", "png", "jpg", "jpeg"])

        if uploaded_file is not None:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            if file_extension == ".pdf":
                file_text = read_pdf(uploaded_file)
            elif file_extension == ".txt":
                file_text = read_txt(uploaded_file)
            elif file_extension in [".png", ".jpg", ".jpeg"]:
                # First detect the language of the image text
                temp_image_text = read_image(uploaded_file, 'en')  # Use English as a placeholder for detection
                detected_lang = detect_language(temp_image_text)
                file_text = read_image(uploaded_file, detected_lang)
            else:
                file_text = None
                st.error("Unsupported file type. Please upload a PDF, TXT, or Image file.")
        else:
            file_text = None

    if file_text:
        if input_type == "Upload File (PDF, TXT, Image)":
            st.write("**File/Text content:**")
            st.text_area("File/Text content", value=file_text, height=200)

        # Detect language
        detected_language = detect_language(file_text)
        st.write(f"**Detected Language:** {detected_language.capitalize()}")

        # Translation option
        if detected_language != "en":
            translate_option = st.checkbox("Translate to English")
            if translate_option:
                file_text = translate_text(file_text, detected_language)
                st.write("**Translated Text:**")
                st.text_area("Translated Text", value=file_text, height=200)
                detected_language = "en"

        # Chat-like prompt system
        if "prompts" not in st.session_state:
            st.session_state.prompts = []

        st.write("### Refine your summary:")
        prompt = st.text_input("Enter a prompt to refine the summary, e.g., 'focus on key points'")

        if st.button("Add Prompt"):
            if prompt:
                st.session_state.prompts.append(prompt)
                st.success(f"Prompt added: {prompt}")
            else:
                st.error("Please enter a valid prompt.")

        # Display current prompts
        if st.session_state.prompts:
            st.write("#### Current Prompts:")
            for i, p in enumerate(st.session_state.prompts):
                st.write(f"{i+1}. {p}")

        # Summary button
        if st.button("Generate Summary"):
            with st.spinner("Generating summary..."):
                try:
                    summary = summarize_text_t5(file_text, st.session_state.prompts)
                    st.subheader("Summary")
                    st.write(summary)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
    else:
        st.write("Please enter some text or upload a file to get started.")

# CSS for styling
st.markdown("""
    <style>
    .stTextArea, .stTextInput, .stButton, .stMarkdown {
        font-family: 'Comic Sans MS', cursive, sans-serif;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
    }
    </style>
    """, unsafe_allow_html=True)

