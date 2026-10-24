import csv
import io
from decimal import Decimal
from flask import Blueprint, render_template, Response, abort, request
from auth.decorators import admin_required
from admin.services import report, influencer_rows, PLATFORMS
from core.extensions import db
from rewards.models import Activity, PointEntry
from core.messages import Message
bp=Blueprint('admin',__name__,url_prefix='/admin')
FIELDS={
'product-sales':'product_slug product_name order_count units_sold box_units_sold gross_sales_usd discount_usd net_sales_usd via_link_sales_usd'.split(),
'link-sales':'link_code influencer_name platform clicks order_count conversion_rate units_sold net_sales_usd commission_usd top_product'.split(),
'orders':'order_id ordered_at status product_slug product_name option_sku option_label quantity unit_price_usd discount_usd line_total_usd link_code influencer_name ship_state is_dummy points_used'.split(),
'option-sales':'product_slug product_name product_line option_sku option_label pack_size list_price_usd order_count quantity_sold pieces_sold gross_sales_usd discount_usd net_sales_usd direct_sales_usd instagram_sales_usd tiktok_sales_usd'.split(),
'influencer-sales':'platform influencer_name discount_code link_path discount_rate commission_rate clicks order_count conversion_rate units_sold gross_sales_usd discount_usd net_sales_usd commission_usd top_product'.split(),
'influencer-orders':'order_id ordered_at status platform influencer_name discount_code link_path discount_rate product_slug product_name option_sku option_label quantity unit_price_usd gross_usd discount_usd line_total_usd commission_rate commission_usd ship_state is_dummy'.split()}
SOURCES={'product-sales':'products','link-sales':'links','orders':'details','option-sales':'options','influencer-sales':'links','influencer-orders':'influencer_details'}
INFLUENCER_KINDS=('influencer-sales','influencer-orders')

def safe_cell(value):
    value=f'{value:.2f}' if isinstance(value,Decimal) else str(value if value is not None else '')
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value

@bp.get('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html',title='Sales overview',data=report(),activities=db.session.scalars(db.select(Activity).order_by(Activity.id.desc()).limit(100)).all(),point_entries=db.session.scalars(db.select(PointEntry).order_by(PointEntry.id.desc()).limit(100)).all(),messages=db.session.scalars(db.select(Message).order_by(Message.id.desc()).limit(50)).all())

@bp.get('/export/<kind>.csv')
@admin_required
def export(kind):
    if kind not in FIELDS: abort(404)
    platform=request.args.get('platform','all')
    if kind in INFLUENCER_KINDS and platform not in ('all',*PLATFORMS): abort(400,description='Choose instagram, tiktok, or all.')
    data=report(); rows=data[SOURCES[kind]]
    if kind in INFLUENCER_KINDS: rows=influencer_rows(rows,platform)
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=FIELDS[kind]); writer.writeheader()
    for row in rows: writer.writerow({key:safe_cell(row[key]) for key in FIELDS[kind]})
    suffix=f'_{platform}' if kind in INFLUENCER_KINDS else ''
    filename=f"reboot_{kind.replace('-','_')}{suffix}_{data['start'].replace('-','')}_{data['end'].replace('-','')}.csv"
    return Response(stream.getvalue().encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})
