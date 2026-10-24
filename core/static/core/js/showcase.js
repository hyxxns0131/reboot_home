/* Image-based multi-view animation, NOT a reconstructed 360° model.
 * Original front/quarter/side/back photographs are never mirrored or warped.
 * Gummy packs have no reverse photograph: the actual candy turns beside a pack
 * that only lifts/tilts. Scroll owns the outer wrapper; selection owns the inner.
 */
(() => {
  'use strict';
  // The old shot-hero ([data-showcase]) may be absent: the motion hero replaced it.
  // The drink / gummy collections below still need the helpers, so only that part is skipped.
  const root=document.querySelector('[data-showcase]');
  const $=s=>document.querySelector(s);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const flavors={
    lime:{color:'#b0ef38',pastel:'#d2e9b4',note:'A bright citrus restart.',detail:'Bright lime with a crisp citrus finish.'},
    lemon:{color:'#ffe137',pastel:'#f4e7a2',note:'A little sunshine. Bottled.',detail:'Zesty lemon with a bright, tangy finish.'},
    cherry:{color:'#ef3a51',pastel:'#f2afc7',note:'Make your next day a good one.',detail:'Juicy cherry with a sweet, fruity finish.'}
  };
  const products=[...['original','balance'].flatMap(line=>['lime','lemon','cherry'].map(flavor=>({kind:'drink',line,flavor,...flavors[flavor]}))),
    ...['original','balance'].map(line=>({kind:'gummy',line,flavor:'lime',color:'#c5ff4b',pastel:'#e1c5ff',note:'Cherry. Lemon. Lime. All in one pouch.'}))];
  const src=(p,angle='front')=>`/images/showcase/${p.line}_${p.flavor}-${angle}.webp`;
  const angleSrc=(p,angle)=>p.kind==='gummy'?`/images/showcase/gummy_${p.line}_lime-${angle}.webp`:src(p,angle);
  const mainSrc=p=>p.kind==='gummy'?`/images/product_image/web/cutout/jelly-${p.line}-package.webp`:src(p);
  const shop=p=>p.kind==='gummy'?`/products/jelly-${p.line}`:`/products/drink-${p.line}?sku=drink-${p.line}-${p.flavor}`;
  const label=p=>`${p.line} ${p.kind==='gummy'?'gummy':`${p.flavor} drink`}`;
  const cache=new Map();
  const load=url=>{
    if(!cache.has(url))cache.set(url,new Promise((resolve,reject)=>{
      const img=new Image();
      const timer=setTimeout(()=>{cache.delete(url);reject(new Error('Image timeout'));},12000);
      img.onload=()=>{clearTimeout(timer);resolve(img);};
      img.onerror=()=>{clearTimeout(timer);cache.delete(url);reject(new Error('Image unavailable'));};
      img.src=url;
    }));
    return cache.get(url);
  };
  const preload=p=>Promise.all(['front','quarter','side','back'].map(a=>load(angleSrc(p,a))));
  if(root){
  const button=$('#shot-button'),image=$('#hero-bottle'),canvas=$('#bottle-sequence'),gummyCanvas=$('#gummy-sequence'),holder=$('.bottle-float');
  const controls=[...document.querySelectorAll('[data-product-index]')];
  controls.forEach((control,i)=>{
    const angle=(i*45-90)*Math.PI/180;
    control.style.setProperty('--orbit-x',`${50+41*Math.cos(angle)}%`);
    control.style.setProperty('--orbit-y',`${50+41*Math.sin(angle)}%`);
    control.addEventListener('click',()=>selectProduct(i));
    control.addEventListener('pointerenter',()=>preload(products[i]).catch(()=>{}));
    control.addEventListener('focus',()=>preload(products[i]).catch(()=>{}));
    control.addEventListener('keydown',e=>{
      if(!['ArrowRight','ArrowLeft','ArrowUp','ArrowDown','Home','End'].includes(e.key))return;
      e.preventDefault();
      const index=e.key==='Home'?0:e.key==='End'?controls.length-1:(i+(['ArrowLeft','ArrowUp'].includes(e.key)?-1:1)+controls.length)%controls.length;
      controls[index].focus();
    });
  });
  let current=0,busy=false,timeline=null,completeTurn=null;
  function draw(target,frames,progress){
    const ctx=target.getContext('2d');if(!ctx)return;
    ctx.clearRect(0,0,target.width,target.height);
    const f=Math.min(frames.length-1,progress*(frames.length-1)),i=Math.floor(f),mix=Math.max(0,Math.min(1,(f-i-.4)/.6));
    const paint=(img,alpha)=>{
      // Preserve the height between photographed angles; side views stay narrow.
      const h=target.height,w=h*img.width/img.height;
      ctx.globalAlpha=alpha;ctx.drawImage(img,(target.width-w)/2,0,w,h);
    };
    paint(frames[i],1-mix);if(mix>0&&i+1<frames.length)paint(frames[i+1],mix);ctx.globalAlpha=1;
  }
  function update(index){
    const p=products[index];current=index;
    root.dataset.product=p.kind==='gummy'?`gummy_${p.line}`:`${p.line}_${p.flavor}`;
    root.dataset.kind=p.kind;
    root.style.setProperty('--flavor',p.line==='balance'?p.pastel:p.color);
    $('#hero-line').textContent=`${p.line.toUpperCase()} ${p.kind==='gummy'?'GUMMY / THREE FLAVORS':'DRINK / 100 ML'}`;
    $('#hero-flavor').textContent=p.kind==='gummy'?'GUMMY':p.flavor.toUpperCase();
    $('#hero-note').textContent=p.note;
    $('#shot-count').textContent=`0${index+1} / 08`;
    image.src=mainSrc(p);image.alt=`REBOOT ${label(p)}`;
    $('#hero-shop-link').href=shop(p);$('#hero-shop-link').setAttribute('aria-label',`Shop ${label(p)}`);
    button.setAttribute('aria-label',`SHOT — next: ${label(products[(index+1)%products.length])}`);
    controls.forEach((control,i)=>control.setAttribute('aria-pressed',String(i===index)));
    $('.hero-gummy-candies').hidden=p.kind!=='gummy';
    document.querySelectorAll('.hero-candy').forEach((img,i)=>{const flavor=i?'lemon':'cherry';img.src=`/images/product_image/web/cutout/jelly-${p.line}-${flavor}.webp`;});
    const companion=p.kind==='gummy'?{kind:'drink',line:p.line,flavor:'lime'}:{kind:'gummy',line:p.line,flavor:'lime'};
    $('#companion-link').href=shop(companion);$('#companion-link').setAttribute('aria-label',`Shop ${label(companion)}`);
    $('#companion-label').textContent=`${p.line.toUpperCase()} ${companion.kind==='gummy'?'GUMMY':'LIME DRINK'}`;
    $('#companion-image').src=mainSrc(companion);$('#companion-image').alt=`REBOOT ${label(companion)}`;
    $('#companion-link').lastElementChild.textContent=companion.kind==='gummy'?'SHOP GUMMIES ↗':'SHOP DRINKS ↗';
  }
  async function selectProduct(next){
    if(busy)return;
    busy=true;root.setAttribute('aria-busy','true');$('#shot-status').textContent='';
    [button,...controls].forEach(b=>b.setAttribute('aria-disabled','true'));
    try{
      const p=products[next];
      const [views]=await Promise.all([preload(p),load(mainSrc(p))]);
      update(next);
      const target=p.kind==='gummy'?gummyCanvas:canvas;
      target.width=views[0].width;target.height=views[0].height;
      draw(target,[views[0]],0);
      if(reduced.matches||!window.gsap||!target.getContext('2d'))return;
      // Direct selection immediately reveals the chosen product, then turns it
      // rapidly through its authentic views. It never cycles unrelated products.
      const frames=[views[0],views[1],views[2],views[3],views[2],views[1],views[0]],state={p:0};
      if(p.kind==='drink'){canvas.hidden=false;image.hidden=true;}
      await new Promise(resolve=>{
        completeTurn=resolve;timeline=gsap.timeline({onComplete:resolve});
        timeline.fromTo(holder,{y:36,rotation:-10,scale:.82},{y:-24,rotation:6,scale:1.04,duration:.3,ease:'power2.out'},0);
        timeline.to(state,{p:1,duration:.78,ease:'none',onUpdate:()=>draw(target,frames,state.p)},0);
        timeline.to(holder,{y:0,rotation:0,scale:1,duration:.48,ease:'power2.out'},.3);
        timeline.fromTo(button,{scale:.9},{scale:1,duration:.3,ease:'back.out(2)'},0);
      });
    }catch(error){$('#shot-status').textContent='Unable to load this product. Please try again.';}
    finally{
      canvas.hidden=true;image.hidden=false;
      if(window.gsap)gsap.set([holder,button],{clearProps:'transform'});
      busy=false;timeline=null;completeTurn=null;root.removeAttribute('aria-busy');
      [button,...controls].forEach(b=>b.removeAttribute('aria-disabled'));
      preload(products[(current+1)%products.length]).catch(()=>{});
    }
  }
  button.addEventListener('click',()=>selectProduct((current+1)%products.length));
  reduced.addEventListener('change',()=>{if(reduced.matches&&timeline){timeline.progress(1);completeTurn?.();}});
  update(0);preload(products[0]).then(()=>preload(products[1])).catch(()=>{});
  if(window.gsap&&window.ScrollTrigger){
    gsap.registerPlugin(ScrollTrigger);
    gsap.matchMedia().add('(prefers-reduced-motion: no-preference)',()=>{
      gsap.timeline({scrollTrigger:{trigger:root,start:'top top',end:'bottom top',scrub:.5}})
        .to('.bottle-scroll',{y:55,xPercent:3,scale:1.08,ease:'none'},0)
        .to('.showcase-tagline',{y:-30,opacity:0,ease:'none'},0);
    });
  }
  }
  let line='original',selected='lime';
  function selectDrink(){
    document.querySelectorAll('.drink-choice').forEach(card=>{
      const flavor=card.dataset.flavor,active=flavor===selected;
      card.dataset.selected=String(active);card.querySelector('button').setAttribute('aria-pressed',String(active));
      card.querySelector('img').src=src({line,flavor});card.querySelector('img').alt=`REBOOT ${line} ${flavor} bottle`;
      card.querySelector('.choice-name').textContent=(line==='balance'?'BALANCE ':'')+flavor.toUpperCase();
      card.querySelector('a').href=shop({kind:'drink',line,flavor});card.querySelector('a').setAttribute('aria-label',`Shop ${line} ${flavor} drink`);
    });
    $('#drink-name').textContent=`${line} ${selected}`.toUpperCase();$('#drink-note').textContent=flavors[selected].detail;
    $('#drink-link').href=shop({kind:'drink',line,flavor:selected});
  }
  const tabs=[...document.querySelectorAll('[data-line]')];
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>{line=tab.dataset.line;tabs.forEach(t=>{t.setAttribute('aria-selected',String(t===tab));t.tabIndex=t===tab?0:-1;});$('#drinks-panel').setAttribute('aria-labelledby',tab.id);selectDrink();});
    tab.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();const target=tabs[e.key==='Home'?0:e.key==='End'?tabs.length-1:1-index];target.click();target.focus();});
  });
  document.querySelectorAll('.drink-select').forEach(b=>b.addEventListener('click',()=>{selected=b.closest('[data-flavor]').dataset.flavor;selectDrink();}));
  document.querySelectorAll('[data-gummy]').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('[data-gummy]').forEach(t=>{t.setAttribute('aria-pressed',String(t===b));t.closest('.gummy-choice').dataset.selected=String(t===b);});
    $('#gummy-scene').src=`/images/product_image/web/jelly-${b.dataset.gummy}-scene-wide.webp`;
    $('#gummy-scene').alt=`${b.dataset.gummy} gummy package with cherry, lemon and lime candies`;
    $('#gummy-scene-link').href=`/products/jelly-${b.dataset.gummy}`;
    $('#gummy-name').textContent=`${b.dataset.gummy.toUpperCase()} GUMMY`;
    document.querySelectorAll('[data-gummy-flavor]').forEach(img=>{img.src=`/images/product_image/web/cutout/jelly-${b.dataset.gummy}-${img.dataset.gummyFlavor}.webp`;img.alt=`${b.dataset.gummy} ${img.dataset.gummyFlavor} gummy`;img.closest('a').href=`/products/jelly-${b.dataset.gummy}`;});
  }));
})();
