import os
import fitz  # PyMuPDF
import json

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def main():
    books = ['Flamingo', 'Vistas']
    all_content = {}
    
    for book in books:
        if not os.path.exists(book):
            continue
            
        print(f"Extracting texts for {book}...")
        book_text = ""
        for filename in sorted(os.listdir(book)):
            if filename.endswith('.pdf'):
                filepath = os.path.join(book, filename)
                print(f"  - Reading {filename}")
                book_text += f"\n\n--- Start of {filename} ---\n\n"
                book_text += extract_text_from_pdf(filepath)
                book_text += f"\n\n--- End of {filename} ---\n\n"
        
        all_content[book] = book_text
        
    with open('books_content.json', 'w', encoding='utf-8') as f:
        json.dump(all_content, f, ensure_ascii=False, indent=2)
        
    print("Done! Extracted text saved to books_content.json")

if __name__ == "__main__":
    main()
