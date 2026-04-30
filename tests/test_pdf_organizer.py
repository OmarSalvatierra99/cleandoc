from pathlib import Path
import unittest

from werkzeug.datastructures import FileStorage

from scripts.organizar_cedula_resultados_pdf import (
    construir_diccionario_entes,
    construir_codigo_ente,
    construir_codigo_fuente,
    construir_numero_ente,
    construir_codigo_periodo,
    construir_ruta_unica,
    describir_incidencia_campos,
    extraer_anexo,
    extraer_campos,
    extraer_observacion_refs,
    extraer_total_observaciones,
    hash_texto,
    limpiar_nombre,
    normalizar_espacios,
    organizar_cedulas_resultados_pdf,
    resolver_ente_catalogo,
)


class PdfOrganizerHelpersTests(unittest.TestCase):
    def test_limpiar_nombre_normalizes_text_for_paths(self):
        self.assertEqual(
            limpiar_nombre("  Secretaría de Infraestructura / Etapa 1 "),
            "SECRETARIA_DE_INFRAESTRUCTURA_ETAPA_1",
        )

    def test_normalizar_espacios_collapses_multiline_values(self):
        self.assertEqual(
            normalizar_espacios("01 DE ENERO AL 27 DE\nMAYO"),
            "01 DE ENERO AL 27 DE MAYO",
        )

    def test_extraer_campos_reads_expected_values_from_examples(self):
        texto = normalizar_espacios("""
        CÉDULA DE RESULTADOS DE AUDITORÍA FINANCIERA 2025
        ENTE FISCALIZABLE: PODER EJECUTIVO DEL ESTADO DE TLAXCALA
        FUENTE DE FINANCIAMIENTO: INGRESOS PROPIOS, PARTICIPACIONES ESTATALES Y RECURSOS FEDERALES
        SOLICITUD DE ACLARACIÓN (SA)
        PERIODO REVISADO: 01 DE ENERO AL 31 DE DICIEMBRE
        DESCRIPCIÓN DEL RESULTADO
        ANEXO: 4 OBSERVACIÓN: 0
        8 Total de Observaciones.
        """)

        campos = extraer_campos(texto)

        self.assertEqual(
            campos["ente_original"].upper(),
            "PODER EJECUTIVO DEL ESTADO DE TLAXCALA",
        )
        self.assertEqual(
            campos["fuente_original"],
            "INGRESOS PROPIOS, PARTICIPACIONES ESTATALES Y RECURSOS FEDERALES",
        )
        self.assertEqual(campos["periodo_original"], "01 DE ENERO AL 31 DE DICIEMBRE")
        self.assertEqual(campos["anexo"], "SA")
        self.assertEqual(campos["observacion_refs"], ["0"])
        self.assertEqual(campos["total_observaciones"], 8)
        self.assertEqual(campos["ente_codigo"], "EJECUTIVO")
        self.assertEqual(campos["ente_numero"], "1")
        self.assertEqual(campos["periodo_codigo"], "ENE-DIC")
        self.assertEqual(campos["fuente_codigo"], "IP_PE_RF")

    def test_construir_codigos_cortos_para_nombre_archivo(self):
        self.assertEqual(
            construir_codigo_ente("INSTITUTO TLAXCALTECA DE LA INFRAESTRUCTURA FÍSICA EDUCATIVA"),
            "ITIFE",
        )
        self.assertEqual(
            construir_numero_ente("PODER JUDICIAL DEL ESTADO DE TLAXCALA"),
            "3",
        )
        self.assertEqual(
            construir_codigo_periodo("16 DE MAYO AL 30 DE JUNIO"),
            "MAY-JUN",
        )
        self.assertEqual(
            construir_codigo_fuente(
                "PARTICIPACIONES ESTATALES (FONDO GENERAL DE PARTICIPACIONES)"
            ),
            "PE_FGP",
        )
        self.assertEqual(
            construir_codigo_fuente(
                "SEGUIMIENTO A PASIVOS DE EJERCICIOS ANTERIORES: "
                "FONDO DE APORTACIONES PARA EL FORTALECIMIENTO DE LAS ENTIDADES FEDERATIVAS"
            ),
            "SPEA_FAFEF",
        )
        self.assertEqual(
            construir_codigo_ente("SECRETARÍA DE MOVILIDAD Y TRANSPORTE"),
            "SMYT",
        )
        self.assertEqual(
            construir_codigo_ente("UPTREP"),
            "UTREP",
        )

    def test_construir_diccionario_entes_uses_catalogo_general_corrections(self):
        catalogo = construir_diccionario_entes()

        self.assertEqual(
            catalogo["SECRETARIA DE MOVILIDAD Y TRANSPORTE"]["siglas"],
            "SMYT",
        )
        self.assertEqual(
            catalogo["UNIVERSIDAD POLITECNICA DE TLAXCALA REGION PONIENTE"]["siglas"],
            "UTREP",
        )
        self.assertEqual(catalogo["SM"]["siglas"], "SMYT")
        self.assertEqual(catalogo["UPTREP"]["siglas"], "UTREP")

    def test_resolver_ente_catalogo_finds_closest_match(self):
        record = resolver_ente_catalogo("SECRETARIA DE INFRAESTRUCTRA")

        self.assertIsNotNone(record)
        self.assertEqual(record["siglas"], "SI")
        self.assertEqual(record["num"], "1.16")

    def test_extraer_anexo_supports_multiple_codes(self):
        self.assertEqual(extraer_anexo("SOLICITUD DE ACLARACIÓN (SA)"), "SA")
        self.assertEqual(extraer_anexo("SOLICITUDES DE ACLARACIÓN"), "SA")
        self.assertEqual(extraer_anexo("POSIBLE DAÑO PATRIMONIAL"), "PDP")
        self.assertEqual(extraer_anexo("PROBABLE DAÑO PATRIMONIAL (PDP)"), "PDP")
        self.assertEqual(
            extraer_anexo("PROMOCIÓN DE RESPONSABILIDAD ADMINISTRATIVA SANCIONATORIA (PRAS)"),
            "PRAS",
        )
        self.assertEqual(
            extraer_anexo("PROMOCIONES DE RESPONSABILIDAD ADMINISTRATIVA SANCIONATORIA"),
            "PRAS",
        )
        self.assertEqual(
            extraer_anexo("PROMOCIÓN DEL EJERCICIO DE LA FACULTAD DE COMPROBACIÓN FISCAL (PEFCF)"),
            "PEFCF",
        )
        self.assertEqual(
            extraer_anexo("PROMOCIONES DEL EJERCICIO DE LA FACULTAD DE COMPROBACIÓN FISCAL"),
            "PEFCF",
        )
        self.assertEqual(extraer_anexo("RECOMENDACIÓN"), "R")
        self.assertEqual(extraer_anexo("RECOMENDACIONES (R)"), "R")

    def test_extraer_campos_stops_ente_before_plural_pras_heading(self):
        texto = normalizar_espacios("""
        ENTE FISCALIZABLE: FIDEICOMISO DE LA CIUDAD INDUSTRIAL DE XICOTÉNCATL
        PROMOCIONES DE RESPONSABILIDAD ADMINISTRATIVA SANCIONATORIA (PRAS)
        FUENTE DE FINANCIAMIENTO: RECURSOS RECAUDADOS Y PARTICIPACIONES ESTATALES
        PERIODO REVISADO: 01 DE JULIO AL 31 DE JULIO
        """)

        campos = extraer_campos(texto)

        self.assertEqual(
            campos["ente_original"].upper(),
            "FIDEICOMISO DE LA CIUDAD INDUSTRIAL DE XICOTÉNCATL",
        )
        self.assertTrue(campos["ente_resuelto"])
        self.assertEqual(campos["ente_numero"], "12")
        self.assertEqual(campos["ente_codigo"], "FIDECIX")
        self.assertEqual(campos["anexo"], "PRAS")

    def test_extraer_observacion_refs_and_total_observaciones(self):
        texto = "ANEXO: 4 OBSERVACIÓN: 0 ANEXO: 5 OBSERVACIÓN: 1 7 Total de Observaciones."

        self.assertEqual(extraer_observacion_refs(texto), ["0", "1"])
        self.assertEqual(extraer_total_observaciones(texto), 7)

    def test_extraer_total_observaciones_uses_last_multiline_match(self):
        texto = """
        2 TOTAL DE OBSERVACIONES.
        Texto intermedio
        9 TOTAL DE OBSERVACIONES.
        """

        self.assertEqual(extraer_total_observaciones(texto), 9)

    def test_hash_texto_detects_identical_content(self):
        self.assertEqual(hash_texto("abc"), hash_texto("abc"))
        self.assertNotEqual(hash_texto("abc"), hash_texto("xyz"))

    def test_construir_ruta_unica_avoids_name_collisions(self):
        usados = {"1.7_ENTE_PE_FGP_ENE-MAY_R.pdf"}

        output_name, archive_path = construir_ruta_unica(
            "1.7",
            "ENTE",
            "ENE-MAY",
            "PE_FGP",
            "R",
            usados,
        )

        self.assertEqual(output_name, "1.7_ENTE_PE_FGP_ENE-MAY_R_1.pdf")
        self.assertEqual(
            archive_path,
            "1.7_ENTE_PE_FGP_ENE-MAY_R_1.pdf",
        )

    def test_describir_incidencia_campos_reports_missing_values(self):
        incidencia = describir_incidencia_campos(
            {
                "ente_original": "COBAT DESCONOCIDO",
                "ente_resuelto": False,
                "ente_numero": "",
                "fuente_original": "SIN_FUENTE",
                "periodo_original": "SIN_PERIODO",
                "anexo": "SIN_ANEXO",
            }
        )

        self.assertIn("COBAT DESCONOCIDO", incidencia)
        self.assertIn("FUENTE DE FINANCIAMIENTO", incidencia)
        self.assertIn("PERÍODO REVISADO", incidencia)
        self.assertIn("tipo de anexo", incidencia)

    def test_organizar_cedulas_resultados_pdf_processes_pras_examples(self):
        base = Path(__file__).resolve().parents[1] / "examples" / "example_PDF_Omitidos"
        handles = []
        files = []

        try:
            for path in sorted(base.glob("*.pdf")):
                fh = path.open("rb")
                handles.append(fh)
                files.append(FileStorage(stream=fh, filename=path.name))

            organized, stats = organizar_cedulas_resultados_pdf(files)
        finally:
            for fh in handles:
                fh.close()

        self.assertEqual(len(files), 12)
        self.assertEqual(stats.processed_files, 12)
        self.assertEqual(stats.skipped_files, 0)
        self.assertEqual(stats.duplicates_removed, 0)
        self.assertEqual(stats.errors, [])
        self.assertEqual(len(organized), 12)


if __name__ == "__main__":
    unittest.main()
