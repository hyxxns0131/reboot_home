from flask import Blueprint,render_template
bp=Blueprint('vibe_test',__name__)
@bp.get('/vibe-test/')
def index(): return render_template('vibe_test/index.html',title='Find your kind of restart.')
