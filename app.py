from flask import Flask, render_template, request, send_file, jsonify
from docx import Document
from io import BytesIO
import re

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB máx.

# ============================================================
# PATRONES
# ============================================================
ORG_PAT = re.compile(r"ÓRGANO\s+DE\s+FISCALIZACI[ÓO]N\s+SUPERIOR", re.IGNORECASE)
DIR_PAT = re.compile(r"DIRECCI[ÓO]N\s+DE\s+AUDITOR[IÍ]A\s+A\s+ENTES\s+ESTATALES", re.IGNORECASE)
ELABORO_PAT = re.compile(r"Elabor[oó]", re.IGNORECASE)

def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "")

# ============================================================
# LIMPIAR TEXTO DENTRO DE TEXTBOXES
# ============================================================
def _limpiar_en_txbx(xmlroot):
    for p in xmlroot.xpath(".//*[local-name()='txbxContent']//*[local-name()='p']"):
        ts = p.xpath(".//*[local-name()='t']")
        if not ts:
            continue
        original = " ".join(_norm_ws(t.text) for t in ts if t.text)
        nuevo = ORG_PAT.sub("", original)
        nuevo = DIR_PAT.sub("", nuevo)
        nuevo = nuevo.strip()
        if nuevo != original:
            ts[0].text = nuevo
            for t in ts[1:]:
                t.text = ""
            if not nuevo:
                parent = p.getparent()
                if parent is not None:
                    parent.remove(p)

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def limpiar_cedula(file_stream):
    doc = Document(file_stream)

    # --- 1. Eliminar imágenes del encabezado (solo si no están en tablas) ---
    for section in doc.sections:
        # Eliminar imágenes DrawingML modernas (<drawing>)
        drawings = section.header._element.xpath(".//*[local-name()='drawing']")
        for shape in drawings:
            if shape.xpath("ancestor::*[local-name()='tbl']"):
                continue  # conservar imágenes dentro de tablas
            parent = shape.getparent()
            if parent is not None:
                parent.remove(shape)

        # Eliminar imágenes VML antiguas (<pict>) - generadas por IlovePDF
        # IMPORTANTE: NO eliminar <pict> que contengan textboxes (contienen texto importante)
        picts = section.header._element.xpath(".//*[local-name()='pict']")
        for pict in picts:
            if pict.xpath("ancestor::*[local-name()='tbl']"):
                continue  # conservar imágenes dentro de tablas

            # NO eliminar si contiene textboxes
            if pict.xpath(".//*[local-name()='txbxContent']"):
                continue  # conservar pict que contiene textboxes

            parent = pict.getparent()
            if parent is not None:
                parent.remove(pict)

    # --- 2. Eliminar encabezados institucionales en párrafos normales ---
    for p in list(doc.paragraphs):
        texto = p.text
        if ORG_PAT.search(texto) or DIR_PAT.search(texto):
            # Limpiar el texto completo del párrafo
            texto_limpio = ORG_PAT.sub("", texto)
            texto_limpio = DIR_PAT.sub("", texto_limpio)
            texto_limpio = texto_limpio.strip()

            if texto_limpio:
                # Si queda texto, poner todo en el primer run y vaciar los demás
                if p.runs:
                    p.runs[0].text = texto_limpio
                    for run in p.runs[1:]:
                        run.text = ""
            else:
                # Si no queda texto, eliminar el párrafo completo
                p._element.getparent().remove(p._element)

    # --- 3. Limpiar textboxes (documento, encabezado y pie) ---
    _limpiar_en_txbx(doc._element)
    for section in doc.sections:
        _limpiar_en_txbx(section.header._element)
        _limpiar_en_txbx(section.footer._element)

    # --- 4. Eliminar todo a partir del primer “Elaboró” ---
    indice_inicio = None
    for i, p in enumerate(doc.paragraphs):
        if ELABORO_PAT.search(p.text.replace(" ", "")):
            indice_inicio = i
            break
    if indice_inicio is not None:
        # Eliminar todos los párrafos desde “Elaboró” hasta el final
        for j in range(len(doc.paragraphs) - 1, indice_inicio - 1, -1):
            para = doc.paragraphs[j]
            para._element.getparent().remove(para._element)

    # --- 5. Guardar resultado ---
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# ============================================================
# RUTAS
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/limpiar_cedula", methods=["POST"])
def limpiar_endpoint():
    files = request.files.getlist("archivo")
    if not files:
        return jsonify({"error": "No se enviaron archivos"}), 400

    import zipfile, tempfile
    cleaned_files = []
    for f in files:
        if not f.filename.lower().endswith(".docx"):
            continue
        try:
            result = limpiar_cedula(f.stream)
            cleaned_files.append((f.filename, result))
        except Exception as e:
            print(f"Error procesando {f.filename}: {e}")

    if not cleaned_files:
        return jsonify({"error": "Ningún archivo válido procesado"}), 400

    if len(cleaned_files) == 1:
        name, stream = cleaned_files[0]
        return send_file(
            stream,
            as_attachment=True,
            download_name=f"limpia_{name}",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, stream in cleaned_files:
            zf.writestr(f"limpia_{name}", stream.read())
    tmp.seek(0)
    return send_file(tmp.name, as_attachment=True, download_name="cleandoc_limpios.zip")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4085)

