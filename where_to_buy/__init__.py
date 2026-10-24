from flask import Blueprint,render_template
bp=Blueprint('where_to_buy',__name__)
@bp.get('/where-to-buy/')
def index(): return render_template('where_to_buy/index.html',title='Your next Reboot starts here.')
