# CleanDoc --- Institutional DOCX Sanitizer

CleanDoc is a focused, high‑reliability tool designed for the **Superior
Audit Office of Tlaxcala (OFS)** to clean official DOCX audit documents
by removing institutional headers, images, and signature sections. It
standardizes documents for downstream processing and preserves only the
essential audit content.

------------------------------------------------------------------------

## Features

-   Automatic removal of:
    -   Institutional headers (Órgano de Fiscalización Superior,
        Dirección de Auditoría...)
    -   Header images not contained in tables
    -   Repeated institutional text inside textboxes (document, header,
        footer)
    -   Everything from the first occurrence of "Elaboró" to the end
-   Cleans multiple DOCX files in one upload (ZIP output)
-   Preserves table‑embedded logos
-   50 MB upload limit
-   Built with Flask, python‑docx, and lxml

------------------------------------------------------------------------

## Installation

``` bash
git clone https://github.com/OmarSalvatierra99/cleandoc.git
cd cleandoc
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

------------------------------------------------------------------------

## Usage Example

``` bash
Input:  documento.docx
Process:
  • Removes OFS headers
  • Removes header images outside tables
  • Cleans textboxes
  • Deletes all content after “Elaboró”

Output: limpia_documento.docx
```

------------------------------------------------------------------------

## Live Workflow

1.  Access the web interface.
2.  Upload one or more `.docx` files.
3.  Receive:
    -   A cleaned `.docx` file (single upload), or
    -   A `.zip` containing all cleaned documents (multiple upload).

------------------------------------------------------------------------

© 2025 **Omar Gabriel Salvatierra Garcia** --- Institutional Software,
OFS Tlaxcala

