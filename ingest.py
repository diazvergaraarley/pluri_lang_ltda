
import os
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables
load_dotenv()

DATA_DIR = "./data"
CHROMA_DIR = "./chroma_db"


def ingest_documents():
    print("Starting document ingestion...")

    # 1. Validate data directory
    if not os.path.exists(DATA_DIR):
        print("❌ Error: The 'data/' directory does not exist.")
        return

    # 2. Load all PDFs from the data directory
    loader = PyPDFDirectoryLoader(DATA_DIR)
    documents = loader.load()

    if not documents:
        print("❌ Error: No PDF documents were found in the 'data/' directory.")
        return

    print(f"Found {len(documents)} pages across the PDF documents.")

    # 3. Split documents into chunks with overlap
    print("Splitting documents into chunks...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    chunks = text_splitter.split_documents(documents)

    print(f"Created {len(chunks)} chunks.")

    # 4. Remove the previous vector database
    if os.path.exists(CHROMA_DIR):
        print("Removing previous ChromaDB...")
        shutil.rmtree(CHROMA_DIR)

    # 5. Generate embeddings and store documents in ChromaDB
    print("Generating embeddings and creating ChromaDB...")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    print("✅ Document ingestion completed successfully.")
    print(f"Vector database created at: {CHROMA_DIR}")


if __name__ == "__main__":
    ingest_documents()
