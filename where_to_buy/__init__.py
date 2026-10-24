from flask import Blueprint,render_template
bp=Blueprint('where_to_buy',__name__)
# Retail partners in display order; each button opens the partner's site in a new tab.
RETAILERS=[('Yamibuy','https://www.yamibuy.com/'),('Amazon','https://www.amazon.com/'),('Olive Young Global','https://global.oliveyoung.com/'),('Weee!','https://www.sayweee.com/')]
@bp.get('/where-to-buy/')
def index(): return render_template('where_to_buy/index.html',retailers=RETAILERS,title='Your next Reboot starts here.')
