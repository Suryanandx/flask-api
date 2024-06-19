import base64
import logging
import os
import pickle
import subprocess

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from nltk.tokenize import sent_tokenize

print(os.getcwd())

from utils.pdf_utils import process_pdf

def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def tokenizer_length(string: str) -> int:
    """Returns the number of tokens in a text string."""
    return len(enc.encode(string))

def split_text_by_sentences(text, token_limit):
    """Splits a text into segments of complete sentences, each with a number of tokens up to token_limit."""
    sentences = sent_tokenize(text)
    current_count = 0
    sentence_buffer = []
    segments = []

    for sentence in sentences:
        # Estimate the token length of the sentence
        sentence_length = tokenizer_length(sentence)

        if current_count + sentence_length > token_limit:
            if sentence_buffer:
                segments.append(' '.join(sentence_buffer))
                sentence_buffer = [sentence]
                current_count = sentence_length
            else:
                # Handle the case where a single sentence exceeds the token_limit
                segments.append(sentence)
                current_count = 0
        else:
            sentence_buffer.append(sentence)
            current_count += sentence_length

    # Add the last segment if there's any
    if sentence_buffer:
        segments.append(' '.join(sentence_buffer))

    return segments

def extract_text_and_save(filename):
    text = ""
    pdf_path = os.path.join("uploads", filename)
    
    cmd = f"pdfgrep -Pn '^(?s:(?=.*consolidated results of operations)|(?=.*Consolidated Statements of Operations)|(?=.*Consolidated Statements of Cash Flows)|(?=.*CONSOLIDATED STATEMENTS OF CASH FLOWS)|(?=.*CONSOLIDATED STATEMENTS OF INCOME)|(?=.*Interest expenses and other bank charges)|(?=.*Depreciation and Amortization)|(?=.*CONSOLIDATED BALANCE SHEETS))' {pdf_path} | awk -F\":\" '$0~\":\"{{print $1}}' | tr '\n' ','"
    print(cmd)
    logging.info(cmd)
    pages = subprocess.check_output(cmd, shell=True).decode("utf-8")
    logging.info(f'count of pages {pages}')
    if not pages:
       logging.warning(f"No matching pages found in {pdf_path}")
       return
    processed_text = process_pdf(pdf_path, pages)
    if processed_text is not None:
        text += processed_text
    text_file = open(f"{os.path.splitext(pdf_path)[0]}.txt", "w")
    text_file.write(text)
    text_file.close()       
    return text

def split_text_by_tokens(text, token_limit):
    """Splits a text into segments, each with a number of tokens up to token_limit."""
    words = text.split()
    current_count = 0
    word_buffer = []
    segments = []

    for word in words:
        # Add a space for all but the first word in the buffer
        test_text = ' '.join(word_buffer + [word]) if word_buffer else word
        word_length = tokenizer_length(test_text)

        if word_length > token_limit:
            # If a single word exceeds the token_limit, it's added to its own segment
            segments.append(word)
            word_buffer.clear()
            continue

        if current_count + word_length > token_limit:
            segments.append(' '.join(word_buffer))
            word_buffer = [word]
            current_count = tokenizer_length(word)
        else:
            word_buffer.append(word)
            current_count = word_length

    # Add the last segment if there's any
    if word_buffer:
        segments.append(' '.join(word_buffer))

    return segments

# Function to get or create the vector store for text embeddings
def get_or_create_vector_store(chunks, store_name):
    embeddings_file_path = f"{store_name}.pkl"

    if os.path.exists(embeddings_file_path):
        with open(embeddings_file_path, "rb") as f:
            vector_store = pickle.load(f)
    else:
        embeddings = OpenAIEmbeddings()
        vector_store = FAISS.from_texts(chunks, embedding=embeddings)
        with open(embeddings_file_path, "wb") as f:
            pickle.dump(vector_store, f)

    return vector_store