from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFacePipeline
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
import tempfile
import os
import logging
from dotenv import load_dotenv
from transformers import pipeline
import chromadb

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Allows servers to securely specify which foreign domains can access the resources
CORS(app, resources={
   r"/*": {
       "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
       "methods": ["GET", "POST", "OPTIONS"],
       # Specifies which HTTP headers can be used during the actual request
       # Headers describe the package without being the actual content
       "allow_headers": ["Content-Type", "Authorization", "Accept", "Accept-Language",
                        "Connection", "Origin", "Referer", "Sec-Fetch-Dest",
                        "Sec-Fetch-Mode", "Sec-Fetch-Site", "User-Agent",
                        "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"],
       "supports_credentials": True,
       "max_age": 3600
   }
})

MAX_FILES = 5
ALLOWED_EXTENSIONS = {'pdf'}
vectorstore = None

# Initialize the HuggingFace model
# Creates a HuggingFace pipeline
# task type: takes text in and produces text out
# specifies model to achieve this with
pipe = pipeline("text2text-generation", model="google/flan-t5-large", max_new_tokens=200)
llm = HuggingFacePipeline(pipeline=pipe)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# app.route: a decorator that registers the function below it as the handler
# for a specific URL. When Flask receives a request matching the URL and method,
# it calls that function.

# "upload-pdfs": the URL path this route listens on. When a request is sent 
# to http://localhost:5001/upload-pdfs, Flask knows to run this function.

# This route receives the PDF from the frontend and kicks off the ingestion pipeline
@app.route('/upload-pdfs', methods=['POST', 'OPTIONS'])
def upload_pdfs():

    # OPTIONS: handles the browser preflight check before the actual POST
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "http://localhost:5173"))
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files[]')

    if len(files) > MAX_FILES:
        return jsonify({'error': f'Maximum {MAX_FILES} files allowed'}), 400

    try:
        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )

        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        all_documents = []

        for file in files:
            if file and allowed_file(file.filename):
                # Sanitize the filename to prevent security attacks
                filename = secure_filename(file.filename)

                # Creates a temp file on disk to save the uploaded PDF to
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    file.save(tmp_file.name)

                    logger.info(f"Processing file: {filename}")

                    # Creates a LangChain PDF loader pointing at the temp file
                    loader = PyPDFLoader(tmp_file.name)
                    documents = loader.load()

                    # Splits documents into smaller chunks
                    split_docs = text_splitter.split_documents(documents)

                    # Adds those chunks to a running list that accumulates chunks across all uploaded files
                    all_documents.extend(split_docs)

                    os.unlink(tmp_file.name)

        global vectorstore

        # Clear existing vectorstore if it exists
        if vectorstore is not None:
            vectorstore = None

        # Use in-memory ChromaDB client to avoid file locking issues
        # Vectors are stored in memory — lost on Flask restart but fine for demo purposes
        client = chromadb.Client()

        # Creates a new ChromaDB vector store from the documents
        # Embeds all chunks to vectors and stores them in ChromaDB
        vectorstore = Chroma.from_documents(
            documents=all_documents,
            embedding=embeddings,
            client=client,
            collection_name="pdf_collection"
        )

        response = jsonify({
           'message': f'Successfully processed {len(files)} PDF files',
           'document_chunks': len(all_documents)
        })
        return response

    except Exception as e:
        logging.error(f"Error processing files: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Question-Answering Route
@app.route('/ask-question', methods=['POST', 'OPTIONS'])
def ask_question():
    if request.method == "OPTIONS":
        return jsonify({"message": "OK"}), 200

    if not vectorstore:
        return jsonify({'error': 'No documents have been uploaded yet'}), 400

    try:
        # Reads the JSON body from the incoming POST request
        data = request.get_json()
        # Checks if the request body was empty or wasn't valid JSON
        # JSON was valid but didn't include a text field
        if not data or 'text' not in data:
            return jsonify({'error': 'No question provided'}), 400

        question = data['text']

        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        prompt = PromptTemplate.from_template(
            """You are a helpful assistant. Use the context below to answer the question. 
        Be specific and concise."

        Context:
        {context}

        Question: {question}

        Answer:"""
        )

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Builds the full retrieval chain using LCEL
        qa_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        source_docs = retriever.invoke(question)
        answer = qa_chain.invoke(question)

        response = jsonify({
            'answer': answer,
            'sources': [doc.page_content for doc in source_docs]
        })

        return response

    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)