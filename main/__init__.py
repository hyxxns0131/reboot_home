from pathlib import Path
from flask import Blueprint,render_template
from products.services import get_all_products
from feed import reel_embeds
from game import play_context
bp=Blueprint('main',__name__)
MODEL_DIR=Path(__file__).resolve().parent.parent/'images'/'3d'

def product_models(products):
    # One GLB per product × flavor; flavors without a generated model are skipped.
    models=[]
    for p in products:
        for flavor in p['flavors']:
            name=f"{p['image_dir']}_{p['variant']}_{flavor.lower()}.glb"
            if (MODEL_DIR/name).exists(): models.append({'src':f'/images/3d/{name}','kind':'jelly' if p['image_dir']=='jelly' else 'drink','name':p['name'],'flavor':flavor})
    return models

@bp.get('/')
def home():
    products=get_all_products()
    return render_template('main/home.html',products=products,models=product_models(products),reels=reel_embeds(),title='Restart your day',game_heading='h2',**play_context())
