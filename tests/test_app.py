from io import BytesIO
import unittest
from unittest.mock import patch
import zipfile

from app import create_app
from utils import FileProcessingError
from scripts.organizar_cedula_resultados_pdf import PdfOrganizationStats
from utils import CleaningStats


class AppRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')
        cls.client = cls.app.test_client()

    def test_index_renders_all_tools(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('Limpieza automatizada de cédulas de auditoría', html)
        self.assertIn('Organizar cédulas de resultados PDF', html)
        self.assertIn('Contador de cédulas PDF', html)
        self.assertIn('NUM_SIGLA_FF_PERIODO_ANEXO.pdf', html)
        self.assertNotIn('resumen.xlsx', html)
        self.assertEqual(html.count('type="file"'), 3)
        self.assertEqual(html.count('<section class="tool-card'), 3)

    def test_health_standard_route(self):
        """El healthcheck estandar /api/health debe responder 200."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'cleandoc')

    def test_health_compat_route(self):
        """/health alias debe seguir funcionando."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

    def test_only_expected_routes_are_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertEqual(
            rules,
            {
                '/',
                '/api/health',
                '/health',
                '/limpiar_cedula',
                '/organizar_cedula_resultados_pdf',
                '/contar_cedulas_pdf',
                '/static/<path:filename>',
            },
        )

    def test_pdf_organizer_logs_duplicate_and_skip_details(self):
        stats = PdfOrganizationStats(
            total_files=3,
            processed_files=1,
            duplicates_removed=1,
            skipped_files=1,
            duplicate_names=['duplicado.pdf'],
            errors=['sin_texto.pdf: No se pudo extraer texto'],
        )

        with patch('app.organizar_cedulas_resultados_pdf', return_value=([object()], stats)):
            with patch(
                'app._send_organized_pdfs',
                return_value=self.app.response_class(status=200),
            ):
                with self.assertLogs(self.app.logger, level='WARNING') as captured:
                    response = self.client.post(
                        '/organizar_cedula_resultados_pdf',
                        data={'archivo': (BytesIO(b'%PDF-1.4 test'), 'demo.pdf')},
                        content_type='multipart/form-data',
                    )

        self.assertEqual(response.status_code, 200)
        logs = '\n'.join(captured.output)
        self.assertIn('PDFs omitidos por duplicado: duplicado.pdf', logs)
        self.assertIn(
            'Incidencias de organización PDF: sin_texto.pdf: No se pudo extraer texto',
            logs,
        )

    def test_pdf_organizer_returns_detailed_errors_when_all_files_fail(self):
        stats = PdfOrganizationStats(
            total_files=2,
            processed_files=0,
            skipped_files=2,
            errors=[
                "COBAT-1.pdf: no se detectó el campo 'PERÍODO REVISADO'",
                "COBAT-2.pdf: el ente detectado 'COBAT XYZ' no se pudo vincular con el catálogo oficial",
            ],
        )

        with patch('app.organizar_cedulas_resultados_pdf', return_value=([], stats)):
            response = self.client.post(
                '/organizar_cedula_resultados_pdf',
                data={'archivo': (BytesIO(b'%PDF-1.4 test'), 'demo.pdf')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['error'], 'No se pudo organizar ningún PDF válido')
        self.assertIn('Todos los archivos fueron omitidos', data['message'])
        self.assertEqual(data['details'], stats.errors)
        self.assertEqual(data['stats']['skipped_files'], 2)

    def test_pdf_organizer_returns_internal_error_detail(self):
        with patch(
            'app.organizar_cedulas_resultados_pdf',
            side_effect=RuntimeError("falló el armado del ZIP"),
        ):
            response = self.client.post(
                '/organizar_cedula_resultados_pdf',
                data={'archivo': (BytesIO(b'%PDF-1.4 test'), 'demo.pdf')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data['error'], 'Error interno del servidor')
        self.assertIn('falló el armado del ZIP', data['message'])
        self.assertIn('RuntimeError', data['details'][0])

    def test_docx_single_download_keeps_original_name(self):
        stats = CleaningStats()

        with patch('app._process_files', return_value=([('cedula.docx', BytesIO(b'docx'))], [stats])):
            response = self.client.post(
                '/limpiar_cedula',
                data={'archivo': (BytesIO(b'PK\x03\x04docx'), 'cedula.docx')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('filename=cedula.docx', response.headers['Content-Disposition'])

    def test_docx_zip_contains_only_original_docx_names(self):
        stats = CleaningStats()
        files = [
            ('uno.docx', BytesIO(b'contenido-uno')),
            ('dos.docx', BytesIO(b'contenido-dos')),
        ]

        with patch('app._process_files', return_value=(files, [stats, stats])):
            response = self.client.post(
                '/limpiar_cedula',
                data={
                    'archivo': [
                        (BytesIO(b'PK\x03\x04docx1'), 'uno.docx'),
                        (BytesIO(b'PK\x03\x04docx2'), 'dos.docx'),
                    ]
                },
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('filename=cleandoc_limpios.zip', response.headers['Content-Disposition'])

        with zipfile.ZipFile(BytesIO(response.data)) as zf:
            names = sorted(zf.namelist())

        self.assertEqual(names, ['dos.docx', 'uno.docx'])


if __name__ == '__main__':
    unittest.main()
