import os, io, secrets
from flask import Blueprint, render_template, redirect, url_for, send_file
from flask_login import login_required, current_user
from extensions import db
from database.models import Certificate, UserQuizAttempt, Quiz

certificates_bp = Blueprint('certificates', __name__, url_prefix='/certificates')

@certificates_bp.route('/')
@login_required
def index():
    certs = Certificate.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Certificate.issued_at.desc()).all()
    return render_template('certificates/index.html', certs=certs)

@certificates_bp.route('/download/<int:cert_id>')
@login_required
def download(cert_id):
    cert = Certificate.query.filter_by(id=cert_id, user_id=current_user.id, is_deleted=False).first_or_404()
    pdf  = _generate_pdf(cert)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
        as_attachment=True, download_name=f'certificate_{cert.cert_number}.pdf')


@certificates_bp.route('/download/u/<string:cert_uuid>')
@login_required
def download_by_uuid(cert_uuid):
    """UUID-based certificate download endpoint for non-sequential URLs."""
    cert = Certificate.query.filter_by(uuid=cert_uuid, user_id=current_user.id, is_deleted=False).first_or_404()
    pdf  = _generate_pdf(cert)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
        as_attachment=True, download_name=f'certificate_{cert.cert_number}.pdf')

def _generate_pdf(cert):
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=0.8*inch, bottomMargin=0.8*inch,
                                leftMargin=1*inch, rightMargin=1*inch)
        elements = []
        title_s  = ParagraphStyle('t', fontSize=30, fontName='Helvetica-Bold', alignment=TA_CENTER,
                                   textColor=colors.HexColor('#4f46e5'), spaceAfter=4)
        sub_s    = ParagraphStyle('s', fontSize=14, fontName='Helvetica', alignment=TA_CENTER,
                                   textColor=colors.HexColor('#5a5850'), spaceAfter=8)
        name_s   = ParagraphStyle('n', fontSize=26, fontName='Helvetica-Bold', alignment=TA_CENTER,
                                   textColor=colors.HexColor('#1a1916'), spaceAfter=10)
        small_s  = ParagraphStyle('sm', fontSize=11, fontName='Helvetica', alignment=TA_CENTER,
                                   textColor=colors.HexColor('#98968e'), spaceAfter=6)
        elements.append(Paragraph('🎓 Certificate of Achievement', title_s))
        elements.append(HRFlowable(width='80%', thickness=2, color=colors.HexColor('#4f46e5')))
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph('This certifies that', sub_s))
        elements.append(Paragraph(cert.user.name, name_s))
        elements.append(Paragraph('has successfully completed', sub_s))
        elements.append(Paragraph(f'<b>{cert.title}</b>', sub_s))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(HRFlowable(width='60%', thickness=1, color=colors.HexColor('#e8e5dd')))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f'Certificate No: <b>{cert.cert_number}</b>', small_s))
        elements.append(Paragraph(f'Issued: {cert.issued_at.strftime("%B %d, %Y")}', small_s))
        elements.append(Paragraph('SyllabusEngine — AI-Powered Education Platform', small_s))
        doc.build(elements)
        return buf.getvalue()
    except ImportError:
        return b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF'

def issue_certificate(user_id, quiz_id, attempt_id, quiz_title):
    """Call this after a passing attempt."""
    existing = Certificate.query.filter_by(user_id=user_id, attempt_id=attempt_id).first()
    if existing:
        return existing
    cert = Certificate(user_id=user_id, quiz_id=quiz_id, attempt_id=attempt_id,
        title=f'Certificate of Completion: {quiz_title}',
        cert_number=f'CERT-{secrets.token_hex(6).upper()}')
    db.session.add(cert); db.session.commit()
    return cert
