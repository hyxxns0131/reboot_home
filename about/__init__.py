from flask import Blueprint,render_template
bp=Blueprint('about',__name__)
@bp.get('/about/story')
def index(): return render_template('about/index.html',title='Born in Korea. Made for your everyday.')
