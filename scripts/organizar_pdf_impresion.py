#!/usr/bin/env python3
"""
Reconstruye un PDF para impresion con reglas estrictas de paginacion:
- No corta observaciones ni la seccion NORMATIVIDAD INCUMPLIDA.
- Encabezados no quedan sueltos al final de pagina.
- Divide tablas solo por filas (y nunca dentro de una observacion).
- Mantiene margenes compactos para maximizar contenido.
- Usa ReportLab Platypus sin canvas absoluto.
"""

from dataclasses import dataclass
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    PageBreak,
    KeepTogether,
    CondPageBreak,
)


@dataclass
class Observacion:
    numero: int
    referencia: str
    poliza: str
    fecha: str
    concepto: str
    importe: str
    monto_observado: str
    descripcion_resultado: str
    normatividad: List[str]


USABLE_WIDTH: Optional[float] = None
USABLE_HEIGHT: Optional[float] = None
HEADER_FLOWABLES: List = []
HEADER_HEIGHT: float = 0.0
STYLES = None
FONT_SCALE = 0.75
LEADING_SCALE = 0.8
MARGIN_CM = 1.5
SPACER_SCALE = 0.7


def build_styles():
    def fs(value: float) -> float:
        return round(value * FONT_SCALE, 2)

    def lead(value: float) -> float:
        return round(value * LEADING_SCALE, 2)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name='TitleBlock',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=fs(11),
            leading=lead(13),
            spaceAfter=fs(6),
        )
    )
    styles.add(
        ParagraphStyle(
            name='Header',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=fs(10),
            leading=lead(12),
            spaceAfter=fs(6),
        )
    )
    styles.add(
        ParagraphStyle(
            name='Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=fs(9.5),
            leading=lead(12),
        )
    )
    styles.add(
        ParagraphStyle(
            name='BodyCJK',
            parent=styles['Body'],
            wordWrap='CJK',
        )
    )
    styles.add(
        ParagraphStyle(
            name='Section',
            parent=styles['Heading4'],
            fontName='Helvetica-Bold',
            fontSize=fs(9.5),
            leading=lead(12),
            spaceBefore=fs(5),
            spaceAfter=fs(3),
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name='ListItem',
            parent=styles['Body'],
            leftIndent=fs(8),
        )
    )
    return styles


def build_header(styles):
    header_lines = [
        'ENTIDAD FISCALIZADORA ESTATAL',
        'DIRECCION DE AUDITORIA A OBRA PUBLICA',
        'CEDULA DE RESULTADOS DE AUDITORIA DE OBRA PUBLICA',
    ]
    header = [Paragraph(line, styles['Header']) for line in header_lines]
    header.append(Spacer(1, 4 * SPACER_SCALE))
    return header


def build_observacion_block(obs: Observacion, styles):
    title = Paragraph(f'Observacion {obs.numero}', styles['TitleBlock'])

    description = Paragraph(obs.descripcion_resultado, styles['BodyCJK'])
    table_data = [
        [
            'REFERENCIA',
            'POLIZA / DOCUMENTO',
            'FECHA',
            'CONCEPTO',
            'IMPORTE',
            'MONTO OBSERVADO',
            'DESCRIPCION DEL RESULTADO',
        ],
        [
            obs.referencia,
            obs.poliza,
            obs.fecha,
            obs.concepto,
            obs.importe,
            obs.monto_observado,
            description,
        ],
    ]

    table = Table(
        table_data,
        colWidths=[2.2 * cm, 3.2 * cm, 2 * cm, 4.2 * cm, 2.2 * cm, 2.6 * cm, 6.6 * cm],
        repeatRows=1,
        # Tabla interna de observacion: no debe dividirse.
        splitByRow=0,
    )
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDEDED')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8.5 * FONT_SCALE),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 1), (-1, -1), 9 * FONT_SCALE),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]
        )
    )

    # NORMATIVIDAD INCUMPLIDA nunca se separa de la observacion.
    norm_header = Paragraph('NORMATIVIDAD INCUMPLIDA', styles['Section'])
    norm_items = [
        Paragraph(f'- {item}', styles['ListItem']) for item in obs.normatividad
    ]

    block = [
        title,
        table,
        Spacer(1, 4 * SPACER_SCALE),
        norm_header,
    ]
    block.extend(norm_items)
    block.append(Spacer(1, 6 * SPACER_SCALE))
    return block


def measure(flowable, avail_width):
    """
    Mide altura real con el MISMO ancho donde se dibuja.
    """
    _, height = flowable.wrap(avail_width, 10000)
    height += flowable.getSpaceBefore()
    height += flowable.getSpaceAfter()
    return height


def measure_group(flowables, avail_width):
    """
    Suma alturas de un grupo de flowables con el ancho real.
    """
    total = 0
    for flowable in flowables:
        total += measure(flowable, avail_width)
    return total


def add_page_break(story, header_flowables):
    story.append(PageBreak())
    story.extend(header_flowables)


def atomic_box(elements, width):
    """
    Encapsula elementos en una Table 1x1 con KeepTogether y splitByRow=0.
    Esto evita que una tabla grande controle los saltos de pagina.
    """
    cell = [KeepTogether(elements)]
    table = Table(
        [[cell]],
        colWidths=[width],
        splitByRow=0,
    )
    table.setStyle(
        TableStyle(
            [
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def ensure_room(story, required_height):
    """
    Inserta CondPageBreak para garantizar espacio antes de renderizar.
    """
    story.append(CondPageBreak(required_height))


def add_flowables(flowables, story, avail_width):
    """
    Agrega flowables no atomicos. Los saltos se resuelven con CondPageBreak.
    """
    for flowable in flowables:
        story.append(flowable)


def render_atomic_block(block_elements, story, avail_width):
    """
    Renderiza un bloque atómico completo.
    """
    # No confiar solo en KeepTogether: el salto se decide antes.
    cell_block = atomic_box(block_elements, avail_width)
    required_height = measure(cell_block, avail_width)
    ensure_room(story, required_height)
    story.append(cell_block)


def render_normatividad(norm_header, norm_items, story, avail_width):
    """
    Renderiza NORMATIVIDAD INCUMPLIDA como bloque indivisible.
    """
    block = [norm_header]
    block.extend(norm_items)
    required_height = measure_group(block, avail_width) + 6
    ensure_room(story, required_height)
    render_atomic_block(block, story, avail_width)


def render_observacion(observacion_data, story, avail_width, force_page_break=True):
    """
    Renderiza una observación completa como bloque atómico.
    """
    if STYLES is None:
        raise RuntimeError('STYLES no inicializado')
    block = build_observacion_block(observacion_data, styles=STYLES)
    required_height = measure_group(block, avail_width)
    ensure_room(story, required_height)
    render_atomic_block(block, story, avail_width)
    if force_page_break:
        # Regla solicitada: nada despues de NORMATIVIDAD INCUMPLIDA en la misma hoja.
        add_page_break(story, HEADER_FLOWABLES)


def render_heading_with_min_body(title, first_body_flowables, story, avail_width):
    """
    Renderiza encabezado + cuerpo con regla de arranque minima.
    """
    if not first_body_flowables:
        render_atomic_block([title], story, avail_width)
        return

    first = first_body_flowables[0]
    title_height = measure(title, avail_width)
    if isinstance(first, Paragraph):
        min_para_height = 3 * first.style.leading
        min_para_height += first.getSpaceBefore() + first.getSpaceAfter()
    else:
        min_para_height = measure(first, avail_width)
    required_height = title_height + min_para_height
    ensure_room(story, required_height)

    block = [title]
    block.extend(first_body_flowables)
    render_atomic_block(block, story, avail_width)


def render_section(title, body_elements, story, avail_width):
    """
    Renderiza encabezado + cuerpo como bloque atómico.
    """
    render_heading_with_min_body(title, body_elements[:1], story, avail_width)
    if len(body_elements) > 1:
        render_atomic_block(body_elements[1:], story, avail_width)


def build_pdf(output_path: str):
    styles = build_styles()
    page_width, page_height = A4
    margin = MARGIN_CM * cm
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    usable_width = page_width - (2 * margin)
    usable_height = page_height - (2 * margin)

    header_flowables = build_header(styles)
    header_height = measure_group(header_flowables, usable_width)

    global USABLE_WIDTH, USABLE_HEIGHT, HEADER_FLOWABLES, HEADER_HEIGHT, STYLES
    USABLE_WIDTH = usable_width
    USABLE_HEIGHT = usable_height
    HEADER_FLOWABLES = header_flowables
    HEADER_HEIGHT = header_height
    STYLES = styles

    # Datos simulados con strings largos
    observaciones = [
        Observacion(
            numero=1,
            referencia='OP-2025-014',
            poliza='POL-OP-5891',
            fecha='15/11/2025',
            concepto='Construccion de drenaje pluvial en colonia Centro',
            importe='$ 1,250,000.00',
            monto_observado='$ 320,450.00',
            descripcion_resultado=(
                'Se identificaron diferencias entre los conceptos ejecutados y los '
                'volumenes reportados en bitacora. La estimacion incluye partidas '
                'duplicadas y una variacion no justificada en el trazo. '
                'La documentacion soporte no acredita la totalidad de los trabajos '
                'segun el catalogo aprobado por el comite tecnico.'
            ),
            normatividad=[
                'Ley de Obras Publicas y Servicios Relacionados con las Mismas, art. 52',
                'Reglamento de la Ley de Obras Publicas, art. 114',
                'Lineamientos estatales de supervision, art. 8',
            ],
        ),
        Observacion(
            numero=2,
            referencia='OP-2025-027',
            poliza='DOC-OP-7723',
            fecha='21/12/2025',
            concepto='Rehabilitacion de pavimento y banquetas',
            importe='$ 890,000.00',
            monto_observado='$ 210,000.00',
            descripcion_resultado=(
                'La revision documental muestra ausencia de evidencias fotograficas '
                'y reportes de supervision diaria. Se detecto que la empresa contratista '
                'no presento pruebas de laboratorio para el control de calidad del '
                'material, y se confirmo un retraso de 18 dias no justificado en el '
                'programa original.'
            ),
            normatividad=[
                'Ley de Disciplina Financiera, art. 17',
                'Manual de supervision de obra publica, numeral 4.2',
            ],
        ),
        Observacion(
            numero=3,
            referencia='OP-2025-033',
            poliza='POL-OP-9010',
            fecha='10/01/2026',
            concepto='Ampliacion de red de agua potable',
            importe='$ 1,560,000.00',
            monto_observado='$ 415,300.00',
            descripcion_resultado=(
                'Se observaron pagos por volu menes no ejecutados en el tramo '
                'norte del proyecto. El acta de entrega-recepcion presenta '
                'inconsistencias con el generador y no se adjuntan pruebas '
                'de calibracion de medidores. La evidencia documental no '
                'soporta el monto total facturado.'
            ),
            normatividad=[
                'Ley de Obras Publicas y Servicios Relacionados con las Mismas, art. 53',
                'Reglamento de la Ley de Obras Publicas, art. 117',
                'Lineamientos estatales de supervision, art. 12',
                'Manual de control interno, capitulo III',
            ],
        ),
    ]

    story = []
    story.extend(header_flowables)

    # Simulacion de maqueta en celda estrecha (ancho real de columna).
    inner_col_width = usable_width * 0.62

    # Simula contenido previo para que el encabezado de seccion quede al final
    # si no se aplica la regla de arranque.
    filler = []
    for _ in range(7):
        filler.append(
            atomic_box(
                [
                    Paragraph(
                        'Antecedentes de revision y alcance. '
                        'Se enlistan los trabajos revisados y los criterios utilizados. '
                        'Este contenido es de prueba para forzar el caso de encabezado huérfano.',
                        styles['BodyCJK'],
                    )
                ],
                inner_col_width,
            )
        )
        filler.append(Spacer(1, 6 * SPACER_SCALE))
    add_flowables(filler, story, inner_col_width)

    # Seccion inicial: encabezado + primer parrafo deben ir juntos.
    section_title = Paragraph('CONCEPTOS DE OBRA PAGADOS', styles['Section'])
    section_body = [
        Paragraph(
            'Se revisaron los conceptos de obra pagados conforme al programa '
            'autorizado y los generadores presentados por la contratista. '
            'Este parrafo se mide y renderiza con el ancho real de la celda.',
            styles['BodyCJK'],
        )
    ]
    render_section(section_title, section_body, story, inner_col_width)

    for index, obs in enumerate(observaciones):
        # Una observacion no inicia si no cabe completa.
        force_break = index < (len(observaciones) - 1)
        render_observacion(obs, story, inner_col_width, force_page_break=force_break)

        # Seccion adicional para demostrar que "PROCESOS CONSTRUCTIVOS" no queda huerfano.
        if index == 1:
            filler2 = []
            for _ in range(5):
                filler2.append(
                    atomic_box(
                        [
                            Paragraph(
                                'Notas de seguimiento tecnico y criterios de evaluacion. '
                                'Contenido de prueba para aproximar el fin de pagina.',
                                styles['BodyCJK'],
                            )
                        ],
                        inner_col_width,
                    )
                )
                filler2.append(Spacer(1, 6 * SPACER_SCALE))
            add_flowables(filler2, story, inner_col_width)

            section_title = Paragraph('PROCESOS CONSTRUCTIVOS', styles['Section'])
            section_body = [
                Paragraph(
                    'Se identificaron desviaciones en los procesos constructivos '
                    'relacionadas con materiales y procedimientos.',
                    styles['BodyCJK'],
                )
            ]
            render_section(section_title, section_body, story, inner_col_width)

    doc.build(story)


if __name__ == '__main__':
    build_pdf('examples/cedula_resultados_impresion.pdf')
