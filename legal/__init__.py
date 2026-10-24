from flask import Blueprint,render_template
bp=Blueprint('legal',__name__)
@bp.get('/legal/')
def index(): return render_template('legal/index.html',title='The small print')
