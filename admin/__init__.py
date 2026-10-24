import csv
import io
from decimal import Decimal
from flask import Blueprint, render_template, Response, abort
from auth.decorators import admin_required
from admin.services import report
bp=Blueprint('admin',__name__,url_prefix='/admin')
FIELDS={
'product-sales':'product_slug product_name order_count units_sold box_units_sold gross_sales_usd discount_usd net_sales_usd via_link_sales_usd'.split(),
'link-sales':'link_code influencer_name platform clicks order_count conversion_rate units_sold net_sales_usd commission_usd top_product'.split(),
'orders':'order_id ordered_at status product_slug product_name option_sku option_label quantity unit_price_usd discount_usd line_total_usd link_code influencer_name ship_state is_dummy'.split()}

def safe_cell(value):
    value=f'{value:.2f}' if isinstance(value,Decimal) else str(value if value is not None else '')
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value

@bp.get('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html',title='Sales overview',data=report())

@bp.get('/export/<kind>.csv')
@admin_required
def export(kind):
    if kind not in FIELDS: abort(404)
    data=report(); rows=data[{'product-sales':'products','link-sales':'links','orders':'details'}[kind]]
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=FIELDS[kind]); writer.writeheader()
    for row in rows: writer.writerow({key:safe_cell(row[key]) for key in FIELDS[kind]})
    filename=f"reboot_{kind.replace('-','_')}_{data['start'].replace('-','')}_{data['end'].replace('-','')}.csv"
    return Response(stream.getvalue().encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})
