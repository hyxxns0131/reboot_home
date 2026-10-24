'use strict';
(() => {
  const ko = document.documentElement.lang === 'ko';
  const words = ko ? {
    ready:'같은 그림의 카드 두 장을 골라주세요.', loading:'게임을 불러오는 중…',
    again:'오늘의 보상을 이미 받았습니다. 다음 게임은 UTC 자정에 열립니다.',
    won:'카드 여섯 쌍을 모두 찾았어요! 100포인트가 적립되었습니다.',
    match:'짝을 찾았어요!', miss:'다시 기억해보세요.', error:'연결을 확인하고 게임 시작 / 이어하기를 눌러주세요.',
    login:'로그인이 필요합니다. 다시 로그인해주세요.', moves:'시도', card:'카드', matched:'찾은 짝',
  } : {
    ready:'Choose two cards with the same symbol.', loading:'Loading your game…',
    again:'Today’s reward is already yours. A new game opens at midnight UTC.',
    won:'All six pairs matched! 100 points have been added to your wallet.',
    match:'A perfect match!', miss:'Remember these for your next turn.', error:'Check your connection, then start / resume the game.',
    login:'Please sign in again.', moves:'Moves', card:'Card', matched:'Matched',
  };
  const start = document.getElementById('game-start');
  if (!start) return;
  const board = document.getElementById('memory-board'), status = document.getElementById('game-status');
  const win = document.getElementById('game-win');
  const symbols = ['✳','∞','◈','☀','☾','✦'];
  let state = null, busy = false, shown = {};
  async function api(path, data) {
    const response = await fetch(`/rewards/${path}`, {
      method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},
      body:JSON.stringify(data || {}), credentials:'same-origin',
    });
    if (response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) throw new Error(words.login);
    const payload = await response.json();
    if (!response.ok) throw new Error(words.error);
    return payload;
  }
  function draw() {
    board.replaceChildren();
    for (let i=0;i<12;i++) {
      const matched = state.matched.includes(i), face = state.faces[i] ?? shown[i];
      const up = matched || state.first === i || shown[i] !== undefined;
      const card = document.createElement('button');
      card.type='button'; card.className=`memory-card${up ? ' flipped' : ''}${matched ? ' matched' : ''}`;
      card.dataset.index=String(i); card.textContent=up ? symbols[face] : '↻';
      card.setAttribute('aria-label',`${words.card} ${i+1}${up ? ': '+symbols[face] : ''}${matched ? ' '+words.matched : ''}`);
      card.disabled=busy || matched || state.first === i || state.complete;
      card.addEventListener('click',()=>flip(i)); board.append(card);
    }
    document.getElementById('game-moves').textContent=`${words.moves}: ${state.moves} · ${state.matched.length/2} / 6`;
    document.querySelectorAll('[data-point-balance]').forEach(el=>el.textContent=state.balance);
    win.hidden=!state.complete;
  }
  async function flip(index) {
    if (busy || !state || state.complete) return;
    busy=true; start.disabled=true; draw();
    try {
      const result = await api('flip',{id:state.id,index,version:state.version});
      if (state.first !== null) shown[state.first]=state.first_face;
      shown[index]=result.face;
      state=result;
      if (state.first !== null) shown[state.first]=state.first_face;
      status.textContent=state.complete ? words.won : (result.pair ? (state.matched.includes(index) ? words.match : words.miss) : words.ready);
      draw();
      if (result.pair && !state.complete) await new Promise(resolve=>setTimeout(resolve,850));
      shown={}; if (state.first !== null) shown[state.first]=state.first_face;
      win.querySelector('p').textContent=words.again;
    } catch(error) {
      status.textContent=error.message;
      // Block further flips until a fresh server snapshot is loaded.
      state=null;
      board.querySelectorAll('button').forEach(b=>b.disabled=true);
    } finally {
      busy=false; start.disabled=false;
      if (state) draw();
    }
  }
  start.addEventListener('click',async()=>{
    if (busy) return;
    busy=true; start.disabled=true; status.textContent=words.loading;
    try {
      state=await api('start'); shown={};
      if (state.first !== null) shown[state.first]=state.first_face;
      status.textContent=state.complete ? words.again : words.ready;
      win.querySelector('p').textContent=words.again;
    } catch(error) { status.textContent=error.message; }
    finally { busy=false; start.disabled=false; if(state) draw(); }
  });
})();
